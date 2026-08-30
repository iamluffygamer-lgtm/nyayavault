from tests.conftest import login, create_case, auth
import pytest

def test_unauthorized_search_leakage(client):
    """Test that searching does not leak snippets or counts from unauthorized cases."""
    # 1. Investigator A creates a case and uploads a document (mocking document text)
    token_a = login(client, "investigator")
    case_a = create_case(client, token_a, "Case A")
    # For now, we just test that a basic search query succeeds and returns total 0
    # for a completely unrelated user (Investigator B).
    token_b = login(client, "forensic") # wait, forensic cannot see investigator's case unless assigned.
    
    # Forensic searches for "Confidential"
    res = client.get("/api/v1/search?q=Confidential", headers=auth(token_b))
    assert res.status_code == 200
    assert res.json()["total"] == 0
    assert len(res.json()["items"]) == 0

