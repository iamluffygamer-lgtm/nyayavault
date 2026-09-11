import pytest
from tests.conftest import auth, login

def test_non_admin_cannot_update_department_or_user(client, db_session, seeded):
    investigator_token = login(client, "investigator")
    
    dept_id = str(seeded["users"]["investigator"].department_id)
    resp = client.patch(f"/api/v1/departments/{dept_id}", headers=auth(investigator_token), json={"name": "Hacked Name"})
    print("PATCH DEPT ERROR:", resp.json())
    assert resp.status_code == 403

    user_id = str(seeded["users"]["forensic"].id)
    resp = client.patch(f"/api/v1/users/{user_id}", headers=auth(investigator_token), json={"is_active": False})
    print("PATCH USER ERROR:", resp.json())
    assert resp.status_code == 403

def test_admin_can_update_department(client, db_session, seeded):
    admin_token = login(client, "admin")
    
    dept_id = str(seeded["users"]["investigator"].department_id)
    resp = client.patch(f"/api/v1/departments/{dept_id}", headers=auth(admin_token), json={"name": "New Awesome Unit"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Awesome Unit"

def test_deactivated_user_cannot_make_requests(client, db_session, seeded):
    admin_token = login(client, "admin")
    investigator_token = login(client, "investigator")
    
    resp = client.get("/api/v1/auth/me", headers=auth(investigator_token))
    assert resp.status_code == 200
    
    user_id = str(seeded["users"]["investigator"].id)
    
    patch_resp = client.patch(f"/api/v1/users/{user_id}", headers=auth(admin_token), json={"is_active": False})
    print("DEACTIVATE USER:", patch_resp.json())
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False
    
    resp = client.get("/api/v1/auth/me", headers=auth(investigator_token))
    assert resp.status_code == 401

def test_department_creation_calculates_path(client, db_session, seeded):
    admin_token = login(client, "admin")
    
    resp = client.get("/api/v1/departments", headers=auth(admin_token))
    assert resp.status_code == 200
    depts = resp.json()
    root = next(d for d in depts if d["path"].count("/") == 2)
    
    child_resp = client.post(
        "/api/v1/departments", 
        headers=auth(admin_token), 
        json={"name": "Test Child Dept", "org_type": "STATE", "parent_id": root["id"], "description": ""}
    )
    print("CREATE DEPT:", child_resp.json())
    assert child_resp.status_code == 201
    child = child_resp.json()
    
    expected_path = f"{root['path']}{child['id']}/"
    assert child["path"] == expected_path
