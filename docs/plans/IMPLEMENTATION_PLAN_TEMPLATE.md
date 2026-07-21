# {{feature_name}} Implementation Plan

> Agentic workers must follow `AGENTS.md`, use an isolated branch/worktree, and execute every checkbox with fresh evidence.

**Goal:** {{one_observable_result}}

**Source Spec:** {{repository_relative_path_and_version}}

**Base SHA:** {{40_character_sha}}

**Allowed Paths:** {{explicit_paths}}

**Architecture:** {{two_or_three_sentences}}

---

### Task 1: {{small_component}}

**Files:**
- Create: `{{exact_path}}`
- Modify: `{{exact_path}}`
- Test: `{{exact_test_path}}`

- [ ] Write one failing test with the exact expected behavior.
- [ ] Run `{{exact_test_command}}`; expected result is FAIL because {{missing_behavior}}.
- [ ] Implement the minimum code shown in this plan to satisfy that behavior.
- [ ] Run `{{exact_test_command}}`; expected result is PASS.
- [ ] Run `{{affected_suite_command}}`; expected result is all tests PASS.
- [ ] Refactor without behavior change and rerun the suite.
- [ ] Update the linked contract/documentation.
- [ ] Commit with `{{conventional_commit_message}}`.

## Completion verification

List exact governance, formatting, lint, type, contract, integration, E2E, build and `git diff --check` commands required for this feature.

