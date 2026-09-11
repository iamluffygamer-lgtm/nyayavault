"""Required coverage: (6) document upload, (7) SHA-256 generation,
(8) document version creation, (10) integrity verification."""

from __future__ import annotations

import hashlib
import uuid

from tests.conftest import (
    auth,
    create_case,
    docx_bytes,
    login,
    pdf_bytes,
    png_bytes,
    upload_document,
)


def test_upload_creates_document_and_version_one(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Upload case")

    response = upload_document(client, token, case["id"])
    assert response.status_code == 201, response.text

    body = response.json()
    assert body["title"] == "Charge Sheet"
    assert body["document_type"] == "CHARGE_SHEET"
    assert body["current_version"] == 1
    assert len(body["versions"]) == 1

    version = body["versions"][0]
    assert version["version_number"] == 1
    assert version["uploader"]["username"] == "investigator"
    # Storage layout must never be exposed to a client.
    assert "object_key" not in version


def test_sha256_matches_the_bytes_that_were_uploaded(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Hashing case")
    payload = pdf_bytes("evidence-payload-for-hashing")
    expected = hashlib.sha256(payload).hexdigest()

    response = upload_document(client, token, case["id"], content=payload)
    version = response.json()["versions"][0]

    assert version["sha256_hash"] == expected
    assert len(version["sha256_hash"]) == 64
    assert version["file_size"] == len(payload)


def test_stored_bytes_are_byte_identical_on_download(client, storage):
    token = login(client, "investigator")
    case = create_case(client, token, "Round-trip case")
    payload = pdf_bytes("round-trip-fidelity")

    document = upload_document(client, token, case["id"], content=payload).json()

    download = client.get(f"/api/v1/documents/{document['id']}/download", headers=auth(token))
    assert download.status_code == 200
    assert download.content == payload
    assert download.headers["x-document-sha256"] == hashlib.sha256(payload).hexdigest()
    assert download.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in download.headers["content-disposition"]


def test_new_version_never_overwrites_the_previous_one(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Versioning case")

    v1_bytes = pdf_bytes("charge sheet — first draft")
    v2_bytes = pdf_bytes("charge sheet — revised after forensic report")

    document = upload_document(client, token, case["id"], content=v1_bytes).json()
    document_id = document["id"]

    second = client.post(
        f"/api/v1/documents/{document_id}/versions",
        headers=auth(token),
        files={"file": ("chargesheet_v2.pdf", v2_bytes, "application/pdf")},
        data={"change_reason": "Revised after receiving the forensic report"},
    )
    assert second.status_code == 201, second.text
    assert second.json()["version_number"] == 2

    versions = client.get(
        f"/api/v1/documents/{document_id}/versions", headers=auth(token)
    ).json()
    assert [v["version_number"] for v in versions] == [1, 2]

    # v1's hash is untouched and still corresponds to the original bytes.
    assert versions[0]["sha256_hash"] == hashlib.sha256(v1_bytes).hexdigest()
    assert versions[1]["sha256_hash"] == hashlib.sha256(v2_bytes).hexdigest()
    assert versions[0]["sha256_hash"] != versions[1]["sha256_hash"]

    # Both sets of bytes remain independently retrievable.
    v1_download = client.get(
        f"/api/v1/documents/{document_id}/download?version=1", headers=auth(token)
    )
    assert v1_download.content == v1_bytes


def test_a_new_version_requires_a_stated_reason(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Change reason case")
    document = upload_document(client, token, case["id"]).json()

    response = client.post(
        f"/api/v1/documents/{document['id']}/versions",
        headers=auth(token),
        files={"file": ("v2.pdf", pdf_bytes("different content"), "application/pdf")},
        data={},
    )
    assert response.status_code == 422


def test_identical_re_upload_is_rejected_rather_than_duplicated(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Duplicate case")
    payload = pdf_bytes("identical bytes")
    document = upload_document(client, token, case["id"], content=payload).json()

    duplicate = client.post(
        f"/api/v1/documents/{document['id']}/versions",
        headers=auth(token),
        files={"file": ("same.pdf", payload, "application/pdf")},
        data={"change_reason": "Accidental resubmission"},
    )
    assert duplicate.status_code == 409
    assert client.get(
        f"/api/v1/documents/{document['id']}/versions", headers=auth(token)
    ).json().__len__() == 1


def test_integrity_verification_passes_for_untouched_storage(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Integrity case")
    document = upload_document(client, token, case["id"]).json()

    report = client.get(f"/api/v1/documents/{document['id']}/verify", headers=auth(token))
    assert report.status_code == 200

    body = report.json()
    assert body["verified"] is True
    assert body["algorithm"] == "SHA-256"
    assert body["results"][0]["expected_sha256"] == body["results"][0]["computed_sha256"]


def test_integrity_verification_detects_tampering_in_object_storage(client, storage, db_session):
    """The point of the whole feature: bytes changed behind the API are caught."""
    from app.models import DocumentVersion

    token = login(client, "investigator")
    case = create_case(client, token, "Tamper case")
    document = upload_document(client, token, case["id"]).json()

    version = db_session.query(DocumentVersion).filter_by(
        document_id=uuid.UUID(document["id"]), version_number=1
    ).one()

    # Modify the stored object directly, bypassing the API entirely.
    storage.corrupt(version.object_key, pdf_bytes("SUBSTITUTED EVIDENCE"))

    report = client.get(f"/api/v1/documents/{document['id']}/verify", headers=auth(token)).json()
    assert report["verified"] is False
    result = report["results"][0]
    assert result["verified"] is False
    assert result["computed_sha256"] != result["expected_sha256"]
    assert "MISMATCH" in result["detail"]


def test_upload_rejects_a_disallowed_file_type(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Bad type case")

    response = upload_document(
        client,
        token,
        case["id"],
        filename="payload.exe",
        content=b"MZ\x90\x00binary",
        content_type="application/octet-stream",
    )
    assert response.status_code == 415


def test_upload_rejects_content_that_contradicts_its_extension(client):
    """A shell script renamed to .pdf must not get through."""
    token = login(client, "investigator")
    case = create_case(client, token, "Spoofed extension case")

    response = upload_document(
        client,
        token,
        case["id"],
        filename="innocent.pdf",
        content=b"#!/bin/sh\nrm -rf /\n",
        content_type="application/pdf",
    )
    assert response.status_code == 415
    assert "does not match" in response.json()["error"]["message"].lower()


def test_upload_rejects_a_zip_masquerading_as_a_docx(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Fake docx case")

    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("malware.exe", "not a word document")

    response = upload_document(
        client,
        token,
        case["id"],
        filename="report.docx",
        content=buffer.getvalue(),
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )
    assert response.status_code == 415


def test_a_real_docx_and_png_are_accepted(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Valid formats case")

    docx = upload_document(
        client,
        token,
        case["id"],
        filename="statement.docx",
        content=docx_bytes(),
        title="Witness Statement",
        document_type="WITNESS_STATEMENT",
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )
    assert docx.status_code == 201, docx.text

    png = upload_document(
        client,
        token,
        case["id"],
        filename="scene.png",
        content=png_bytes(),
        title="Scene photograph",
        document_type="EVIDENCE_PHOTO",
        content_type="image/png",
    )
    assert png.status_code == 201, png.text


def test_upload_rejects_an_empty_file(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Empty file case")

    response = upload_document(client, token, case["id"], content=b"")
    assert response.status_code in (415, 422)


def test_upload_rejects_a_file_over_the_size_limit(client, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_bytes", 2048, raising=False)

    token = login(client, "investigator")
    case = create_case(client, token, "Oversize case")

    response = upload_document(client, token, case["id"], content=pdf_bytes("x" * 4096))
    assert response.status_code == 413


def test_path_traversal_in_the_filename_is_neutralised(client, storage, db_session):
    """The client cannot steer where the object lands."""
    from app.models import DocumentVersion

    token = login(client, "investigator")
    case = create_case(client, token, "Traversal case")

    response = upload_document(
        client, token, case["id"], filename="../../../../etc/passwd.pdf"
    )
    assert response.status_code == 201

    version = db_session.query(DocumentVersion).filter_by(
        document_id=uuid.UUID(response.json()["id"])
    ).one()
    assert ".." not in version.object_key
    assert version.object_key.startswith(f"cases/{case['id']}/documents/")
    assert "/etc/" not in version.object_key
    # Directory components are stripped entirely, leaving only a basename.
    assert version.original_filename == "passwd.pdf"
    assert "/" not in version.original_filename


def test_upload_requires_write_access_to_the_case(client, seeded):
    owner_token = login(client, "investigator")
    case = create_case(client, owner_token, "Access controlled case")

    # Not a member at all -> the case does not exist as far as they know.
    outsider = upload_document(client, login(client, "investigator2"), case["id"])
    assert outsider.status_code == 404

    # Assigned READ-only -> visible, but uploads are refused.
    client.post(
        f"/api/v1/cases/{case['id']}/members",
        headers=auth(owner_token),
        json={"user_id": str(seeded["users"]["forensic"].id), "access_level": "READ"},
    )
    read_only = upload_document(client, login(client, "forensic"), case["id"])
    assert read_only.status_code == 403


def test_uploads_to_a_closed_case_are_refused(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Closed case")
    client.patch(
        f"/api/v1/cases/{case['id']}/status", headers=auth(token), json={"status": "CLOSED"}
    )

    response = upload_document(client, token, case["id"])
    assert response.status_code == 403


def test_auditor_may_read_documents_but_not_upload(client):
    owner_token = login(client, "investigator")
    case = create_case(client, owner_token, "Auditor visibility case")
    upload_document(client, owner_token, case["id"])

    auditor_token = login(client, "auditor")
    listing = client.get(
        f"/api/v1/cases/{case['id']}/documents", headers=auth(auditor_token)
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["latest_sha256"]

    assert upload_document(client, auditor_token, case["id"]).status_code == 403


def test_document_list_carries_current_version_metadata(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Listing case")
    payload = pdf_bytes("listed document")
    upload_document(client, token, case["id"], content=payload)

    items = client.get(f"/api/v1/cases/{case['id']}/documents", headers=auth(token)).json()
    assert items[0]["latest_sha256"] == hashlib.sha256(payload).hexdigest()
    assert items[0]["latest_file_size"] == len(payload)
    assert items[0]["current_version"] == 1


def test_demo_tamper_endpoint_returns_404_when_disabled(client, db_session, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "allow_demo_tamper", False)
    from tests.conftest import login, create_case, upload_document
    token = login(client, "admin")
    case = create_case(client, token)
    doc = upload_document(client, token, case["id"]).json()
    
    resp = client.post(
        f"/api/v1/documents/{doc['id']}/versions/{doc['current_version']}/demo-tamper",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["message"] == "Not Found"
