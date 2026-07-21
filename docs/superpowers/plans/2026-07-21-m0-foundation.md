# M0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible PCB-CDSO foundation that starts Web, API, MySQL, Redis and Celery from an empty environment and freezes the contracts needed by M1-M6.

**Architecture:** A React/Vite SPA calls a modular FastAPI application. SQLAlchemy/Alembic own MySQL state; Celery uses Redis for transport and writes durable facts to MySQL. Docker Compose controls dependency health and one-shot migration/bootstrap jobs.

**Tech Stack:** Python 3.12, FastAPI 0.139.2, SQLAlchemy 2.0.51, Alembic 1.18.5, Celery 5.6.3, redis-py 6.4.0, MySQL 8.4, Redis Server 7.4, Node 22, React 19.2.7, Vite 8.1.5, TypeScript 7.0.2, Ant Design 6.5.1, Vitest 4.1.10, Playwright 1.61.1, Docker Compose 2.27+

---

## File map

```text
package.json / package-lock.json        npm workspace and exact Web dependency graph
apps/web/                               login shell and Web tests
services/api/pyproject.toml             API direct dependencies and tool config
services/api/requirements.lock          complete Python runtime/test lock
services/api/src/pcb_cdso/              API, config, DB, bootstrap and tasks
services/api/alembic/                   schema migrations
contracts/openapi/openapi.json          generated API contract
contracts/schemas/*.schema.json         stable cross-agent envelopes
compose.yaml                            reproducible local deployment
infra/docker/                           API/Web container definitions
scripts/quality/verify_m0.py            empty-volume M0 smoke verifier
tests/contract/                         contract drift tests
tests/e2e/                              browser smoke
```

### Task 1: Freeze package manifests and machine contracts

**Files:**
- Create: `package.json`
- Create: `.nvmrc`
- Create: `services/api/pyproject.toml`
- Create: `contracts/schemas/error.schema.json`
- Create: `contracts/schemas/task.schema.json`
- Create: `contracts/schemas/revision.schema.json`
- Create: `contracts/schemas/idempotency.schema.json`
- Create: `tests/contract/test_json_schemas.py`

- [ ] **Step 1: Write the failing schema tests**

Create a standard-library unittest that loads all four schemas, validates `$schema`, `$id`, `type`, `required`, `properties`, and asserts the exact required fields for error and task envelopes.

- [ ] **Step 2: Verify RED**

Run `python -m unittest tests.contract.test_json_schemas -v` and expect failure because `contracts/schemas/` does not exist.

- [ ] **Step 3: Add minimal manifests and schemas**

Use npm workspaces `apps/*`, Node engine `>=22.12 <23`, Python `>=3.12,<3.13`, and the exact ADR versions. Error required fields are `code/message_key/field_path/details/request_id`; task required fields are `task_id/status/progress/stage/processed/total/error/retryable`.

- [ ] **Step 4: Verify GREEN and lock dependencies**

Run `npm install --package-lock-only`, generate `services/api/requirements.lock` from `pyproject.toml`, then rerun the schema test. Expected: all tests pass and both lock files exist.

- [ ] **Step 5: Commit**

Commit `build(m0): freeze dependencies and contracts`.

### Task 2: Build the FastAPI health and error foundation

**Files:**
- Create: `services/api/src/pcb_cdso/__init__.py`
- Create: `services/api/src/pcb_cdso/main.py`
- Create: `services/api/src/pcb_cdso/core/config.py`
- Create: `services/api/src/pcb_cdso/http/errors.py`
- Create: `services/api/src/pcb_cdso/http/request_id.py`
- Create: `services/api/src/pcb_cdso/http/health.py`
- Create: `services/api/tests/test_health.py`

- [ ] **Step 1: Write failing live/ready/request-ID tests**

Use FastAPI TestClient with injected dependency probes. Assert live never calls probes; ready returns 200 when both probes pass; ready returns 503 with `DEPENDENCY_UNAVAILABLE` when either fails; response header and error `request_id` match.

- [ ] **Step 2: Verify RED**

Run `python -m pytest services/api/tests/test_health.py -q`. Expected: import failure for `pcb_cdso.main`.

- [ ] **Step 3: Implement minimal API foundation**

Create a `create_app(settings, db_probe, redis_probe)` factory, request-ID middleware and stable exception handler. Keep dependency probes callable and injectable; do not embed test-only branches.

- [ ] **Step 4: Verify GREEN and generate OpenAPI**

Run the target test, then serialize `app.openapi()` with sorted keys to `contracts/openapi/openapi.json`.

- [ ] **Step 5: Commit**

Commit `feat(api): add health and error contract foundation`.

### Task 3: Add MySQL migration and idempotent administrator bootstrap

**Files:**
- Create: `services/api/alembic.ini`
- Create: `services/api/alembic/env.py`
- Create: `services/api/alembic/versions/0001_users_audit.py`
- Create: `services/api/src/pcb_cdso/db/base.py`
- Create: `services/api/src/pcb_cdso/db/session.py`
- Create: `services/api/src/pcb_cdso/db/models.py`
- Create: `services/api/src/pcb_cdso/bootstrap.py`
- Create: `services/api/tests/integration/test_bootstrap.py`

- [ ] **Step 1: Write failing integration tests**

Against `TEST_DATABASE_URL`, run Alembic upgrade, call bootstrap twice, and assert exactly one ADMIN, one `admin.bootstrap.created` event, an Argon2 hash that verifies, and no plaintext password in persisted values or captured logs.

- [ ] **Step 2: Verify RED**

Run `python -m pytest services/api/tests/integration/test_bootstrap.py -q`. Expected: missing migration/bootstrap implementation.

- [ ] **Step 3: Implement models, migration and command**

Create UUID user/audit identifiers, unique normalized email, `ADMIN/ENGINEER` check constraint, password hash, active flag and UTC timestamps. Bootstrap uses one transaction and treats an existing ADMIN as success without hashing the supplied password again.

- [ ] **Step 4: Verify GREEN and migration idempotence**

Run Alembic upgrade twice and the integration test. Then downgrade one revision and upgrade again in a disposable database.

- [ ] **Step 5: Commit**

Commit `feat(api): add initial migration and admin bootstrap`.

### Task 4: Add Redis and Celery task foundation

**Files:**
- Create: `services/api/src/pcb_cdso/tasks/celery_app.py`
- Create: `services/api/src/pcb_cdso/tasks/smoke.py`
- Create: `services/api/src/pcb_cdso/http/tasks.py`
- Create: `services/api/tests/integration/test_tasks.py`

- [ ] **Step 1: Write failing task tests**

Assert a real worker consumes `smoke`, returns `SUCCEEDED`, preserves request correlation, and two POST requests with the same scoped `Idempotency-Key` return the same task id.

- [ ] **Step 2: Verify RED**

Run `python -m pytest services/api/tests/integration/test_tasks.py -q`. Expected: missing task application.

- [ ] **Step 3: Implement minimal Celery app and development endpoint**

Configure JSON serialization, UTC, explicit time limits and Redis URLs from Settings. The smoke task returns its correlation ID; no business task is introduced.

- [ ] **Step 4: Verify GREEN**

Start the test worker and run the integration file. Expected: task reaches `SUCCEEDED` within 30 seconds and duplicate key returns the original id.

- [ ] **Step 5: Commit**

Commit `feat(worker): add celery smoke task foundation`.

### Task 5: Build the bilingual themed login shell

**Files:**
- Create: `apps/web/index.html`
- Create: `apps/web/package.json`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/App.test.tsx`
- Create: `apps/web/src/i18n.ts`
- Create: `apps/web/src/theme.ts`
- Create: `apps/web/src/styles.css`

- [ ] **Step 1: Write failing UI tests**

Assert default Chinese labels, English switch, light/dark token change, persisted preferences, disabled M0 submit behavior, and an accessible explanation that identity activates in M1.

- [ ] **Step 2: Verify RED**

Run `npm run test --workspace @pcb-cdso/web -- --run`. Expected: missing app modules.

- [ ] **Step 3: Implement the minimal shell**

Use Ant Design ConfigProvider tokens and a focused login panel. Store only locale/theme in localStorage. Do not add navigation or business placeholders.

- [ ] **Step 4: Verify GREEN, typecheck and build**

Run Web tests, `npm run typecheck --workspace @pcb-cdso/web`, and `npm run build --workspace @pcb-cdso/web`.

- [ ] **Step 5: Commit**

Commit `feat(web): add bilingual themed login shell`.

### Task 6: Compose the runtime and empty-environment verifier

**Files:**
- Create: `compose.yaml`
- Create: `.env.example`
- Create: `infra/docker/api.Dockerfile`
- Create: `infra/docker/web.Dockerfile`
- Create: `infra/docker/nginx.conf`
- Create: `.dockerignore`
- Create: `scripts/quality/verify_m0.py`
- Create: `tests/e2e/login-shell.spec.ts`

- [ ] **Step 1: Write failing compose-structure and smoke tests**

The verifier must parse `docker compose config`, require services `mysql/redis/migrate/bootstrap-admin/api/worker/web`, reject default production secrets, and probe Web, live, ready and OpenAPI after startup.

- [ ] **Step 2: Verify RED**

Run `python scripts/quality/verify_m0.py --check-config-only`. Expected: missing `compose.yaml`.

- [ ] **Step 3: Add Dockerfiles, Compose and health checks**

Use named volumes, non-root application containers, dependency health conditions, one-shot migration/bootstrap services, API port 8000 and Web port 3000. `.env.example` contains clearly local non-secret placeholders and instructions to replace them.

- [ ] **Step 4: Verify GREEN from empty volumes**

Run config-only, then `docker compose down --volumes`, `docker compose up --build --wait`, full verifier, Playwright smoke, restart, and verifier again. Save image digests and logs without secrets.

- [ ] **Step 5: Commit**

Commit `build(m0): add reproducible compose runtime`.

### Task 7: Unify quality commands and GitHub Actions

**Files:**
- Modify: `Makefile`
- Modify: `README.md`
- Modify: `.github/workflows/governance.yml`
- Create: `.github/workflows/build.yml`
- Create: `scripts/quality/check_secrets.py`
- Create: `tests/governance/test_check_secrets.py`

- [ ] **Step 1: Write failing command/security tests**

Test that tracked text rejects known secret-key names with non-example values and that Makefile exposes `api-test/web-test/contract/integration/build/m0-smoke/verify`.

- [ ] **Step 2: Verify RED**

Run the new governance test. Expected: missing secret checker and missing targets.

- [ ] **Step 3: Implement commands and CI jobs**

Keep `verify` deterministic and non-destructive: governance, secret scan, unit/contract, lint/typecheck and builds. Keep destructive empty-volume smoke as explicit `m0-smoke`, not a default developer command.

- [ ] **Step 4: Verify GREEN**

Run `make verify`, workflow YAML parsing, and `git diff --check` on Windows. CI uses Python 3.12 and Node 22.

- [ ] **Step 5: Commit**

Commit `ci(m0): enforce application foundation gates`.

### Task 8: Produce M0 evidence and acceptance candidate

**Files:**
- Create: `fixtures/acceptance/M0/1.0.0/manifest.json`
- Create: `artifacts/acceptance/M0/*.txt`
- Create: `docs/testing/acceptance/M0-acceptance.md`
- Modify: `docs/testing/plans/M0-test-plan.md`
- Modify: `docs/milestones/M0-repository-baseline.md`

- [ ] **Step 1: Run every required command on the candidate**

Run governance, API/Web tests, contract, integration, build, empty-volume smoke and verify. Capture exit codes, versions, lock hashes and image digests.

- [ ] **Step 2: Record negative evidence**

Stop Redis and prove ready=503/live=200; rerun bootstrap and prove row counts unchanged; scan logs for the injected password; regenerate OpenAPI and prove no diff.

- [ ] **Step 3: Create signed software fixture manifest**

List evidence files and actual SHA-256 values, producer `Implementer`, software verifier `Test Agent`, expert approver `null`, and signed record path `docs/testing/acceptance/M0-acceptance.md`.

- [ ] **Step 4: Update plan/results and acceptance record**

Change each executed Test Plan result from `not_run` to `pass`, reference real evidence paths, set the Acceptance Record Candidate SHA to the tested commit, and obtain Product Sign-off. Do not mark the milestone `verified` before these facts exist.

- [ ] **Step 5: Run the acceptance gate and commit**

Run `python scripts/quality/check_governance.py --acceptance-ready M0`; expected exit 0. Commit `docs(m0): record foundation acceptance`.
