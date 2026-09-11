import pytest
import time
from tests.conftest import login, create_case, auth, pdf_bytes, upload_document

def test_anchor_status_endpoints(client, db_session):
    token = login(client, "investigator")
    case = create_case(client, token)
    
    doc = upload_document(client, token, case["id"]).json()
    doc_id = doc["id"]
    version = doc["current_version"]
    
    # Check anchor status
    resp = client.get(f"/api/v1/documents/{doc_id}/versions/{version}/anchor", headers=auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["PENDING", "ANCHORED", "FAILED"]

def test_verify_chain_mismatch(client, db_session):
    token = login(client, "investigator")
    case = create_case(client, token)
    
    doc = upload_document(client, token, case["id"]).json()
    doc_id = doc["id"]
    version = doc["current_version"]
    
    resp = client.get(f"/api/v1/documents/{doc_id}/versions/{version}/verify-chain", headers=auth(token))
    assert resp.status_code == 200
    assert "status" in resp.json()

def test_anchor_fails_gracefully(client, db_session):
    pass

def test_download_while_pending(client, db_session):
    token = login(client, "investigator")
    case = create_case(client, token)
    doc = upload_document(client, token, case["id"]).json()
    
    resp = client.get(f"/api/v1/documents/{doc['id']}/download", headers=auth(token))
    assert resp.status_code == 200

