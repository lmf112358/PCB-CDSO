from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.quality.check_pr_body import check_pr_body, load_pr_context


VALID_BODY = """
## 关联事实
- Issue：GH-101
- Base SHA：aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

## Agent Handoff
- Implementer / Tool：Coder / Coder
- Head SHA：bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
- Handoff path：docs/handoffs/GH-101.md

## Spec Review（由独立 Reviewer 填写）
- Reviewer / Tool：Alice / Codex
- Reviewed SHA：bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
- 结论：APPROVE

## Code Quality Review（由独立 Reviewer 填写）
- Reviewer / Tool：Bob / Claude Code
- Reviewed SHA：bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
- 结论：APPROVE

## Acceptance（阶段候选时填写）
- Candidate SHA / Tag：
- Acceptance Agent：
- Acceptance Record path：
- 状态：not-required
"""


class PullRequestBodyTest(unittest.TestCase):
    def test_load_pr_context_falls_back_to_github_event_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            event_path = Path(directory) / "event.json"
            event_path.write_text(
                json.dumps(
                    {
                        "pull_request": {
                            "body": VALID_BODY,
                            "head": {"sha": "b" * 40},
                        }
                    }
                ),
                encoding="utf-8",
            )
            environment = {
                "PR_BODY": "",
                "PR_HEAD_SHA": "",
                "GITHUB_EVENT_PATH": str(event_path),
            }
            with patch.dict(os.environ, environment, clear=False):
                self.assertEqual((VALID_BODY, "b" * 40), load_pr_context("PR_BODY", "PR_HEAD_SHA"))

    def test_complete_independent_reviews_pass(self) -> None:
        self.assertEqual([], check_pr_body(VALID_BODY))

    def test_missing_review_identity_and_approval_fail(self) -> None:
        body = VALID_BODY.replace("Alice / Codex", "").replace("- 结论：APPROVE", "- 结论：REQUEST-CHANGES", 1)
        errors = check_pr_body(body)
        self.assertTrue(any("Spec Review reviewer" in error for error in errors))
        self.assertTrue(any("Spec Review conclusion" in error for error in errors))

    def test_reviewers_must_be_independent(self) -> None:
        body = VALID_BODY.replace("Bob / Claude Code", "Alice / Codex")
        errors = check_pr_body(body)
        self.assertTrue(any("independent" in error for error in errors))

    def test_reviewed_sha_must_equal_pr_head(self) -> None:
        errors = check_pr_body(VALID_BODY, expected_head_sha="c" * 40)
        self.assertTrue(any("current PR head" in error for error in errors))

    def test_candidate_acceptance_requires_go_record(self) -> None:
        body = VALID_BODY.replace("- 状态：not-required", "- 状态：GO")
        errors = check_pr_body(body)
        self.assertTrue(any("Acceptance Record path" in error for error in errors))
        self.assertTrue(any("Candidate SHA" in error for error in errors))

    def test_candidate_record_path_must_use_standard_milestone_path(self) -> None:
        body = (
            VALID_BODY.replace("- 状态：not-required", "- 状态：GO")
            .replace("- Candidate SHA / Tag：", f"- Candidate SHA / Tag：{'b' * 40}")
            .replace("- Acceptance Record path：", "- Acceptance Record path：docs/random.md")
        )
        errors = check_pr_body(body)
        self.assertTrue(any("standard milestone path" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
