import time
import requests
import json
import uuid

BASE_URL = "http://localhost:8000/api/v1"

def test_all_flows():
    print("Testing flows...")
    # Wait for backend to be ready
    for _ in range(10):
        try:
            if requests.get(f"http://localhost:8000/api/health").status_code == 200: # Wait, maybe no health endpoint.
                break
        except:
            pass
        time.sleep(2)

    # We will just run it in the terminal manually or through the script when backend is up.
    
