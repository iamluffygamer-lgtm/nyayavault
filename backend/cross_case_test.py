import sys
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User
from app.models.role import Role, RoleName
from app.models.case import Case, CaseAssignment, CaseStatus
from app.models.document import Document, DocumentVersion, DocumentText, ExtractionMethod, ExtractionStatus, DocumentType
from app.services.search_service import execute_search

db = SessionLocal()

try:
    inv_a = db.query(User).filter_by(username="inv_a_test").first()

    # 5. Execute Search as Investigator A
    # Search for something in Case 1
    result1 = execute_search(db, inv_a, q="fingerprint")
    res1 = result1["items"]
    total1 = result1["total"]
    print(f"\n[+] Inv A searching 'fingerprint' (authorized term): Total={total1}, Items={[r.get("title") if isinstance(r, dict) else getattr(r, "title") for r in res1]}")
    assert total1 == 1

    # Search for PROJECT-ORANGE-999
    result2 = execute_search(db, inv_a, q="PROJECT-ORANGE-999")
    res2 = result2["items"]
    total2 = result2["total"]
    print(f"\n[+] Inv A searching 'PROJECT-ORANGE-999' (unauthorized term): Total={total2}, Items={[r.get("title") if isinstance(r, dict) else getattr(r, "title") for r in res2]}")
    assert total2 == 0
    assert len(res2) == 0

    print("\n[SUCCESS] Cross-case search isolation verified!")

except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
