import requests

BASE_URL = "http://localhost:8000/api/v1"
resp = requests.post(f"{BASE_URL}/auth/login", json={"username": "inv_colaba", "password": "Invest#Passw0rd!26"})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

cases = requests.get(f"{BASE_URL}/cases", headers=headers).json()["items"]
if not cases:
    print("No cases")
    exit(0)

case_id = cases[0]["id"]
print(f"Fetching evidence for {case_id}")
ev = requests.get(f"{BASE_URL}/cases/{case_id}/evidence", headers=headers)
print(ev.status_code)
print(ev.text)
