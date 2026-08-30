# Architecture decisions

Each entry states the decision, why it was made, and what it costs. Where a
decision was close, the rejected alternative is named.

---

## 1. Modular monolith, not microservices

**Decision.** One FastAPI process with internal seams: `routers → services →
models`, plus a storage adapter.

**Why.** The brief requires it, and it is right anyway. At M0 the whole system
shares one transactional boundary — a document version and its audit event
*must* commit together. Splitting them across services would replace a database
transaction with a distributed one, which is a large amount of complexity bought
to solve a scaling problem that does not exist yet.

**Cost.** The whole API scales as one unit. The seams are drawn so that document
processing (OCR, embeddings) can be extracted later, because those are genuinely
asynchronous and CPU-bound.

---

## 2. UUID primary keys

**Decision.** Every table uses `sa.Uuid` primary keys rather than serial integers.

**Why.** Identifiers appear in URLs. Sequential integers let anyone with one
valid case ID probe for neighbours, and the count leaks how many cases exist.
`sa.Uuid` is dialect-aware — native `UUID` on PostgreSQL, `CHAR(32)` on SQLite —
so the test suite runs without PostgreSQL.

**Cost.** Slightly larger indexes and non-sequential inserts. Human-facing
identity is served by `case_number` (`NV-2026-000042`) instead.

---

## 3. Enums as VARCHAR + CHECK, not native PostgreSQL enums

**Decision.** `sa.Enum(..., native_enum=False)`.

**Why.** Adding a value to a native PostgreSQL enum requires `ALTER TYPE`, which
is awkward inside a transaction and historically painful to reverse. Case
statuses and audit actions will grow every milestone. A CHECK constraint gives
the same integrity with a trivial migration, and keeps the schema portable to
SQLite for tests.

**Cost.** A few bytes per row and no native enum ordering.

---

## 4. The role in the JWT is decorative

**Decision.** Tokens carry a `role` claim, but `get_current_user` re-reads the
user row on every request and authorisation uses the database value.

**Why.** The brief says "never trust role information supplied by the frontend".
A signed claim is *not* frontend-supplied, so putting the role in the token would
be defensible — but it also means a role change or account deactivation does not
take effect until the token expires, up to eight hours later. For a system where
revoking an officer's access should be immediate, that is the wrong trade.
`test_role_claim_in_a_valid_token_does_not_grant_privileges` pins this behaviour:
a token signed with the *correct* key but carrying `role: ADMIN` still gets a 403.

**Cost.** One indexed primary-key lookup per request.

---

## 5. Inaccessible cases return 404, not 403

**Decision.** A case that exists but that the caller may not see is reported as
not found.

**Why.** 403 confirms existence. An investigator could enumerate case IDs and
learn which ones are real — for a system holding sealed investigations, the
existence of a case is itself sensitive.

**Cost.** Slightly less helpful errors for legitimate users, mitigated by the UI
suggesting they ask the case owner for access.

---

## 6. `case_assignments`: an eighth table

**Decision.** Added beyond the six entities the brief lists.

**Why.** The problem statement requires *case-level* access control. Role alone
cannot express "this investigator may see this case", and the alternative —
creator-only visibility — makes collaboration impossible, which is not how
investigations work. Adding the table now avoids reworking every authorisation
call site in M1.

**Cost.** One table and one join beyond the specification. All six specified
entities exist exactly as described. The deviation is documented in the M0
report rather than left for a reviewer to discover.

---

## 7. Global audit chain, not per-case

**Decision.** One hash chain across the whole system; the per-case view is a
filter over it.

**Why.** With per-case chains, deleting an entire case's audit history leaves no
trace anywhere else. A global chain means any deletion breaks the single chain.

**Cost.** Appends must be serialised. On PostgreSQL a transaction-scoped advisory
lock (`pg_advisory_xact_lock`) is taken around read-head-and-append; it does not
lock the table, so concurrent readers are unaffected. This is a throughput
ceiling on audit writes and is the correct thing to revisit if the system ever
sustains high write concurrency.

---

## 8. Verification walks hash pointers, not a sorted column

**Decision.** `verify_chain` builds a map of `previous_event_hash → event` and
walks from the genesis sentinel, rather than ordering by timestamp.

**Why.** Ordering by timestamp would trust a column an attacker can edit. The
hash pointers are covered by the hashes themselves, so following them is the
only ordering that cannot be forged. It also makes deletions detectable as a
distinct failure mode: the walk terminates with rows left over.

**Cost.** O(n) memory for the map. Fine at prototype scale; a windowed
verification is the answer at millions of events.

---

## 9. Timestamps are canonicalised before hashing

**Decision.** `canonical_timestamp()` converts to UTC at fixed microsecond
precision before the value enters the hash pre-image.

**Why.** This was a real bug caught by the tests. PostgreSQL returns
timezone-aware datetimes; SQLite returns naive ones. Hashing `isoformat()`
directly produced one value on write and a different one on read, so every
verification reported tampering that had not happened. A security feature that
cries wolf is worse than no feature, because people learn to ignore it.

---

## 10. Canonical JSON as the hash pre-image

**Decision.** `json.dumps(..., sort_keys=True, separators=(",", ":"))` rather
than string concatenation.

**Why.** Concatenation is ambiguous: `("ab", "c")` and `("a", "bc")` produce the
same pre-image, which is a (minor, but real) collision. Sorted-key JSON is
unambiguous and stable across Python versions and dict insertion orders. A test
asserts that two metadata dicts with different key ordering hash identically.

---

## 11. Downloads stream through the API; no presigned URLs

**Decision.** `StreamingResponse` from object storage, through FastAPI, to the
client.

**Why.** Two things a presigned URL cannot do: re-check authorisation for the
request actually being served, and write an audit event for every read. For a
system whose next milestone is chain of custody, "who opened this document, and
when" is the whole point.

**Cost.** Backend bandwidth and a held connection per download. Presigned URLs
with short expiry are the scaling answer, and the trade is stated in
`routers/documents.py` so the next engineer sees the reasoning before changing
it.

---

## 12. Hand-written magic-byte sniffing, not `libmagic`

**Decision.** A small signature table in `file_validation.py` instead of
`python-magic`.

**Why.** `python-magic` needs the `libmagic` native library, which behaves
differently across base images and is a recurring source of "works on my
machine". The signature table covers exactly the formats the system accepts,
which is a smaller and more auditable surface than a general-purpose identifier —
and for OOXML it does something `libmagic` does not: opens the ZIP and checks for
`word/document.xml`, so an archive of executables renamed `.docx` is rejected.

**Cost.** Adding a format means writing its signature check. That is the point.

---

## 13. bcrypt directly, with a SHA-256 pre-hash

**Decision.** No passlib; `bcrypt.hashpw(base64(sha256(password)), salt)`.

**Why.** Two independent reasons. passlib 1.7.4 is unmaintained and raises
against bcrypt ≥ 4.1 — a dependency that breaks on upgrade is not a good
foundation. Separately, bcrypt silently truncates at 72 bytes, so two long
passwords sharing a 72-byte prefix would be equivalent; the pre-hash makes every
byte contribute. `test_long_passwords_are_not_truncated_at_72_bytes` proves it.

**Cost.** One extra SHA-256 per verification, which is negligible next to bcrypt.

---

## 14. Object storage behind an interface

**Decision.** `ObjectStorage` ABC with `MinioStorage` and `InMemoryStorage`.

**Why.** Three benefits from one abstraction: the test suite needs no MinIO
container; object-key generation lives in exactly one function, so a client can
never influence a path; and swapping MinIO for S3 or Azure later touches one
module. `InMemoryStorage.corrupt()` also makes the tamper-detection test
possible — it simulates modification at the storage layer, which is the exact
scenario integrity verification exists to catch.

**Cost.** One layer of indirection, which the brief's "no unnecessary
abstractions" rule justifies precisely because it earns three concrete things.

---

## 15. Uploads are streamed, hashed and size-checked in one pass

**Decision.** Read in 1 MiB chunks into a `SpooledTemporaryFile`, updating the
SHA-256 and the byte counter as we go, aborting the moment the limit is exceeded.

**Why.** `await file.read()` buffers the entire body in memory before any check
runs, so the size limit would be enforced only after the damage was done — a
free denial-of-service. Streaming means an oversized upload is abandoned
partway. The spool keeps small files in memory and spills larger ones to disk.

---

## 16. Identical re-uploads are rejected, not versioned

**Decision.** If the new bytes hash to the same value as the current version,
return 409.

**Why.** A double-clicked submit button should not create a v2 identical to v1.
In a system where version history is evidence, a spurious revision is noise a
lawyer would have to explain.

**Cost.** Legitimately re-uploading identical content requires an explicit path.
Acceptable, and arguably correct.

---

## 17. Object cleanup on transaction failure

**Decision.** If the database work after a successful object write fails, the
object is deleted and the transaction rolls back.

**Why.** Otherwise storage accumulates blobs with no metadata — invisible, never
garbage-collected, and holding case material nobody knows about.

**Cost.** Deletion is best-effort. A crash between the object write and the
rollback still orphans a blob; a reconciliation job comparing storage against
`document_versions` is the production answer.

---

## 18. Audit writes share the caller's transaction

**Decision.** `record_event` flushes but does not commit; the caller owns the
transaction.

**Why.** The audit row and the change it describes must be atomic. If the audit
write fails, the action rolls back — an action that cannot be recorded must not
happen. The alternative (a separate transaction, or fire-and-forget logging)
allows silent unaudited changes, which for this system is the worst failure mode
available.

**Cost.** An audit failure fails the user's request. That is the intended trade.

---

## 19. Response schemas as an outbound allow-list

**Decision.** Every endpoint declares a `response_model`.

**Why.** A field not declared in a schema cannot reach a client. That is how
`password_hash` and `object_key` stay internal — not by remembering to strip them
at each call site, but structurally. `object_key` in particular is withheld
because publishing the storage layout helps an attacker who has reached MinIO
directly.

---

## 20. `from __future__ import annotations` is omitted in `dependencies.py`

**Decision.** That one module does not use postponed annotations, with a comment
explaining why.

**Why.** FastAPI resolves the signature of a callable *instance* (the
`RequireRoles` dependency class) without access to the defining module's globals,
so a stringified annotation like `"CurrentUser"` cannot be resolved. The
parameter was silently treated as a query parameter, and every role-gated
endpoint returned 422 instead of enforcing anything. Caught by the tests; the
comment exists so nobody adds the import back.

---

## 21. Encryption at rest is deferred to the deployment layer

**Decision.** M0 stores documents and database rows unencrypted beyond whatever
the underlying disk provides. No application-level envelope encryption.

**Why.** Encryption at rest is an infrastructure property, not an application
one, and implementing it badly in the application is worse than not implementing
it at all: the keys end up in the same `.env` as everything else, which encrypts
the data against an attacker who already holds the key. The honest position at
prototype stage is to state the requirement and leave the mechanism to the
deployment.

**Production deployment requires encryption at rest with managed key
infrastructure.** Concretely: server-side encryption on the MinIO/S3 bucket with
keys held in a KMS (AWS KMS, Azure Key Vault, or Vault transit), transparent
data encryption or an encrypted volume for PostgreSQL, and key material the
application process can request but never store. Per-case data keys are worth
considering, because they turn "destroy this case's material" into a
key-deletion operation rather than a storage sweep.

**Cost.** Disk-level access to a prototype deployment exposes case documents.
This is why `SECURITY.md` states that M0 must not hold real case data.

---

## 22. Retention, legal hold and archival are modelled but not built

**Decision.** `document_versions` is append-only and nothing is ever deleted,
but there is no retention policy, no `retention_until`, no legal-hold flag and
no archival state machine.

**Why.** The evidence lifecycle is domain work that belongs with the rest of the
legal workflow, not bolted onto the storage foundation. Adding the columns before
the workflow that drives them produces fields nobody sets.

**The shape it will take.** A document carries a retention policy and a computed
`retention_until`; an independent `legal_hold` flag suspends expiry regardless of
policy — a hold must always win over a schedule, which is the entire point of a
hold — and an `archival_status` moves material to colder storage without removing
it from the audit chain. Expiry then becomes a deliberate, audited action rather
than a background delete.

**Cost.** Until this exists nothing ages out, which for a prototype is the safe
direction to fail in.
