# Security notes — NyayaVault M0

This document states what the prototype actually defends against, what it does
not, and what production would require. It is written to be read by someone
looking for the gaps, because a system that handles evidence should be evaluated
that way.

**NyayaVault M0 is not production-ready and must not hold real case data.**

---

## 1. Threat model

### In scope for M0

| Threat | Defence |
|---|---|
| Credential stuffing / password cracking | bcrypt cost 12 over a SHA-256 pre-hash; minimum 12-character policy across 3 character classes |
| Username enumeration via the login endpoint | Identical error message and a constant-time dummy verification when the user does not exist |
| Token forgery | HS256 signature; the algorithm allow-list is pinned so `alg: none` and downgrades are rejected; `iss`, `exp`, `iat`, `sub` all required |
| Privilege escalation via a token claim | The `role` claim is never used for a decision. The user row — and therefore the role and `is_active` flag — is re-read from the database on every request |
| Horizontal access (reading another officer's case) | Case-level authorisation; an inaccessible case returns 404 so its existence is not confirmed |
| Path traversal / arbitrary storage writes | Object keys are composed entirely from server-generated UUIDs; the client filename is reduced to a basename and stripped to `[A-Za-z0-9._-]` |
| Malicious file disguised by extension | Magic-byte sniffing cross-checked against the extension; OOXML containers are opened and their internal layout verified |
| Denial of service by upload size | The size cap is enforced while streaming in 1 MiB chunks, so an oversized body is abandoned partway rather than buffered |
| Silent overwriting of evidence | `UNIQUE(document_id, version_number)` and `UNIQUE(object_key)`; the service never issues UPDATE or DELETE against `document_versions` |
| Undetected modification of stored bytes | `GET /documents/{id}/verify` re-reads from object storage and re-hashes |
| Undetected modification of the audit log | Global hash chain; `GET /audit/verify` walks the hash pointers and recomputes every event |
| SQL injection | SQLAlchemy with bound parameters throughout; LIKE wildcards in user input are escaped |
| Information leakage in errors | Uniform terse responses; driver messages are logged against a request id, never returned |
| Stale sessions after deactivation | `is_active` is checked on every request, so revocation takes effect immediately |

### Explicitly out of scope for M0

Network-level attacks (TLS is terminated by infrastructure that does not exist
yet), insider threat with direct database write access, physical access to the
object store, supply-chain compromise of dependencies, and side channels beyond
the login timing equaliser.

---

## 2. What "hash-linked audit" does and does not mean

Each event stores the hash of its predecessor:

```
e1.event_hash = SHA256(canonical(e1 fields ‖ GENESIS))
e2.event_hash = SHA256(canonical(e2 fields ‖ e1.event_hash))
e3.event_hash = SHA256(canonical(e3 fields ‖ e2.event_hash))
```

`canonical(...)` is JSON with sorted keys and compact separators, and timestamps
are normalised to UTC at fixed precision before hashing. Concatenating fields
into one string was rejected because it is ambiguous — `("ab","c")` and
`("a","bc")` would produce the same pre-image.

**What this gives you.** Editing or deleting any historical row invalidates every
hash after it. `GET /audit/verify` reports the exact event at which verification
first fails, and distinguishes three failure modes: content that no longer
matches its hash, a forked chain, and a chain that terminates with rows left
over (a deletion). Two tests demonstrate this against a live database.

**What this does not give you.** An attacker with `UPDATE` on `audit_events`
can rewrite an event *and* recompute every subsequent hash. The chain would then
verify cleanly. This is tamper **evidence**, not tamper **proofing**.

**What would close the gap.** Publish the head hash somewhere the application
cannot rewrite — a WORM/object-lock bucket, a timestamping authority (RFC 3161),
a second database with append-only grants, or a ledger. Anchoring hourly means
an attacker can rewrite at most one hour of history undetected. This is planned
for a later milestone and is deliberately not claimed now.

Related hardening for production: revoke `UPDATE` and `DELETE` on
`audit_events` from the application's database role and insert through a
`SECURITY DEFINER` function, so even a compromised application cannot rewrite
history.

---

## 5. Reporting a vulnerability

This is a hackathon prototype with no production deployment. Raise issues with
the team directly rather than filing them publicly.
