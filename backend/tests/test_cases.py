"""Required coverage: (3) case creation, (4) unauthorized case access,
(5) authorized case access."""

from __future__ import annotations

import re

from tests.conftest import auth, create_case, login


def test_create_case_generates_a_unique_sequential_number(client):
    token = login(client, "investigator")

    first = create_case(client, token, "Vehicle theft — MG Road")
    second = create_case(client, token, "Cheque fraud — Sector 12")

    assert re.fullmatch(r"NV-\d{4}-\d{6}", first["case_number"]), first["case_number"]
    assert first["case_number"] != second["case_number"]
    assert first["status"] == "OPEN"
    assert first["creator"]["username"] == "investigator"
    assert first["document_count"] == 0
    assert first["can_upload"] is True


def test_case_creation_requires_an_authorised_role(client):
    """A FORENSIC_OFFICER may upload to cases but may not open them."""
    response = client.post(
        "/api/v1/cases",
        headers=auth(login(client, "forensic")),
        json={"title": "Unauthorised case"},
    )
    assert response.status_code == 403


def test_case_creation_requires_authentication(client):
    assert client.post("/api/v1/cases", json={"title": "Anonymous case"}).status_code == 401


def test_case_creation_validates_input(client):
    token = login(client, "investigator")
    assert client.post("/api/v1/cases", headers=auth(token), json={"title": "ab"}).status_code == 422
    assert client.post("/api/v1/cases", headers=auth(token), json={}).status_code == 422


def test_creator_has_authorised_access_to_their_case(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Authorised access case")

    response = client.get(f"/api/v1/cases/{case['id']}", headers=auth(token))
    assert response.status_code == 200
    assert response.json()["case_number"] == case["case_number"]
    assert response.json()["access_level"] == "MANAGE"


def test_unauthorised_user_cannot_read_another_officers_case(client):
    owner_token = login(client, "investigator")
    case = create_case(client, owner_token, "Confidential operation")

    other_token = login(client, "investigator2")
    response = client.get(f"/api/v1/cases/{case['id']}", headers=auth(other_token))

    # 404 rather than 403: the API must not confirm that the case exists.
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_unauthorised_user_cannot_see_the_case_in_listings(client):
    owner_token = login(client, "investigator")
    create_case(client, owner_token, "Hidden case")

    listing = client.get("/api/v1/cases", headers=auth(login(client, "investigator2")))
    assert listing.status_code == 200
    assert listing.json()["total"] == 0
    assert listing.json()["items"] == []


def test_assignment_grants_case_level_access(client, seeded):
    owner_token = login(client, "investigator")
    case = create_case(client, owner_token, "Joint investigation")

    forensic_id = str(seeded["users"]["forensic"].id)
    other_token = login(client, "forensic")

    assert client.get(f"/api/v1/cases/{case['id']}", headers=auth(other_token)).status_code == 404

    assigned = client.post(
        f"/api/v1/cases/{case['id']}/members",
        headers=auth(owner_token),
        json={"user_id": forensic_id, "access_level": "CONTRIBUTE"},
    )
    assert assigned.status_code == 201, assigned.text

    now_visible = client.get(f"/api/v1/cases/{case['id']}", headers=auth(other_token))
    assert now_visible.status_code == 200
    assert now_visible.json()["access_level"] == "CONTRIBUTE"
    assert now_visible.json()["can_upload"] is True


def test_admin_sees_every_case_and_auditor_is_read_only(client):
    create_case(client, login(client, "investigator"), "Case A")
    create_case(client, login(client, "legal"), "Case B")

    admin_listing = client.get("/api/v1/cases", headers=auth(login(client, "admin")))
    assert admin_listing.json()["total"] == 2

    auditor_token = login(client, "auditor")
    auditor_listing = client.get("/api/v1/cases", headers=auth(auditor_token))
    assert auditor_listing.json()["total"] == 2

    case_id = auditor_listing.json()["items"][0]["id"]
    detail = client.get(f"/api/v1/cases/{case_id}", headers=auth(auditor_token))
    assert detail.json()["access_level"] == "READ"
    assert detail.json()["can_upload"] is False

    # Read-only means read-only, even with full visibility.
    assert client.post(
        "/api/v1/cases", headers=auth(auditor_token), json={"title": "Auditor case"}
    ).status_code == 403


def test_case_search_is_scoped_and_escapes_wildcards(client):
    token = login(client, "investigator")
    create_case(client, token, "Narcotics seizure at port")
    create_case(client, token, "Cyber fraud helpline complaint")

    hits = client.get("/api/v1/cases?search=narcotics", headers=auth(token)).json()
    assert hits["total"] == 1
    assert "Narcotics" in hits["items"][0]["title"]

    # A bare "%" must be treated as a literal, not as "match everything".
    wildcard = client.get("/api/v1/cases?search=%25", headers=auth(token)).json()
    assert wildcard["total"] == 0


def test_status_filter_and_transition(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Status transition case")

    updated = client.patch(
        f"/api/v1/cases/{case['id']}/status",
        headers=auth(token),
        json={"status": "UNDER_INVESTIGATION"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "UNDER_INVESTIGATION"

    filtered = client.get(
        "/api/v1/cases?status=UNDER_INVESTIGATION", headers=auth(token)
    ).json()
    assert filtered["total"] == 1


def test_archived_cases_cannot_be_reopened(client):
    token = login(client, "investigator")
    case = create_case(client, token, "Archived case")

    client.patch(
        f"/api/v1/cases/{case['id']}/status", headers=auth(token), json={"status": "ARCHIVED"}
    )
    reopened = client.patch(
        f"/api/v1/cases/{case['id']}/status", headers=auth(token), json={"status": "OPEN"}
    )
    assert reopened.status_code == 403


def test_statistics_only_count_visible_cases(client):
    create_case(client, login(client, "investigator"), "Visible to owner")

    other = client.get("/api/v1/cases/statistics", headers=auth(login(client, "investigator2")))
    assert other.json() == {
        "total_cases": 0,
        "active_cases": 0,
        "closed_cases": 0,
        "total_documents": 0,
    }

    admin = client.get("/api/v1/cases/statistics", headers=auth(login(client, "admin")))
    assert admin.json()["total_cases"] == 1
    assert admin.json()["active_cases"] == 1


def test_unknown_case_id_is_a_404(client):
    token = login(client, "investigator")
    missing = "00000000-0000-4000-8000-000000000000"
    assert client.get(f"/api/v1/cases/{missing}", headers=auth(token)).status_code == 404
