import httpx
import time
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.models.user import User
from app.config import get_settings
from minio import Minio
import io

BASE_URL = "http://localhost:8000/api/v1"

def login(client, username, password):
    r = client.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]
    
def test_evidence_and_audit():
    print("\nTesting evidence flow and audit chain...")
    client = httpx.Client(timeout=10.0)
    token_inv = login(client, "inv_colaba", "Dev#Passw0rd!2026")
    token_bandra = login(client, "inv_bandra", "Dev#Passw0rd!2026")
    
    engine = create_engine(get_settings().database_url)
    with Session(engine) as db:
        bandra_user = db.execute(select(User).where(User.username == 'inv_bandra')).scalar_one()
        bandra_id = str(bandra_user.id)
    
    client.headers.update({"Authorization": f"Bearer {token_inv}"})
    
    # Create case
    r = client.post(f"{BASE_URL}/cases", json={"title": "Audit Test", "description": "Flow test"})
    case_id = r.json()["id"]
    
    # Add bandra as a contributor so they can accept evidence
    r = client.post(f"{BASE_URL}/cases/{case_id}/members", json={"user_id": bandra_id, "access_level": "CONTRIBUTE"})
    r.raise_for_status()
    
    # Create evidence
    r = client.post(f"{BASE_URL}/cases/{case_id}/evidence", json={"title": "Knife", "evidence_type": "physical", "storage_location": "A1"})
    r.raise_for_status()
    ev_id = r.json()["id"]
    print(f"Created evidence {ev_id}")
    
    # Seal evidence
    r = client.post(f"{BASE_URL}/evidence/{ev_id}/seal")
    r.raise_for_status()
    
    # Transfer evidence
    r = client.post(f"{BASE_URL}/evidence/{ev_id}/transfers", json={"to_user_id": bandra_id, "notes": "Handover"})
    transfer_id = r.json()["id"]
    r.raise_for_status()
    print("Transferred evidence")
    
    # Accept transfer (as bandra)
    client.headers.update({"Authorization": f"Bearer {token_bandra}"})
    r = client.post(f"{BASE_URL}/transfers/{transfer_id}/accept", json={"notes": "Received"})
    r.raise_for_status()
    print("Accepted evidence")
    
    # Check audit chain for this evidence
    client.headers.update({"Authorization": f"Bearer {token_inv}"})
    r = client.get(f"{BASE_URL}/cases/{case_id}/audit")
    r.raise_for_status()
    events = [e for e in r.json()["items"] if e["entity_id"] == ev_id]
    
    for e in events:
        print(f"Event: {e['action']} | hash: {e['event_hash']} | prev: {e.get('previous_event_hash')}")
        
    # verify entire chain
    token_admin = login(client, "admin", "Admin#Passw0rd!2026") # Or whatever admin password is
    client.headers.update({"Authorization": f"Bearer {token_admin}"})
    r = client.get(f"{BASE_URL}/audit/verify")
    r.raise_for_status()
    print(f"Global Audit verify: {r.json()}")

test_evidence_and_audit()

def test_ocr():
    print("\nTesting OCR flow...")
    client = httpx.Client(timeout=10.0)
    token = login(client, "inv_colaba", "Dev#Passw0rd!2026")
    client.headers.update({"Authorization": f"Bearer {token}"})
    
    r = client.post(f"{BASE_URL}/cases", json={"title": "OCR Test Case", "description": "Flow test"})
    case_id = r.json()["id"]
    
    # We need a small image converted to PDF for OCR
    from PIL import Image
    import io
    img = Image.new('RGB', (200, 50), color = (255, 255, 255))
    from PIL import ImageDraw, ImageFont
    d = ImageDraw.Draw(img)
    d.text((10,10), "SECRET KEY 99", fill=(0,0,0))
    pdf_bytes = io.BytesIO()
    img.save(pdf_bytes, format='PDF')
    
    files = {"file": ("scanned.pdf", pdf_bytes.getvalue(), "application/pdf")}
    data = {"title": "Scanned Doc", "document_type": "OTHER"}
    r = client.post(f"{BASE_URL}/cases/{case_id}/documents", files=files, data=data)
    doc_id = r.json()["id"]
    print(f"Uploaded scanned doc {doc_id}")
    
    # Trigger OCR explicitly if needed, or check if it happens automatically.
    # Usually it's automatic via background task.
    time.sleep(5)
    
    # Search
    r = client.get(f"{BASE_URL}/search?q=SECRET")
    print(f"Search results: {r.json()}")

if __name__ == "__main__":
    test_ocr()
