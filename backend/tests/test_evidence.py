import pytest
from fastapi.testclient import TestClient

from app.models.evidence import EvidenceStatus
from tests.conftest import login, auth


def create_case(client: TestClient, token: str, title: str = "Test case") -> dict:
    response = client.post(
        "/api/v1/cases",
        headers=auth(token),
        json={"title": title, "description": "Created by the test suite."},
    )
    assert response.status_code == 201
    return response.json()

def test_evidence_requires_contributor_access(client: TestClient):
    # Investigator A creates case
    token_a = login(client, "investigator")
    case = create_case(client, token_a)

    # Investigator B tries to create evidence in Case A
    token_b = login(client, "investigator2")
    response = client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        headers=auth(token_b),
        json={
            "case_id": case["id"],
            "title": "Stolen laptop",
            "evidence_type": "physical",
            "storage_location": "Locker A1",
        }
    )
    assert response.status_code == 404  # Fails closed, case not found

def test_evidence_role_permissions(client: TestClient):
    token_a = login(client, "investigator")
    case = create_case(client, token_a)
    
    # 1. Investigator creates evidence
    response = client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        headers=auth(token_a),
        json={
            "case_id": case["id"],
            "title": "Stolen laptop",
            "evidence_type": "physical",
            "storage_location": "Locker A1",
        }
    )
    assert response.status_code == 201
    evidence_id = response.json()["id"]

    # 2. Auditor can view it but not seal it
    token_auditor = login(client, "auditor")
    assert client.get(f"/api/v1/cases/{case['id']}/evidence", headers=auth(token_auditor)).status_code == 200
    assert client.post(f"/api/v1/evidence/{evidence_id}/seal", headers=auth(token_auditor)).status_code == 403

    # 3. Investigator seals it
    response = client.post(f"/api/v1/evidence/{evidence_id}/seal", headers=auth(token_a))
    assert response.status_code == 200, response.text

    # 4. Forensic officer tries to submit it (disallowed)
    # Give forensic officer contribute access first via assignment
    token_admin = login(client, "admin")
    client.post(
        f"/api/v1/cases/{case['id']}/members",
        headers=auth(token_admin),
        json={"user_id": client.get("/api/v1/auth/me", headers=auth(login(client, "forensic"))).json()["id"], "access_level": "CONTRIBUTE"}
    )
    token_forensic = login(client, "forensic")
    # Forensic can't submit to court
    assert client.post(f"/api/v1/evidence/{evidence_id}/submit", headers=auth(token_forensic)).status_code == 403
    
    # But Forensic CAN analyze. First transfer to themselves.
    forensic_id = client.get("/api/v1/auth/me", headers=auth(token_forensic)).json()["id"]
    
    # Wait, the investigator has to initiate the transfer! 
    # Forensic officer can't just take it.
    assert client.post(f"/api/v1/evidence/{evidence_id}/transfers", headers=auth(token_a), json={"to_user_id": forensic_id, "reason": "Analysis"}).status_code == 201
    
    # Forensic accepts it
    transfer_id = client.get(f"/api/v1/evidence/{evidence_id}/transfers", headers=auth(token_forensic)).json()[-1]["id"]
    assert client.post(f"/api/v1/transfers/{transfer_id}/accept", headers=auth(token_forensic)).status_code == 200
    
    # Check what the DB says about current_custodian
    ev_detail = client.get(f"/api/v1/evidence/{evidence_id}", headers=auth(token_forensic)).json()
    print("AFTER ACCEPT TRANSFER: evidence detail =", ev_detail)
    
    # Then Forensic can start analysis
    resp_start = client.post(f"/api/v1/evidence/{evidence_id}/start-analysis", headers=auth(token_forensic))
    assert resp_start.status_code == 200, resp_start.text
    
    # Forensic completes analysis
    resp_complete = client.post(f"/api/v1/evidence/{evidence_id}/complete-analysis", headers=auth(token_forensic))
    assert resp_complete.status_code == 200, resp_complete.text
    
    # Investigator can submit it
    # Wait, the current custodian is Forensic! Investigator cannot submit it unless it's transferred back!
    # Investigator requests it back (initiate transfer is done by Forensic!)
    investigator_id = client.get("/api/v1/auth/me", headers=auth(token_a)).json()["id"]
    client.post(f"/api/v1/evidence/{evidence_id}/transfers", headers=auth(token_forensic), json={"to_user_id": investigator_id, "reason": "Return"}).status_code == 201
    
    # Investigator accepts it
    transfer_id2 = client.get(f"/api/v1/evidence/{evidence_id}/transfers", headers=auth(token_a)).json()[-1]["id"]
    client.post(f"/api/v1/transfers/{transfer_id2}/accept", headers=auth(token_a)).status_code == 200

    # Investigator submits it to court
    assert client.post(f"/api/v1/evidence/{evidence_id}/submit", headers=auth(token_a)).status_code == 200
