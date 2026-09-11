import requests
import sys
import time

BASE_URL = "http://localhost:8000/api/v1"

def login(username, password):
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        print(f"Failed to login {username}: {resp.text}")
        sys.exit(1)
    return resp.json()["access_token"]

def get_auth(token):
    return {"Authorization": f"Bearer {token}"}

def main():
    print("Authenticating as admin...")
    admin_token = login("admin", "Admin#Passw0rd!2026")
    admin_auth = get_auth(admin_token)

    print("Fetching roles and departments...")
    roles_resp = requests.get(f"{BASE_URL}/roles", headers=admin_auth)
    roles = {r["name"]: r["id"] for r in roles_resp.json()}
    
    depts_resp = requests.get(f"{BASE_URL}/departments", headers=admin_auth)
    depts = depts_resp.json()
    
    colaba = next((d for d in depts if d["name"] == "Colaba Police Station"), None)
    cyber = next((d for d in depts if d["name"] == "Cyber Crime Cell"), None)
    legal = next((d for d in depts if d["name"] == "Prosecution Wing"), None)
    
    users_to_create = [
        ("inv_colaba", "inv_colaba@nyayavault.gov.in", "Invest#Passw0rd!26", roles["INVESTIGATOR"], colaba["id"]),
        ("forensic_lead", "forensic_lead@nyayavault.gov.in", "Forens#Passw0rd!26", roles["FORENSIC_OFFICER"], cyber["id"]),
        ("legal_adv", "legal_adv@nyayavault.gov.in", "Legal#Passw0rd!2026", roles["LEGAL_OFFICER"], legal["id"]),
    ]

    created_users = {}

    for username, email, pwd, rid, did in users_to_create:
        print(f"Ensuring user {username} exists...")
        resp = requests.post(f"{BASE_URL}/users", headers=admin_auth, json={
            "username": username,
            "email": email,
            "password": pwd,
            "role_id": rid,
            "department_id": did
        })
        if resp.status_code == 201:
            print(f"User {username} created.")
            created_users[username] = resp.json()["id"]
        elif resp.status_code == 409 and "already registered" in resp.text:
            users_list = requests.get(f"{BASE_URL}/users?limit=200", headers=admin_auth).json()["items"]
            created_users[username] = next(u["id"] for u in users_list if u["username"] == username)
            print(f"User {username} already exists (id: {created_users[username]}).")
        else:
            print(f"Error creating user {username}: {resp.text}")
            sys.exit(1)

    print("\nAuthenticating as inv_colaba...")
    inv_token = login("inv_colaba", "Invest#Passw0rd!26")
    inv_auth = get_auth(inv_token)
    
    print("Creating case...")
    case_resp = requests.post(f"{BASE_URL}/cases", headers=inv_auth, json={
        "title": "State vs. Smuggling Ring (Operation SeaBreeze)",
        "description": "Investigation into a highly organized cyber financial fraud syndicate operating a fake call center targeting elderly citizens. Seized multiple server racks and cryptographic ledgers.",
        "status": "OPEN"
    })
    if case_resp.status_code != 201:
        print(f"Failed to create case: {case_resp.text}")
        sys.exit(1)
    
    case_id = case_resp.json()["id"]
    print(f"Case created: {case_id}")

    print("Adding forensic and legal users to case...")
    for member_username in ["forensic_lead", "legal_adv"]:
        uid = created_users[member_username]
        access_level = "CONTRIBUTE" if member_username == "forensic_lead" else "READ"
        resp = requests.post(f"{BASE_URL}/cases/{case_id}/members", headers=inv_auth, json={
            "user_id": uid,
            "access_level": access_level
        })
        if resp.status_code != 201:
            print(f"Failed to add {member_username} to case: {resp.text}")

    print("Uploading FIR document...")
    fir_content = b"FIRST INFORMATION REPORT\n\nIncident: Cyber Fraud\nDate: 2026-09-10\nLocation: Colaba\nDetails: Fake call center operating from a rented commercial space."
    files = {'file': ('fir_report.txt', fir_content, 'text/plain')}
    data = {
        'title': 'FIR - Operation Phantom',
        'document_type': 'FIR',
        'description': 'Initial complaint and FIR registration based on victim testimony.'
    }
    doc_resp = requests.post(f"{BASE_URL}/cases/{case_id}/documents", headers=inv_auth, files=files, data=data)
    if doc_resp.status_code == 201:
        print("FIR Document uploaded.")
    else:
        print(f"Failed to upload document: {doc_resp.text}")

    print("Registering Evidence...")
    ev_resp = requests.post(f"{BASE_URL}/cases/{case_id}/evidence", headers=inv_auth, json={
        "title": "Dell PowerEdge Server Rack 01",
        "description": "Main database server running the spoofed VoIP system.",
        "evidence_type": "ELECTRONICS",
        "collected_at": "2026-09-09T14:30:00Z",
        "collected_location": "Colaba Office 401"
    })
    if ev_resp.status_code == 201:
        ev_id = ev_resp.json()["id"]
        print(f"Evidence registered: {ev_id}")
        
        print("Sealing Evidence...")
        seal_resp = requests.post(f"{BASE_URL}/evidence/{ev_id}/seal", headers=inv_auth)
        if seal_resp.status_code == 200:
            print("Evidence sealed.")
        else:
            print(f"Failed to seal evidence: {seal_resp.text}")
        
        print("Transferring Evidence to Forensics...")
        transfer_resp = requests.post(f"{BASE_URL}/evidence/{ev_id}/transfers", headers=inv_auth, json={
            "to_user_id": created_users["forensic_lead"],
            "purpose": "Disk image and decryption",
            "notes": "Please prioritize memory dump before power down."
        })
        if transfer_resp.status_code == 201:
            transfer_id = transfer_resp.json()["id"]
            print(f"Evidence transfer initiated: {transfer_id}")
        else:
            print(f"Failed to transfer evidence: {transfer_resp.text}")
            sys.exit(1)
    else:
        print(f"Failed to register evidence: {ev_resp.text}")
        sys.exit(1)
        
    print("\nAuthenticating as forensic_lead...")
    for_token = login("forensic_lead", "Forens#Passw0rd!26")
    for_auth = get_auth(for_token)
    
    print("Accepting Evidence Transfer...")
    accept_resp = requests.post(f"{BASE_URL}/transfers/{transfer_id}/accept", headers=for_auth)
    if accept_resp.status_code == 200:
        print("Evidence accepted.")
    else:
        print(f"Error accepting evidence: {accept_resp.text}")
    
    print("\nAuthenticating as inv_colaba again (to upload forensic report)...")
    print("Uploading Forensic Analysis Report...")
    report_content = b"FORENSIC ANALYSIS REPORT\n\nSeal: MH-CYBER-2026-001\nStatus: Intact\nFindings: Decrypted 14 TB of victim data and VoIP logs. VoIP infrastructure maps directly to the suspect's registered IP ranges."
    files2 = {'file': ('forensic_report.txt', report_content, 'text/plain')}
    data2 = {
        'title': 'Forensic Analysis - Dell Server',
        'document_type': 'FORENSIC_REPORT',
        'description': 'Memory dump and disk decryption results for Evidence MH-CYBER-2026-001.'
    }
    doc_resp2 = requests.post(f"{BASE_URL}/cases/{case_id}/documents", headers=inv_auth, files=files2, data=data2)
    if doc_resp2.status_code == 201:
        print("Forensic Document uploaded.")
    else:
        print(f"Failed to upload forensic document: {doc_resp2.text}")
    
    print("\n--- SEED COMPLETE ---")
    print(f"Users created (or verified):")
    print("  inv_colaba (Invest#Passw0rd!26)")
    print("  forensic_lead (Forens#Passw0rd!26)")
    print("  legal_adv (Legal#Passw0rd!2026)")
    print(f"Case created: {case_id}")
    print("Log in to the frontend as inv_colaba to view!")

if __name__ == "__main__":
    main()
