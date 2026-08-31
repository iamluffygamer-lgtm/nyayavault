from tests.conftest import login, create_case, auth, pdf_bytes
import pytest
import uuid

def test_search_and_ocr_authorization(client):
    """Test that searching and OCR enforce authorization."""
    # 1. Investigator A creates a case and uploads a document
    token_a = login(client, "investigator")
    case_a = create_case(client, token_a, "Top Secret Case")
    
    # Upload document
    resp = client.post(
        f"/api/v1/cases/{case_a['id']}/documents",
        headers=auth(token_a),
        files={"file": ("secret.pdf", pdf_bytes("This is a secret about corruption"), "application/pdf")},
        data={"title": "Secret Document"}
    )
    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    # 2. Investigator B (no access to Case A)
    token_b = login(client, "investigator2")
    
    # Search should return 0 results for B
    search_b = client.get("/api/v1/search?q=corruption", headers=auth(token_b))
    assert search_b.status_code == 200
    assert search_b.json()["total"] == 0
    
    # 3. OCR Triggering
    # B cannot trigger OCR for A's document
    ocr_b = client.post(f"/api/v1/documents/{doc_id}/versions/1/ocr", headers=auth(token_b))
    assert ocr_b.status_code == 403 or ocr_b.status_code == 404 # 404 because not authorized to even know it exists
    
    # A can trigger OCR
    ocr_a = client.post(f"/api/v1/documents/{doc_id}/versions/1/ocr", headers=auth(token_a))
    assert ocr_a.status_code == 200 or ocr_a.status_code == 202

