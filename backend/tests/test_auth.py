"""Required coverage: (1) user authentication, (2) invalid login."""

from __future__ import annotations

from tests.conftest import PASSWORDS, auth, login


def test_login_succeeds_and_returns_a_usable_token(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "investigator", "password": PASSWORDS["investigator"]},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["user"]["username"] == "investigator"
    assert body["user"]["role"]["name"] == "INVESTIGATOR"
    # The password hash must never appear in a response.
    assert "password_hash" not in body["user"]
    assert "password" not in body["user"]

    me = client.get("/api/v1/auth/me", headers=auth(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["username"] == "investigator"


def test_login_with_wrong_password_is_rejected(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "investigator", "password": "definitely-not-the-password"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


def test_login_for_unknown_user_gives_the_same_message(client):
    """Identical wording, so the endpoint cannot be used to enumerate usernames."""
    unknown = client.post(
        "/api/v1/auth/login", json={"username": "ghost", "password": "irrelevant"}
    )
    wrong_password = client.post(
        "/api/v1/auth/login", json={"username": "investigator", "password": "wrong"}
    )
    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json()["error"]["message"] == wrong_password.json()["error"]["message"]


def test_deactivated_account_cannot_authenticate(client, db_session, seeded):
    from app.models import User

    user = db_session.get(User, seeded["users"]["legal"].id)
    user.is_active = False
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login", json={"username": "legal", "password": PASSWORDS["legal"]}
    )
    assert response.status_code == 401


def test_protected_endpoints_require_a_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/cases").status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth("not-a-real-token")).status_code == 401


def test_tampered_token_is_rejected(client):
    """A token re-signed with a different key must not be accepted."""
    import jwt

    token = login(client, "investigator")
    claims = jwt.decode(token, options={"verify_signature": False})
    forged = jwt.encode({**claims, "role": "ADMIN"}, "attacker-key", algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers=auth(forged)).status_code == 401


def test_role_claim_in_a_valid_token_does_not_grant_privileges(client, db_session, seeded):
    """The token's `role` claim is informational; the database decides.

    Here the token is signed with the *correct* server key but carries
    role=ADMIN for a user who is only an INVESTIGATOR. The admin-only endpoint
    must still refuse, proving authorisation re-reads the database.
    """
    import jwt

    from app.config import get_settings

    settings = get_settings()
    token = login(client, "investigator")
    claims = jwt.decode(
        token, settings.jwt_secret_key, algorithms=["HS256"], issuer=settings.app_name
    )
    escalated = jwt.encode(
        {**claims, "role": "ADMIN"}, settings.jwt_secret_key, algorithm="HS256"
    )

    response = client.get("/api/v1/users", headers=auth(escalated))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_only_admins_may_create_users(client, seeded):
    role_id = str(seeded["roles"]["FORENSIC_OFFICER"].id)
    payload = {
        "username": "newofficer",
        "email": "newofficer@nyayavault.gov.in",
        "password": "Another#Strong1Pass",
        "role_id": role_id,
    }

    denied = client.post(
        "/api/v1/users", headers=auth(login(client, "investigator")), json=payload
    )
    assert denied.status_code == 403

    allowed = client.post("/api/v1/users", headers=auth(login(client, "admin")), json=payload)
    assert allowed.status_code == 201, allowed.text
    assert allowed.json()["role"]["name"] == "FORENSIC_OFFICER"


def test_weak_passwords_are_refused(client, seeded):
    response = client.post(
        "/api/v1/users",
        headers=auth(login(client, "admin")),
        json={
            "username": "weakuser",
            "email": "weak@nyayavault.gov.in",
            "password": "password",
            "role_id": str(seeded["roles"]["AUDITOR"].id),
        },
    )
    assert response.status_code == 422


def test_password_hashing_is_salted_and_verifiable():
    from app.security import hash_password, verify_password

    first = hash_password("Correct#Horse1Battery")
    second = hash_password("Correct#Horse1Battery")

    assert first != second, "each hash must use a fresh salt"
    assert first.startswith("$2b$")
    assert verify_password("Correct#Horse1Battery", first)
    assert not verify_password("Correct#Horse1Batteryx", first)
    assert not verify_password("", first)


def test_long_passwords_are_not_truncated_at_72_bytes():
    """bcrypt truncates at 72 bytes; the SHA-256 pre-hash prevents that."""
    from app.security import hash_password, verify_password

    base = "A" * 72
    stored = hash_password(base + "#first1")
    assert not verify_password(base + "#second2", stored)
