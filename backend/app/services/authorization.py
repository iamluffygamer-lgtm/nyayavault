"""Authorisation policy — the single source of truth for "who may do what".

Two layers, both evaluated server-side against database state:

1. **Role-based** — coarse capabilities attached to the user's role.
2. **Case-level** — whether this user may touch *this* case.

The role is always re-read from the `users` table via the JWT subject. The
`role` claim inside the token is never consulted for a decision, and nothing
sent by the browser can influence the outcome.

Case-level rule for M0
----------------------
* ADMIN            — full access to every case.
* AUDITOR          — read-only access to every case, including the audit trail.
* Case creator     — MANAGE access to cases they opened.
* Assigned members — access at the level recorded in `case_assignments`.
* Everyone else    — no access; the case is reported as not found.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import NotFoundError, PermissionDeniedError
from app.models.case import (
    MUTABLE_CASE_STATUSES,
    Case,
    CaseAccessLevel,
    CaseAssignment,
    CaseStatus,
)
from app.models.role import RoleName
from app.models.user import User

# ---------------------------------------------------------------- capabilities

CAN_CREATE_CASE = frozenset({RoleName.ADMIN, RoleName.INVESTIGATOR, RoleName.LEGAL_OFFICER})
CAN_UPLOAD_DOCUMENT = frozenset(
    {
        RoleName.ADMIN,
        RoleName.INVESTIGATOR,
        RoleName.FORENSIC_OFFICER,
        RoleName.LEGAL_OFFICER,
    }
)
CAN_MANAGE_USERS = frozenset({RoleName.ADMIN})
# Roles with unrestricted visibility. AUDITOR is read-only by construction: it
# appears here but in no write capability set.
GLOBAL_READERS = frozenset({RoleName.ADMIN, RoleName.AUDITOR})
GLOBAL_WRITERS = frozenset({RoleName.ADMIN})

_LEVEL_RANK = {
    CaseAccessLevel.READ: 1,
    CaseAccessLevel.CONTRIBUTE: 2,
    CaseAccessLevel.MANAGE: 3,
}


@dataclass(frozen=True)
class CaseAccess:
    """Resolved access of one user to one case."""

    case: Case
    level: CaseAccessLevel
    via: str  # "role" | "creator" | "assignment"

    @property
    def can_read(self) -> bool:
        return True

    @property
    def can_contribute(self) -> bool:
        return _LEVEL_RANK[self.level] >= _LEVEL_RANK[CaseAccessLevel.CONTRIBUTE]

    @property
    def can_manage(self) -> bool:
        return _LEVEL_RANK[self.level] >= _LEVEL_RANK[CaseAccessLevel.MANAGE]


def has_role(user: User, allowed: frozenset[RoleName]) -> bool:
    return user.role_name in {str(r) for r in allowed}


def require_role(user: User, allowed: frozenset[RoleName], *, action: str) -> None:
    if not has_role(user, allowed):
        raise PermissionDeniedError(f"Your role ({user.role_name}) may not {action}.")


def resolve_case_access(db: Session, user: User, case: Case) -> CaseAccess | None:
    """Return the user's access to a case, or None if they have none."""
    role = user.role_name

    if role == RoleName.ADMIN:
        return CaseAccess(case=case, level=CaseAccessLevel.MANAGE, via="role")
    if role == RoleName.AUDITOR:
        return CaseAccess(case=case, level=CaseAccessLevel.READ, via="role")
    if case.created_by == user.id:
        return CaseAccess(case=case, level=CaseAccessLevel.MANAGE, via="creator")

    assignment = db.execute(
        select(CaseAssignment).where(
            CaseAssignment.case_id == case.id, CaseAssignment.user_id == user.id
        )
    ).scalar_one_or_none()
    if assignment is not None:
        return CaseAccess(case=case, level=assignment.access_level, via="assignment")

    return None


def get_case_for_user(
    db: Session,
    user: User,
    case_id: uuid.UUID,
    *,
    require_write: bool = False,
) -> CaseAccess:
    """Load a case and assert the user may use it.

    A case the user cannot see raises NotFoundError, not PermissionDeniedError,
    so the API never confirms that a case exists to someone unauthorised.
    """
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError("Case not found.")

    access = resolve_case_access(db, user, case)
    if access is None:
        raise NotFoundError("Case not found.")

    if require_write:
        if not access.can_contribute:
            raise PermissionDeniedError("You have read-only access to this case.")
        if case.status not in MUTABLE_CASE_STATUSES:
            raise PermissionDeniedError(
                f"Case {case.case_number} is {case.status} and no longer accepts changes."
            )
    return access


def assert_case_status_transition(current: CaseStatus, target: CaseStatus) -> None:
    """Archived cases are terminal; everything else may move freely for M0."""
    if current == CaseStatus.ARCHIVED and target != CaseStatus.ARCHIVED:
        raise PermissionDeniedError("An archived case cannot be reopened.")

def get_authorized_cases_query(user: User) -> select:
    """Return a SQLAlchemy Select statement yielding authorized case IDs.
    
    This must mirror `resolve_case_access` perfectly.
    """
    from app.models.case import Case, CaseAssignment
    from sqlalchemy import or_

    if user.role_name in (RoleName.ADMIN, RoleName.AUDITOR):
        return select(Case.id)
    
    return select(Case.id).distinct().outerjoin(
        CaseAssignment, CaseAssignment.case_id == Case.id
    ).where(
        or_(
            Case.created_by == user.id,
            CaseAssignment.user_id == user.id
        )
    )
