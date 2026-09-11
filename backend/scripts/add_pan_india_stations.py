import requests
import sys

BASE_URL = "http://localhost:8000/api/v1"

def login(username, password):
    resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    if resp.status_code != 200:
        print("Failed admin login")
        sys.exit(1)
    return resp.json()["access_token"]

def create_dept(auth, name, desc, org_type, parent_id=None):
    payload = {
        "name": name,
        "description": desc,
        "org_type": org_type,
        "parent_id": parent_id
    }
    resp = requests.post(f"{BASE_URL}/departments", headers=auth, json=payload)
    if resp.status_code == 201:
        return resp.json()["id"]
    elif resp.status_code == 400 and "already exists" in resp.text:
        # Just fetch it
        depts = requests.get(f"{BASE_URL}/departments", headers=auth).json()
        for d in depts:
            if d["name"] == name:
                return d["id"]
    return None

def main():
    token = login("admin", "Admin#Passw0rd!2026")
    auth = {"Authorization": f"Bearer {token}"}

    # DELHI
    delhi_hq = create_dept(auth, "Delhi Police Headquarters", "Apex command for NCT of Delhi", "STATE")
    if delhi_hq:
        nd_dist = create_dept(auth, "New Delhi District", "New Delhi District Command", "DISTRICT", delhi_hq)
        create_dept(auth, "Parliament Street Police Station", "High security zone station", "STATION", nd_dist)
        create_dept(auth, "Connaught Place Police Station", "Commercial hub station", "STATION", nd_dist)

    # UP
    up_hq = create_dept(auth, "Uttar Pradesh Police Headquarters", "Apex command for UP", "STATE")
    if up_hq:
        lucknow = create_dept(auth, "Lucknow Commissionerate", "Lucknow Urban Command", "DISTRICT", up_hq)
        create_dept(auth, "Hazratganj Kotwali", "Central Lucknow Kotwali", "STATION", lucknow)
        create_dept(auth, "Gomti Nagar Police Station", "Gomti Nagar Station", "STATION", lucknow)
        
    # KARNATAKA
    kar_hq = create_dept(auth, "Karnataka State Police Headquarters", "Apex command for Karnataka", "STATE")
    if kar_hq:
        blr = create_dept(auth, "Bengaluru City Police", "Bengaluru Urban Command", "DISTRICT", kar_hq)
        create_dept(auth, "Cubbon Park Police Station", "Central Bengaluru Station", "STATION", blr)
        create_dept(auth, "Koramangala Police Station", "South-East Bengaluru Station", "STATION", blr)

    print("Pan-India stations added successfully!")

if __name__ == "__main__":
    main()
