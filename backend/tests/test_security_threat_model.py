import pytest
from tests.conftest import auth, login, create_case, upload_document, pdf_bytes

def test_authorization_read_access_cannot_upload_or_transfer(client, db_session, seeded):
    # 1. Authorization edge cases: case member with READ access cannot upload a new document version or transfer evidence
    owner_token = login(client, "investigator")
    case = create_case(client, owner_token, "Joint investigation")

    forensic_id = str(seeded["users"]["forensic"].id)
    reader_token = login(client, "forensic")

    assigned = client.post(
        f"/api/v1/cases/{case['id']}/members",
        headers=auth(owner_token),
        json={"user_id": forensic_id, "access_level": "READ"},
    )
    assert assigned.status_code == 201

    # Try to upload a document as READ member
    files = {"file": ("test.pdf", pdf_bytes(), "application/pdf")}
    upload_resp = client.post(
        f"/api/v1/cases/{case['id']}/documents",
        headers=auth(reader_token),
        files=files,
        data={"title": "Test Title"}
    )
    assert upload_resp.status_code == 403

    # To test transfer, owner uploads document and creates evidence
    import time
    
    files = {"file": ("test.pdf", pdf_bytes(f"NyayaVault test document {time.time()}"), "application/pdf")}
    doc_resp = client.post(f"/api/v1/cases/{case['id']}/documents", headers=auth(owner_token), files=files, data={"title": "Test Title"})
    doc = doc_resp.json()

    ev_resp = client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        headers=auth(owner_token),
        json={
            "title": "Weapon",
            "evidence_type": "PHYSICAL",
            "source_document_id": doc["id"]
        }
    )
    assert ev_resp.status_code == 201
    ev_id = ev_resp.json()["id"]

    # Try to transfer evidence as READ member
    transfer_resp = client.post(
        f"/api/v1/evidence/{ev_id}/transfers",
        headers=auth(reader_token),
        json={"to_user_id": str(seeded["users"]["legal"].id), "reason": "Test transfer"}
    )
    assert transfer_resp.status_code == 403


def test_user_with_no_assignment_gets_404_on_case_scoped_endpoints(client):
    owner_token = login(client, "investigator")
    case = create_case(client, owner_token, "Secret Case")
    
    import time
    
    files = {"file": ("test.pdf", pdf_bytes(f"NyayaVault test document {time.time()}"), "application/pdf")}
    doc_resp = client.post(f"/api/v1/cases/{case['id']}/documents", headers=auth(owner_token), files=files, data={"title": "Test Title"})
    doc = doc_resp.json()
    doc_id = doc["id"]
    version_id = doc["current_version"]
    
    ev_resp = client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        headers=auth(owner_token),
        json={"title": "Weapon", "evidence_type": "PHYSICAL"}
    )
    ev_id = ev_resp.json()["id"]

    # unassigned user
    unauth_token = login(client, "investigator2")
    
    endpoints = [
        # Base case
        ("GET", f"/api/v1/cases/{case['id']}"),
        ("GET", f"/api/v1/cases/{case['id']}/timeline"),
        # Documents
        ("GET", f"/api/v1/cases/{case['id']}/documents"),
        ("GET", f"/api/v1/documents/{doc_id}"),
        ("GET", f"/api/v1/documents/{doc_id}/versions/{version_id}/download"),
        ("GET", f"/api/v1/documents/{doc_id}/verify"),
        ("GET", f"/api/v1/documents/{doc_id}/versions/{version_id}/verify-chain"),
        ("GET", f"/api/v1/documents/{doc_id}/versions/{version_id}/anchor"),
        # Evidence
        ("GET", f"/api/v1/cases/{case['id']}/evidence"),
        ("GET", f"/api/v1/evidence/{ev_id}"),
        ("GET", f"/api/v1/evidence/{ev_id}/timeline"),
        ("GET", f"/api/v1/evidence/{ev_id}/transfers"),
    ]
    
    for method, url in endpoints:
        resp = client.request(method, url, headers=auth(unauth_token))
        assert resp.status_code == 404, f"{method} {url} returned {resp.status_code} instead of 404"


def test_non_admin_auditor_cannot_reach_audit_events(client):
    # a non-ADMIN/AUDITOR user cannot reach GET /audit/events
    investigator_token = login(client, "investigator")
    
    resp_events = client.get("/api/v1/audit/events", headers=auth(investigator_token))
    assert resp_events.status_code == 403
    
    resp_verify = client.get("/api/v1/audit/verify", headers=auth(investigator_token))
    assert resp_verify.status_code == 403
    
    # But admin CAN reach it
    admin_token = login(client, "admin")
    resp_admin = client.get("/api/v1/audit/events", headers=auth(admin_token))
    assert resp_admin.status_code == 200


def test_blockchain_failure_does_not_break_upload(client, db_session, monkeypatch):
    from app.config import get_settings
    import os
    
    # 2. Blockchain failure handling
    # point blockchain_rpc_url at a closed port
    monkeypatch.setattr(get_settings(), "blockchain_rpc_url", "http://127.0.0.1:9999")
    
    # Also mock is_connected so it returns False immediately without timing out
    from web3 import Web3
    monkeypatch.setattr(Web3, "is_connected", lambda self: False)
    
    # Mock SessionLocal so the background task uses the test db
    import app.database
    monkeypatch.setattr(app.database, "SessionLocal", lambda: db_session)
    
    
    owner_token = login(client, "investigator")
    case = create_case(client, owner_token, "No Blockchain Case")
    
    import time
    
    files = {"file": ("test.pdf", pdf_bytes(f"NyayaVault test document {time.time()}"), "application/pdf")}
    doc_resp = client.post(f"/api/v1/cases/{case['id']}/documents", headers=auth(owner_token), files=files, data={"title": "Test Title"})
    assert doc_resp.status_code == 201
    doc = doc_resp.json()
    
    doc_id = doc["id"]
    version_id = doc["current_version"]
    
    # Confirm version is still downloadable
    download_resp = client.get(f"/api/v1/documents/{doc_id}/download?version={version_id}", headers=auth(owner_token))
    assert download_resp.status_code == 200
    
    # Confirm hash verifiable
    verify_resp = client.get(f"/api/v1/documents/{doc_id}/verify", headers=auth(owner_token))
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True
    
    # Confirm anchor status shows FAILED
    anchor_resp = client.get(f"/api/v1/documents/{doc_id}/versions/{version_id}/anchor", headers=auth(owner_token))
    assert anchor_resp.status_code == 200
    assert anchor_resp.json()["status"] == "FAILED"

def test_tamper_and_custody_integrity_mismatch(client, db_session, storage, seeded):
    # 3. Tamper + custody integrity together
    owner_token = login(client, "investigator")
    case = create_case(client, owner_token, "Tampered Case")
    
    import time
    
    files = {"file": ("test.pdf", pdf_bytes(f"NyayaVault test document {time.time()}"), "application/pdf")}
    doc_resp = client.post(f"/api/v1/cases/{case['id']}/documents", headers=auth(owner_token), files=files, data={"title": "Test Title"})
    doc = doc_resp.json()
    doc_id = doc["id"]
    version_id = doc["current_version"]
    
    # Force anchor it synchronously since test background tasks are unreliable across db sessions
    from app.services.blockchain_service import anchor_document_hash
    from app.models.document import DocumentVersion
    from app.models.blockchain import AnchorStatus
    from sqlalchemy import select
    import uuid
    version = db_session.execute(select(DocumentVersion).where(DocumentVersion.document_id == uuid.UUID(doc_id), DocumentVersion.version_number == version_id)).scalar_one()
    res = anchor_document_hash(version.sha256_hash, str(case["id"]), doc_id, version_id)
    print("ANCHOR RESULT:", res.status, res.error)
    if res.status == "ANCHORED":
        version.blockchain_anchor.status = AnchorStatus.ANCHORED
        version.blockchain_anchor.tx_hash = res.tx_hash
        version.blockchain_anchor.block_number = res.block_number
        db_session.commit()

    # Create evidence
    ev_resp = client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        headers=auth(owner_token),
        json={
            "title": "Suspect File",
            "evidence_type": "DIGITAL",
            "source_document_id": doc_id
        }
    )
    assert ev_resp.status_code == 201
    ev_id = ev_resp.json()["id"]
    
    # Tamper with storage directly (we use the InMemoryStorage test double)
    # The document object key is something like "case_id/doc_id/version_id"
    # Wait, how does the document get its object key?
    # Let's fetch the document version object key from DB directly, or we can just iterate over all objects in `storage._objects` and tamper the only one there.
    # Because it's InMemoryStorage!
    assert len(storage._objects) == 1
    object_key = list(storage._objects.keys())[0]
    original_bytes = storage._objects[object_key]
    storage._objects[object_key] = original_bytes + b"CORRUPTED"
    
    # Confirm GET /documents/{id}/verify detects it
    verify_resp = client.get(f"/api/v1/documents/{doc_id}/verify", headers=auth(owner_token))
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["verified"] is False
    
    # Confirm GET /documents/{id}/versions/{version}/verify-chain detects it
    chain_resp = client.get(f"/api/v1/documents/{doc_id}/versions/{version_id}/verify-chain", headers=auth(owner_token))
    assert chain_resp.status_code == 200
    chain_data = chain_resp.json()
    assert chain_data["status"] == "MISMATCH"
    
    # Confirm evidence verification detects it
    ev_verify_resp = client.get(f"/api/v1/evidence/{ev_id}/verify", headers=auth(owner_token))
    assert ev_verify_resp.status_code == 200
    ev_verify_data = ev_verify_resp.json()
    assert ev_verify_data["is_intact"] is False
