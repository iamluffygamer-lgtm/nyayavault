import sys
import logging
from sqlalchemy import select, delete
from app.database import SessionLocal
from app.models.case import Case, CaseAssignment
from app.models.document import Document, DocumentVersion
from app.models.evidence import Evidence, EvidenceTransfer
from app.models.audit import AuditEvent
from app.models.user import User
from app.models.role import Role
from app.models.department import Department
from app.services.audit_service import record_event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_case")

def main():
    with SessionLocal() as db:
        admin = db.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
        if not admin:
            logger.error("Admin user not found.")
            return 1
            
        dept = db.execute(select(Department).where(Department.name == "Colaba Police Station")).scalar_one_or_none()
        if not dept:
            dept = admin.department
            
        db.execute(delete(EvidenceTransfer))
        db.execute(delete(Evidence))
        db.execute(delete(DocumentVersion))
        db.execute(delete(Document))
        db.execute(delete(CaseAssignment))
        db.execute(delete(AuditEvent))
        db.execute(delete(Case))
        db.commit()
        
        investigator = db.execute(select(User).where(User.username == "inspector.rao")).scalar_one_or_none()
        if not investigator:
            inv_role = db.execute(select(Role).where(Role.name == "INVESTIGATOR")).scalar_one()
            from app.security import hash_password
            investigator = User(
                username="inspector.rao",
                email="r.rao@police.gov.in",
                full_name="Inspector R. Rao",
                password_hash=hash_password("Passw0rd123!"),
                role_id=inv_role.id,
                department_id=dept.id,
                is_active=True
            )
            db.add(investigator)
            db.flush()

        case = Case(
            case_number="FIR-2026-0089",
            title="Financial Fraud and Embezzlement - Sterling Corp",
            description="Investigation into alleged diversion of corporate funds totaling ₹45,000,000 by senior executives through shell companies.\n\nComplainant: Board of Directors, Sterling Corp.\nJurisdiction: Cyber Crime & Financial Fraud Wing",
            status="UNDER_INVESTIGATION",
            created_by=investigator.id,
            department_id=dept.id
        )
        db.add(case)
        db.flush()
        
        db.add(CaseAssignment(case_id=case.id, user_id=admin.id, access_level="MANAGE", assigned_by=admin.id))
        db.add(CaseAssignment(case_id=case.id, user_id=investigator.id, access_level="MANAGE", assigned_by=admin.id))
        db.commit()
        
        record_event(
            db,
            actor_id=investigator.id,
            action="CASE_CREATED",
            entity_type="CASE",
            entity_id=str(case.id),
            case_id=case.id,
            metadata={"case_number": case.case_number}
        )
        
        logger.info("Successfully created professional case: FIR-2026-0089")

if __name__ == "__main__":
    sys.exit(main())
