# PCB-CDSO Development Governance Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the repository-level SOP, agent contract, documentation templates, GitHub collaboration files, milestone specifications, and machine-checkable governance baseline required to develop PCB-CDSO v0.6 with SDD and TDD.

**Architecture:** Product truth lives in the approved PRD; approved ADRs, milestone specs, feature specs, machine contracts, fixtures, tests, and implementation plans refine it in that order. GitHub is the only merge authority, each agent writes in an isolated branch/worktree, and a small Python governance checker enforces required files, metadata, and forbidden unfinished markers in CI.

**Tech Stack:** Markdown, Git/GitHub, GitHub Actions, Python 3.12-compatible standard library, Make, JSON/JSON Schema, YAML.

---

## Planned file map

```text
AGENTS.md                                      all-agent constitution
README.md                                      human/agent entry point
Makefile                                       platform-neutral quality commands
.editorconfig                                  text defaults
.gitattributes                                 LF and generated-file rules
.gitignore                                     local/runtime exclusions
.github/CODEOWNERS                             review ownership baseline
.github/pull_request_template.md               PR evidence contract
.github/ISSUE_TEMPLATE/feature.yml             feature intake
.github/ISSUE_TEMPLATE/bug.yml                 defect intake
.github/workflows/governance.yml               governance CI
docs/sop/DEVELOPMENT_SOP.md                    full development guide
docs/architecture/adr/ADR_TEMPLATE.md          decision template
docs/milestones/M0-M5-*.md                     executable phase boundaries
docs/specs/FEATURE_SPEC_TEMPLATE.md             behavior spec template
docs/plans/IMPLEMENTATION_PLAN_TEMPLATE.md      task plan template
docs/testing/TEST_PLAN_TEMPLATE.md              test design template
docs/testing/DATA_AND_FIXTURE_REQUIREMENTS.md   required data matrix
docs/testing/ACCEPTANCE_RECORD_TEMPLATE.md      evidence record
docs/handoffs/AGENT_HANDOFF_TEMPLATE.md         cross-agent handoff
contracts/seeds/seed-manifest.schema.json       seed governance schema
fixtures/README.md                              fixture rules
scripts/quality/check_governance.py             machine governance check
tests/governance/test_check_governance.py       checker regression tests
```

### Task 1: Establish repository text and command baseline

**Files:**
- Create: `README.md`
- Create: `Makefile`
- Create: `.editorconfig`
- Create: `.gitattributes`
- Create: `.gitignore`

- [ ] **Step 1: Write repository entry documentation**

Document the product boundary, truth-source order, directory map, prerequisites, and the exact `make governance`, `make test`, `make verify`, and `make acceptance` commands. State that application commands remain unavailable until M0 selects the package managers.

- [ ] **Step 2: Add platform-neutral command entry points**

```make
PYTHON ?= python

.PHONY: governance test verify acceptance
governance:
	$(PYTHON) scripts/quality/check_governance.py

test:
	$(PYTHON) -m unittest discover -s tests -p "test_*.py" -v

verify: governance test

acceptance:
	$(PYTHON) scripts/quality/check_governance.py --acceptance-ready
```

- [ ] **Step 3: Normalize text files**

Set UTF-8, final newline, spaces by default, tabs only for `Makefile`, and LF for source/config. Ignore `.env`, IDE state, caches, coverage, build output, generated exports, local databases, and fixture scratch data without ignoring committed golden fixtures.

- [ ] **Step 4: Run baseline command**

Run: `make governance`

Expected: FAIL because the governance checker has not yet been created. This is the planned red state.

- [ ] **Step 5: Commit**

```bash
git add README.md Makefile .editorconfig .gitattributes .gitignore
git commit -m "chore: establish repository command baseline"
```

### Task 2: Create the unified agent contract

**Files:**
- Create: `AGENTS.md`
- Create: `docs/handoffs/AGENT_HANDOFF_TEMPLATE.md`

- [ ] **Step 1: Define mandatory startup order**

Require every agent to read `AGENTS.md`, the approved milestone spec, the feature spec, linked ADRs, contracts, and tests before editing. Define the truth hierarchy and require explicit reporting when sources conflict.

- [ ] **Step 2: Define ownership and isolation**

Specify one Issue, one branch, one worktree, and one active file owner. Prohibit direct writes to `main`, shared worktrees, unapproved contract changes, deleting tests to pass CI, hidden scope expansion, secrets, and destructive Git operations.

- [ ] **Step 3: Define agent task envelope**

Every dispatched task must include: objective, allowed paths, prohibited paths, source spec, dependency SHA, required tests, acceptance command, branch name, and completion format.

- [ ] **Step 4: Define handoff evidence**

The handoff template must record agent/tool, Issue, branch, worktree, base SHA, head SHA, files changed, commands with exit status, decisions, risks, unresolved blockers, and recommended next action.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md docs/handoffs/AGENT_HANDOFF_TEMPLATE.md
git commit -m "docs: define unified multi-agent protocol"
```

### Task 3: Write the complete SDD/TDD development SOP

**Files:**
- Create: `docs/sop/DEVELOPMENT_SOP.md`

- [ ] **Step 1: Define preflight and Definition of Ready**

Cover GitHub repository creation, branch protection, local tools, environment files, contract/fixture readiness, Issue creation, spec approval, dependency checks, and clean worktree verification.

- [ ] **Step 2: Define the SDD cycle**

Document PRD to ADR to milestone spec to feature spec to implementation plan. Include status transitions `draft -> approved -> implementing -> verified -> superseded` and who may transition each state.

- [ ] **Step 3: Define the TDD cycle**

Require red-green-refactor evidence, exact test selection by risk, regression tests for defects, contract-first API changes, migrations with rollback verification, and golden-fixture checksum handling.

- [ ] **Step 4: Define PR, CI, review, merge, and release**

Include Conventional Commits, PR size guidance, evidence checklist, two-stage review (spec then code quality), CI gates, squash merge, release tag format, rollback, and post-merge smoke tests.

- [ ] **Step 5: Define multi-agent orchestration**

Describe Orchestrator, Spec Agent, Implementer, Test Agent, Reviewer, and Acceptance Agent. Include safe parallelization, contract-first sequencing, file leases, merge queues, stale branch handling, conflict escalation, context packets, and handoffs.

- [ ] **Step 6: Define stage acceptance**

For M0-M5, list Definition of Ready, exit evidence, mandatory tests, demo path, data requirements, and stop/go decision. Keep software verification separate from expert validation.

- [ ] **Step 7: Commit**

```bash
git add docs/sop/DEVELOPMENT_SOP.md
git commit -m "docs: add SDD and TDD development SOP"
```

### Task 4: Add reusable specification and evidence templates

**Files:**
- Create: `docs/architecture/adr/ADR_TEMPLATE.md`
- Create: `docs/specs/FEATURE_SPEC_TEMPLATE.md`
- Create: `docs/plans/IMPLEMENTATION_PLAN_TEMPLATE.md`
- Create: `docs/testing/TEST_PLAN_TEMPLATE.md`
- Create: `docs/testing/ACCEPTANCE_RECORD_TEMPLATE.md`

- [ ] **Step 1: Add ADR template**

Require context, decision, alternatives, consequences, migration/rollback, affected contracts, validation evidence, owner, status, and supersession link.

- [ ] **Step 2: Add feature spec template**

Require user outcome, non-goals, domain vocabulary, state table, normal/failure flows, validation rules, API/data changes, permissions, observability, acceptance scenarios, and open questions that block approval.

- [ ] **Step 3: Add implementation plan template**

Require exact files, small checkbox steps, failing test, expected failure, minimal implementation, passing command, refactor, documentation, and commit for each task.

- [ ] **Step 4: Add test plan and acceptance record**

Map each acceptance criterion to unit, property, contract, integration, E2E, visual, performance, or expert validation. Record environment, SHA, fixture checksums, commands, results, evidence paths, deviations, and sign-off.

- [ ] **Step 5: Commit**

```bash
git add docs/architecture/adr docs/specs docs/plans docs/testing
git commit -m "docs: add specification and acceptance templates"
```

### Task 5: Define required product data and fixtures

**Files:**
- Create: `docs/testing/DATA_AND_FIXTURE_REQUIREMENTS.md`
- Create: `contracts/seeds/seed-manifest.schema.json`
- Create: `fixtures/README.md`

- [ ] **Step 1: Inventory required data**

Specify product/process seeds, bilingual question registry, process environment rules, coefficient tables, users/roles, project hierarchy, weather CSV, static calculation baselines, 24-hour dynamic baseline, invalid inputs, concurrency fixtures, CSV golden files, and UI screenshot baselines.

- [ ] **Step 2: Define verification levels**

Use `UNVERIFIED`, `SOFTWARE_VERIFIED`, and `EXPERT_VERIFIED`. Require source, version, owner, checksum, applicable product/process, effective date, and validation evidence. Prohibit promotion to expert verified without a named sign-off record.

- [ ] **Step 3: Add seed manifest schema**

Require `schemaVersion`, `datasetId`, `datasetVersion`, `verificationStatus`, `source`, `owner`, `checksum`, `dependencies`, `records`, and bilingual labels. Set `additionalProperties` to false at the root.

- [ ] **Step 4: Define fixture immutability**

Golden fixtures are immutable after approval. Changes require a new version, regenerated checksum, linked Issue/ADR, updated expected result, and explicit review by the affected domain owner.

- [ ] **Step 5: Validate JSON schema syntax**

Run:

```bash
python -c "import json; json.load(open('contracts/seeds/seed-manifest.schema.json', encoding='utf-8')); print('schema json valid')"
```

Expected: `schema json valid`

- [ ] **Step 6: Commit**

```bash
git add docs/testing/DATA_AND_FIXTURE_REQUIREMENTS.md contracts/seeds fixtures/README.md
git commit -m "docs: define governed data and fixture requirements"
```

### Task 6: Add M0-M5 milestone specifications

**Files:**
- Create: `docs/milestones/M0-repository-baseline.md`
- Create: `docs/milestones/M1-identity-template-project.md`
- Create: `docs/milestones/M2-controlled-data-collection.md`
- Create: `docs/milestones/M3-static-calculation.md`
- Create: `docs/milestones/M4-weather-simulation-forecast.md`
- Create: `docs/milestones/M5-results-export-delivery.md`

- [ ] **Step 1: Apply a common milestone structure**

Each file must include metadata, objective, included/excluded scope, dependencies, deliverables, contract changes, required data, Definition of Ready, test matrix, quality gate, demo script, Definition of Done, evidence paths, risks, and rollback/stop conditions.

- [ ] **Step 2: Populate M0-M2 from PRD**

M0 covers clean startup and governance; M1 covers first admin, engineer accounts, immutable template snapshots, and project ownership; M2 covers eight-stage question flow, strong validation, process coverage, revisions, and save/resume.

- [ ] **Step 3: Populate M3-M5 from PRD**

M3 covers traceable static formulas and aggregation; M4 covers weather, UTC axis, three-year simulation, seven-day forecast, and task correctness; M5 covers result tabs, zone drill-down, CSV semantics, bilingual themes, deployment, and final acceptance.

- [ ] **Step 4: Cross-check requirements**

Run a PRD-to-milestone traceability review. Every P0 bullet in `docs/product/PRD_v0.6.md` must appear in exactly one primary milestone and may list secondary milestones as dependencies.

- [ ] **Step 5: Commit**

```bash
git add docs/milestones
git commit -m "docs: define executable M0 through M5 milestones"
```

### Task 7: Add GitHub collaboration policy

**Files:**
- Create: `.github/CODEOWNERS`
- Create: `.github/pull_request_template.md`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/ISSUE_TEMPLATE/feature.yml`
- Create: `.github/ISSUE_TEMPLATE/bug.yml`

- [ ] **Step 1: Define ownership placeholders as teams, not individuals**

Use repository team handles for product/specs, API/contracts, UI, calculations/data, infrastructure, and acceptance. Document that the repository administrator replaces example handles before enabling required CODEOWNERS reviews.

- [ ] **Step 2: Add structured Issues**

Feature intake requires source milestone/spec, outcome, scope, acceptance criteria, allowed paths, dependencies, data, and risk. Bug intake requires environment, SHA, fixture, reproduction, expected/actual result, severity, and evidence.

- [ ] **Step 3: Add PR evidence contract**

Require linked Issue/Spec, change summary, non-goals, test commands/results, screenshots or CSV evidence when relevant, migrations, contract changes, risk, rollback, and handoff status. Include checkboxes that tests were not deleted or skipped to obtain green CI.

- [ ] **Step 4: Commit**

```bash
git add .github/CODEOWNERS .github/ISSUE_TEMPLATE .github/pull_request_template.md
git commit -m "chore: add GitHub issue and pull request governance"
```

### Task 8: Implement and test governance CI

**Files:**
- Create: `scripts/quality/check_governance.py`
- Create: `tests/governance/test_check_governance.py`
- Create: `.github/workflows/governance.yml`

- [ ] **Step 1: Write failing checker tests**

Test that the checker fails for a missing required file, invalid document status, forbidden unfinished markers in approved documents, malformed JSON, and an acceptance-ready run without all milestone files. Test a minimal valid temporary repository passes.

- [ ] **Step 2: Run tests and confirm red**

Run: `python -m unittest tests.governance.test_check_governance -v`

Expected: FAIL because `scripts.quality.check_governance` does not exist.

- [ ] **Step 3: Implement the minimum checker**

Use only the Python standard library. Check required paths, UTF-8 decoding, JSON syntax, allowed metadata statuses, forbidden unfinished markers in approved files, and optional `--acceptance-ready` requirements. Print each failure and exit 1; print a concise success summary and exit 0 otherwise.

- [ ] **Step 4: Run tests and full verification**

Run:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/quality/check_governance.py
```

Expected: all tests pass; checker reports governance baseline valid.

- [ ] **Step 5: Add GitHub Actions**

Run on pull requests and pushes to `main`, using Python 3.12. Execute `python scripts/quality/check_governance.py` and `python -m unittest discover -s tests -p "test_*.py" -v`. Set least-privilege read-only contents permission and concurrency cancellation by branch.

- [ ] **Step 6: Commit**

```bash
git add scripts/quality tests/governance .github/workflows/governance.yml
git commit -m "ci: enforce development governance baseline"
```

### Task 9: Final reader test, verification, and baseline tag

**Files:**
- Modify only documents that fail reader testing or machine checks.
- Create: `docs/testing/governance-pack-acceptance-2026-07-21.md`

- [ ] **Step 1: Run a context-free reader review**

Ask an independent reviewer to determine how to start M0, dispatch two parallel agents safely, prepare static/weather fixtures, prove a milestone passed, resolve conflicting specs, and recover from a failed PR. Fix any answer that cannot be derived from repository files.

- [ ] **Step 2: Run fresh machine verification**

```bash
python scripts/quality/check_governance.py
python -m unittest discover -s tests -p "test_*.py" -v
git diff --check
git status --short
```

Expected: checker passes, all tests pass, `git diff --check` has no output, and status lists only the acceptance record before its commit.

- [ ] **Step 3: Record evidence**

Write commands, exit codes, repository SHA, reviewed files, reader-test findings, deviations, and final decision in the acceptance record.

- [ ] **Step 4: Commit and tag**

```bash
git add docs/testing/governance-pack-acceptance-2026-07-21.md
git commit -m "docs: accept development governance pack"
git tag -a governance-v0.1.0 -m "PCB-CDSO development governance baseline"
```

- [ ] **Step 5: Verify final state**

Run:

```bash
git status --short --branch
git log --oneline --decorate -10
git tag --list "governance-*"
```

Expected: clean `main`, governance commits visible, and tag `governance-v0.1.0` present.

