"""Idempotent reference-data seeding.

Run with:  python -m app.seed

Creates the five roles and a small set of departments. It creates the bootstrap
ADMIN account ONLY if SEED_ADMIN_PASSWORD is set in the environment — there is
deliberately no default admin password anywhere in this repository, so a
deployment can never accidentally ship with known credentials.

Safe to run repeatedly: existing rows are left untouched.
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.logging_config import configure_logging
from app.models.department import Department
from app.models.role import ROLE_DESCRIPTIONS, Role, RoleName
from app.models.permission import Permission, PermissionName
from app.models.user import User
from app.security import PasswordPolicyError, hash_password, validate_password_policy

logger = logging.getLogger("app.seed")

HIERARCHY = {
    "name": "State Police HQ",
    "description": "State Police Headquarters",
    "org_type": "STATE",
    "children": [
        {
            "name": "North Zone",
            "description": "Northern Zone Command",
            "org_type": "ZONE",
            "children": [
                {
                    "name": "Mumbai Range",
                    "description": "Mumbai Range Command",
                    "org_type": "RANGE",
                    "children": [
                        {
                            "name": "Mumbai District",
                            "description": "Mumbai District HQ",
                            "org_type": "DISTRICT",
                            "children": [
                                {
                                    "name": "Colaba Police Station",
                                    "description": "Colaba local station",
                                    "org_type": "POLICE_STATION",
                                    "children": []
                                },
                                {
                                    "name": "Bandra Police Station",
                                    "description": "Bandra local station",
                                    "org_type": "POLICE_STATION",
                                    "children": []
                                },
                            ]
                        }
                    ]
                }
            ]
        },
        {
            "name": "Criminal Investigation Department",
            "description": "Primary investigating wing for serious offences.",
            "org_type": "UNIT",
            "children": []
        },
        {
            "name": "Cyber Crime Cell",
            "description": "Digital forensics and cyber-enabled crime.",
            "org_type": "UNIT",
            "children": []
        },
        {
            "name": "Forensic Science Laboratory",
            "description": "Laboratory analysis and expert reports.",
            "org_type": "UNIT",
            "children": []
        },
        {
            "name": "Prosecution Wing",
            "description": "Legal review, filings and court liaison.",
            "org_type": "UNIT",
            "children": []
        },
        {
            "name": "Internal Audit",
            "description": "Independent oversight of case and evidence handling.",
            "org_type": "UNIT",
            "children": []
        },
    ]
}


def seed_roles(db: Session) -> dict[str, Role]:
    # 1. Seed Permissions
    from app.models.permission import Permission, PermissionName
    from sqlalchemy import select
    
    existing_perms = {p.name: p for p in db.execute(select(Permission)).scalars().all()}
    for name in PermissionName:
        if name.value not in existing_perms:
            perm = Permission(name=name.value, description=f"Permission for {name.value}")
            db.add(perm)
            existing_perms[name.value] = perm
            
    db.flush()

    # 2. Seed Roles and map permissions
    role_perms_map = {
        RoleName.ADMIN: list(PermissionName),
        RoleName.INVESTIGATOR: [
            PermissionName.CASE_CREATE, PermissionName.CASE_VIEW, PermissionName.CASE_UPDATE,
            PermissionName.DOCUMENT_VIEW, PermissionName.DOCUMENT_UPLOAD,
            PermissionName.EVIDENCE_CREATE, PermissionName.EVIDENCE_VIEW, PermissionName.EVIDENCE_TRANSFER,
            PermissionName.EVIDENCE_SEAL, PermissionName.EVIDENCE_SUBMIT, PermissionName.EVIDENCE_ARCHIVE
        ],
        RoleName.FORENSIC_OFFICER: [
            PermissionName.CASE_VIEW, PermissionName.DOCUMENT_VIEW, PermissionName.DOCUMENT_UPLOAD,
            PermissionName.EVIDENCE_VIEW, PermissionName.EVIDENCE_TRANSFER, PermissionName.EVIDENCE_ANALYZE
        ],
        RoleName.LEGAL_OFFICER: [
            PermissionName.CASE_CREATE, PermissionName.CASE_VIEW, PermissionName.CASE_UPDATE,
            PermissionName.DOCUMENT_VIEW, PermissionName.DOCUMENT_UPLOAD,
            PermissionName.EVIDENCE_VIEW, PermissionName.EVIDENCE_SUBMIT, PermissionName.EVIDENCE_ARCHIVE
        ],
        RoleName.AUDITOR: [
            PermissionName.CASE_VIEW, PermissionName.DOCUMENT_VIEW, PermissionName.EVIDENCE_VIEW, PermissionName.AUDIT_VIEW
        ]
    }

    existing = {r.name: r for r in db.execute(select(Role)).scalars().unique().all()}
    for name in RoleName:
        if name.value not in existing:
            role = Role(name=name.value, description=ROLE_DESCRIPTIONS[name])
            db.add(role)
            existing[name.value] = role
            logger.info("seed_role_created", extra={"role": name.value})
            
        role = existing[name.value]
        # Assign permissions
        assigned_perms = role_perms_map.get(name, [])
        role.permissions = [existing_perms[p.value] for p in assigned_perms]

    db.flush()
    return existing


def seed_departments(db: Session) -> dict[str, Department]:
    existing = {d.name: d for d in db.execute(select(Department)).scalars().all()}
    
    def process_node(node, parent_id=None):
        name = node["name"]
        if name not in existing:
            dept = Department(
                name=name,
                description=node.get("description"),
                org_type=node.get("org_type", "UNIT"),
                parent_id=parent_id
            )
            db.add(dept)
            db.flush() # flush to generate ID and trigger event listener
            existing[name] = dept
            logger.info("seed_department_created", extra={"department": name})
        
        dept_id = existing[name].id
        for child in node.get("children", []):
            process_node(child, dept_id)

    process_node(HIERARCHY)
    db.flush()
    return existing


def seed_admin(db: Session, roles: dict[str, Role], departments: dict[str, Department]) -> None:
    settings = get_settings()
    password = settings.seed_admin_password

    if not password:
        logger.warning(
            "seed_admin_skipped",
            extra={"reason": "SEED_ADMIN_PASSWORD is not set — no admin account was created."},
        )
        return

    username = settings.seed_admin_username
    if db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        logger.info("seed_admin_exists", extra={"username": username})
        return

    try:
        validate_password_policy(password)
    except PasswordPolicyError as exc:
        logger.error("seed_admin_rejected", extra={"reason": str(exc)})
        raise SystemExit(1) from exc

    admin = User(
        username=username,
        email=settings.seed_admin_email.lower(),
        full_name="System Administrator",
        password_hash=hash_password(password),
        role_id=roles[RoleName.ADMIN.value].id,
        department_id=departments["Internal Audit"].id,
        is_active=True,
    )
    db.add(admin)
    logger.info("seed_admin_created", extra={"username": username})


def main() -> int:
    configure_logging(get_settings().log_level)
    with SessionLocal() as db:
        roles = seed_roles(db)
        departments = seed_departments(db)
        seed_admin(db, roles, departments)
        db.commit()
    logger.info("seed_complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
