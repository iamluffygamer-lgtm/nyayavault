"""Required coverage: (9) audit event creation, plus hash-chain integrity."""

from __future__ import annotations

from tests.conftest import PASSWORDS, auth, create_case, login, upload_document


def _actions(events: list[dict]) -> list[str]:
    return [e["action"] for e in events]


def test_case_creation_writes_an_audit_event(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Audited case")

    events = client.get(f"/api/v1/cases/{case['id']}/audit", headers=auth(token)).json()
    assert events["total"] >= 1
    assert "CASE_CREATED" in _actions(events["items"])

    created = next(e for e in events["items"] if e["action"] == "CASE_CREATED")
    assert created["actor"]["username"] == "investigator"
    assert created["result"] == "SUCCESS"
    assert created["event_metadata"]["case_number"] == case["case_number"]
    assert len(created["event_hash"]) == 64
    assert len(created["previous_event_hash"]) == 64


def test_document_upload_writes_an_audit_event_with_the_hash(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Audited upload")
    document = upload_document(client, token, case["id"]).json()

    events = client.get(f"/api/v1/cases/{case['id']}/audit", headers=auth(token)).json()["items"]
    uploaded = next(e for e in events if e["action"] == "DOCUMENT_UPLOADED")

    assert uploaded["event_metadata"]["document_id"] == document["id"]
    assert uploaded["event_metadata"]["version_number"] == 1
    assert uploaded["event_metadata"]["sha256"] == document["versions"][0]["sha256_hash"]


def test_downloads_and_verifications_are_audited(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Chain of custody")
    document = upload_document(client, token, case["id"]).json()

    client.get(f"/api/v1/documents/{document['id']}/download", headers=auth(token))
    client.get(f"/api/v1/documents/{document['id']}/verify", headers=auth(token))

    actions = _actions(
        client.get(f"/api/v1/cases/{case['id']}/audit", headers=auth(token)).json()["items"]
    )
    assert "DOCUMENT_DOWNLOADED" in actions
    assert "DOCUMENT_INTEGRITY_VERIFIED" in actions


def test_failed_logins_are_audited_without_leaking_the_password(client):
    client.post("/api/v1/auth/login", json={"username": "investigator", "password": "wrong"})

    events = client.get("/api/v1/audit/events", headers=auth(login(client, "admin"))).json()
    failures = [e for e in events["items"] if e["action"] == "LOGIN_FAILED"]

    assert failures, "a failed login must be recorded"
    serialised = str(failures[0])
    assert "wrong" not in serialised
    assert PASSWORDS["investigator"] not in serialised


def test_rejected_uploads_are_audited(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Rejected upload case")
    upload_document(
        client, token, case["id"], filename="evil.exe", content=b"MZ\x90", content_type="application/octet-stream"
    )

    events = client.get(f"/api/v1/cases/{case['id']}/audit", headers=auth(token)).json()["items"]
    rejected = next(e for e in events if e["action"] == "UPLOAD_REJECTED")
    assert rejected["result"] == "FAILURE"


def test_events_form_an_unbroken_hash_chain(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Chain case")
    upload_document(client, token, case["id"])

    report = client.get("/api/v1/audit/verify", headers=auth(login(client, "admin"))).json()
    assert report["intact"] is True
    assert report["events_checked"] >= 3
    assert report["broken_at_index"] is None
    assert len(report["head_hash"]) == 64


def test_each_event_links_to_its_predecessor(client, db_session):
    from app.models import GENESIS_HASH, AuditEvent

    token = login(client, "investigator")
    case = create_case(client, token, "Linkage case")
    upload_document(client, token, case["id"])

    events = (
        db_session.query(AuditEvent)
        .order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
        .all()
    )
    assert events[0].previous_event_hash == GENESIS_HASH
    for previous, current in zip(events, events[1:]):
        assert current.previous_event_hash == previous.event_hash


def test_editing_a_historical_event_breaks_verification(client, db_session):
    """Tamper-evidence: a silent edit in the database is detected."""
    from app.models import AuditEvent

    token = login(client, "investigator")
    create_case(client, token, "Tamper the log")
    upload_document(client, token, create_case(client, token, "Second case")["id"])

    victim = (
        db_session.query(AuditEvent)
        .order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
        .first()
    )
    victim.event_metadata = {**victim.event_metadata, "case_number": "NV-1999-000001"}
    db_session.commit()

    report = client.get("/api/v1/audit/verify", headers=auth(login(client, "admin"))).json()
    assert report["intact"] is False
    assert report["broken_at_index"] == 0
    assert report["broken_event_id"] == str(victim.id)


def test_deleting_an_event_breaks_verification(client, db_session):
    from app.models import AuditEvent

    token = login(client, "investigator")
    create_case(client, token, "Case one")
    create_case(client, token, "Case two")
    create_case(client, token, "Case three")

    events = (
        db_session.query(AuditEvent)
        .order_by(AuditEvent.timestamp.asc(), AuditEvent.id.asc())
        .all()
    )
    db_session.delete(events[1])
    db_session.commit()

    report = client.get("/api/v1/audit/verify", headers=auth(login(client, "admin"))).json()
    assert report["intact"] is False
    assert "Broken link" in report["detail"]


def test_the_same_event_always_hashes_to_the_same_value():
    """Determinism: dict ordering must not change the hash."""
    from datetime import datetime, timezone

    from app.services.audit_service import compute_event_hash

    timestamp = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
    common = {
        "actor_id": None,
        "case_id": None,
        "entity_type": "case",
        "entity_id": "abc",
        "action": "CASE_CREATED",
        "result": "SUCCESS",
        "timestamp": timestamp,
        "previous_event_hash": "0" * 64,
    }

    first = compute_event_hash(**common, metadata={"a": 1, "b": 2})
    second = compute_event_hash(**common, metadata={"b": 2, "a": 1})
    different = compute_event_hash(**common, metadata={"a": 1, "b": 3})

    assert first == second
    assert first != different
    assert len(first) == 64


def test_the_system_audit_log_is_restricted_to_oversight_roles(client):
    assert client.get(
        "/api/v1/audit/events", headers=auth(login(client, "investigator"))
    ).status_code == 403
    assert client.get(
        "/api/v1/audit/events", headers=auth(login(client, "auditor"))
    ).status_code == 200
    assert client.get(
        "/api/v1/audit/verify", headers=auth(login(client, "admin"))
    ).status_code == 200


def test_case_audit_is_scoped_to_case_members(client):
    owner_token = login(client, "investigator")
    case = create_case(client, owner_token, "Private audit trail")

    assert client.get(
        f"/api/v1/cases/{case['id']}/audit", headers=auth(login(client, "investigator2"))
    ).status_code == 404
