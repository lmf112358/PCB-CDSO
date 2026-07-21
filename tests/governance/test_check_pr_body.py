from __future__ import annotations

import unittest

from scripts.quality.check_pr_body import check_pr_body


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

    def test_candidate_acceptance_requires_go_record(self) -> None:
        body = VALID_BODY.replace("- 状态：not-required", "- 状态：GO")
        errors = check_pr_body(body)
        self.assertTrue(any("Acceptance Record path" in error for error in errors))
        self.assertTrue(any("Candidate SHA" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
