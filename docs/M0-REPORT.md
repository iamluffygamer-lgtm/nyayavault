# M0 Deliverables Report

The brief asked for six things at the end. Here they are.

---

## 1. Files created

### Root

| File | Purpose |
|---|---|
| `docker-compose.yml` | PostgreSQL (pgvector), MinIO, backend, frontend. Health-gated startup ordering. |
| `.env.example` | Every environment variable, annotated. No real secrets. |
| `.gitignore` | Excludes `.env`, virtualenvs, `node_modules`, build output. |
| `Makefile` | `up`, `down`, `migrate`, `seed`, `test`, `shell-db`, … |
| `README.md` | Architecture, quick start, demo walkthrough, API table, limitations. |
| `SECURITY.md` | Threat model, known weaknesses, production checklist. |
| `docs/ARCHITECTURE.md` | Design decisions and their reasoning. |
| `docs/M0-REPORT.md` | This file. |

### Backend — `backend/`

| File | Purpose |
|---|---|
| `Dockerfile` | Python 3.12-slim, non-root user. |
| `requirements.txt` | Pinned dependencies. |
| `pytest.ini` | Test configuration. |
| `alembic.ini` | Alembic config; the URL is injected from the environment. |
| `alembic/env.py` | Reads `DATABASE_URL` from settings, imports all models. |
| `alembic/script.py.mako` | Revision template. |
| `alembic/versions/0001_initial_schema.py` | All 8 tables; enables `pgvector`. |
| **`app/`** | |
| `main.py` | App factory, CORS, request-id middleware, security headers, routers, `/health`. |
| `config.py` | Pydantic settings; refuses placeholder secrets in production. |
| `database.py` | Engine, session factory, `get_db` dependency. |
| `storage.py` | `ObjectStorage` interface, `MinioStorage`, `InMemoryStorage`, key generation, filename sanitisation. |
| `security.py` | bcrypt-sha256 hashing, password policy, JWT issue/verify. |
| `dependencies.py` | `get_current_user`, `RequireRoles`, typed aliases. |
| `errors.py` | Exception hierarchy and handlers. |
| `logging_config.py` | JSON structured logging. |
| `seed.py` | Idempotent roles, departments, optional bootstrap admin. |
| **`app/models/`** | `base.py`, `role.py`, `department.py`, `user.py`, `case.py`, `document.py`, `audit.py` |
| **`app/schemas/`** | `common.py`, `auth.py`, `user.py`, `case.py`, `document.py`, `audit.py` |
| **`app/services/`** | `authorization.py`, `auth_service.py`, `case_service.py`, `document_service.py`, `audit_service.py`, `file_validation.py` |
| **`app/routers/`** | `auth.py`, `users.py`, `cases.py`, `documents.py`, `audit.py` |
| **`tests/`** | `conftest.py`, `test_auth.py`, `test_cases.py`, `test_documents.py`, `test_audit.py` |

### Frontend — `frontend/`

| File | Purpose |
|---|---|
| `package.json`, `tsconfig.json`, `next.config.mjs`, `tailwind.config.ts`, `postcss.config.mjs`, `.eslintrc.json` | Project configuration; security headers set in `next.config.mjs`. |
| `Dockerfile` | Multi-stage build, standalone output, non-root. |
| `.env.local.example` | `NEXT_PUBLIC_API_BASE_URL`. |
| `src/app/layout.tsx`, `globals.css`, `page.tsx` | Shell and design tokens. |
| `src/app/login/page.tsx` | Split-panel sign-in. |
| `src/app/dashboard/page.tsx` | Real stat tiles, recent cases, activity, chain verification. |
| `src/app/cases/page.tsx` | Searchable, filterable list; new-case dialog. |
| `src/app/cases/[id]/page.tsx` | Case header, documents / activity / members tabs, upload. |
| `src/app/documents/[id]/page.tsx` | Metadata, version history with full SHA-256, verify, download, supersede. |
| `src/app/audit/page.tsx` | Oversight view with chain verification. |
| `src/components/ui/index.tsx` | Button, Card, Badge, Input, Textarea, Select, Label, Table, Dialog, Alert, Skeleton, EmptyState. |
| `src/components/layout/app-shell.tsx` | Authenticated shell, sidebar, route guard. |
| `src/components/brand.tsx` | Logo and wordmark. |
| `src/components/cases/case-status-badge.tsx` | Status colouring. |
| `src/components/documents/document-upload.tsx` | Drag-and-drop upload form. |
| `src/components/integrity-badge.tsx` | Verified / failed / not-yet-checked state. |
| `src/components/audit/audit-timeline.tsx` | Human-readable event timeline with hashes. |
| `src/lib/api.ts` | Typed API client, 401 handling, authenticated blob download. |
| `src/lib/auth.ts` | Session storage with the limitation documented in-file. |
| `src/lib/utils.ts` | `cn`, byte/date formatting, hash shortening. |
| `src/types/index.ts` | TypeScript mirrors of every API schema. |

---

## 2. Commands to run the project

```bash
cp .env.example .env
# replace every CHANGE_ME value, and set SEED_ADMIN_PASSWORD

docker compose up -d --build          # or: make up
docker compose logs -f backend
```

| Service | URL |
|---|---|
| Web | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| MinIO console | http://localhost:9001 |

Stop with `docker compose down`; wipe data with `docker compose down -v`.

Without Docker:

```bash
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload

# frontend
cd frontend && cp .env.local.example .env.local
npm install && npm run dev
```

---

## 3. Environment variables required

| Variable | Required | Default | Notes |
|---|---|---|---|
| `POSTGRES_USER` | ✅ | — | Database container |
| `POSTGRES_PASSWORD` | ✅ | — | Database container |
| `POSTGRES_DB` | ✅ | — | Database container |
| `DATABASE_URL` | ✅ | — | SQLAlchemy URL used by the API |
| `MINIO_ROOT_USER` | ✅ | — | MinIO container |
| `MINIO_ROOT_PASSWORD` | ✅ | — | MinIO container, minimum 8 characters |
| `MINIO_ENDPOINT` | ✅ | `localhost:9000` | `minio:9000` inside compose |
| `MINIO_ACCESS_KEY` | ✅ | — | API → MinIO |
| `MINIO_SECRET_KEY` | ✅ | — | API → MinIO |
| `MINIO_BUCKET` | | `nyayavault-documents` | Created on startup if absent |
| `MINIO_SECURE` | | `false` | `true` in production |
| `JWT_SECRET_KEY` | ✅ | — | ≥32 chars; startup fails in production if weak |
| `JWT_ALGORITHM` | | `HS256` | `HS256` / `HS384` / `HS512` |
| `JWT_EXPIRE_MINUTES` | | `480` | |
| `BCRYPT_ROUNDS` | | `12` | Floor of 10 in production |
| `APP_ENV` | | `development` | `production` disables `/docs` and enables the guards |
| `LOG_LEVEL` | | `INFO` | |
| `ALLOWED_ORIGINS` | | `http://localhost:3000` | Comma-separated; `*` rejected in production |
| `MAX_UPLOAD_BYTES` | | `52428800` | 50 MiB |
| `SEED_ADMIN_USERNAME` | | `admin` | |
| `SEED_ADMIN_EMAIL` | | `admin@nyayavault.local` | |
| `SEED_ADMIN_PASSWORD` | | *(empty)* | **No admin is created if empty.** No default password exists anywhere in the repository. |
| `NEXT_PUBLIC_API_BASE_URL` | ✅ | `http://localhost:8000` | Compiled into the browser bundle |

---

## 4. Database migration commands

```bash
make migrate                          # docker compose exec backend alembic upgrade head
make migration m="add evidence table" # autogenerate a revision
make downgrade                        # alembic downgrade -1
make seed                             # python -m app.seed

# on the host
cd backend
alembic upgrade head
alembic current
alembic history --verbose
alembic downgrade base                # drop everything
```

`docker compose up` already runs `alembic upgrade head` followed by
`python -m app.seed` before starting the API, so a fresh clone needs no manual
migration step.

**Verified:** Alembic's `compare_metadata` reports zero drift between migration
`0001` and the SQLAlchemy models.

---

## 5. Test commands

```bash
make test           # inside the container
make test-local     # on the host

cd backend
python -m pytest -q                       # all 56 tests, ~6 seconds
python -m pytest -v                       # named
python -m pytest tests/test_documents.py  # one file
python -m pytest -k "integrity or audit"  # by keyword
```

Result at the time of writing:

```
56 passed in 5.85s
```

No PostgreSQL or MinIO instance is needed: the suite runs against SQLite with an
injected in-memory object-storage backend.

Frontend:

```bash
cd frontend
npm run typecheck    # tsc --noEmit — clean
npm run build        # next build — 8 routes, compiles clean
npm run lint
```

---

## 6. Known limitations

The full list with impact and remediation is in
[SECURITY.md §3](../SECURITY.md#3-known-weaknesses-in-this-prototype) and
[README § Known limitations](../README.md#known-limitations). The short version:

1. **Not production-ready.** No TLS, rate limiting, secrets manager, backups or DR.
2. **The audit chain is tamper-evident, not tamper-proof.** Database write access defeats it; external anchoring is the fix and is not in M0.
3. **The token is in `localStorage`**, so XSS would expose it. httpOnly cookies are the production answer.
4. **No token revocation.** A stolen token is valid until expiry, though deactivating the account blocks it on the next request.
5. **Case numbers are count-derived** and can collide under concurrency; the unique constraint catches it and the service retries.
6. **Downloads stream through the API.** Correct for auditability, not for scale.
7. **MinIO uses root credentials**; production needs a scoped service account.
8. **No antivirus scanning.** Format validation is not malware detection.
9. **No encryption at rest** beyond the underlying disk.
10. **No soft delete, retention policy or legal hold.**
11. **No frontend tests.**
12. **Offset pagination** drifts under concurrent writes.

### Deliberate deviations from the brief

Two, both additive and both stated here rather than buried:

**`case_assignments` table (an eighth table).** The brief lists six entities but
also requires *case-level* access control, which a role column alone cannot
express — it cannot say "this investigator may see this case". Adding the join
table now avoids rewriting every authorisation call site in M1. All six
specified entities exist exactly as described.

**Two extra endpoints.** `POST /documents/{id}/versions` is required by the
brief's own v1→v2→v3 example, which cannot be produced by the listed endpoints
alone. `GET /audit/verify` makes the hash-linked audit trail demonstrable rather
than merely present; the brief said "implement approximately" these endpoints.

### What was deliberately NOT built

Per the brief's scope boundary: no AI or LLM integration, no OCR, no vector
search (the extension is enabled, no embeddings are computed), no blockchain
anchoring, no digital signatures, no evidence workflow or chain-of-custody
transfer, and no court/evidence package generation.

---

## Verification performed

Not claimed — run:

- `pytest` → **56 passed**, covering all ten required scenarios plus token
  forgery, privilege escalation, path traversal, content-type spoofing, ZIP-as-
  DOCX, oversize uploads, search wildcard escaping, and audit-chain tamper and
  deletion detection.
- `alembic upgrade head` → applies cleanly; `compare_metadata` → **zero drift**.
- `python -m app.seed` → succeeds, and is idempotent on a second run.
- `tsc --noEmit` → **clean**.
- `next build` → **compiles clean**, 8 routes.
