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
                "PR_BODY": "stale environment body",
                "PR_HEAD_SHA": "a" * 40,
                "GITHUB_EVENT_PATH": str(event_path),
            }
            with patch.dict(os.environ, environment, clear=False):
                self.assertEqual((VALID_BODY, "b" * 40), load_pr_context("PR_BODY", "PR_HEAD_SHA"))

    def test_complete_independent_reviews_pass(self) -> None:
        self.assertEqual([], check_pr_body(VALID_BODY))

    def test_complete_independent_reviews_pass_with_crlf(self) -> None:
        self.assertEqual([], check_pr_body(VALID_BODY.replace("\n", "\r\n")))

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


# Solo-developer exception body per SOP Appendix A (v0.2.0).
# Triggered by a declaration line in the PR body. Identities below are
# intentionally identical to prove Appendix A bypasses the independence check.
SOLO_DEV_BODY = """
## Agent Handoff
- Implementer / Tool：limingfeng
- Head SHA：bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
- Handoff path：docs/handoffs/m0-m1-wave1.md
- SOP Appendix A：applies

## Spec Review
- Reviewer / Tool：limingfeng
- Reviewed SHA：bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
- 结论：APPROVE

## Code Quality Review
- Reviewer / Tool：limingfeng
- Reviewed SHA：bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
- 结论：APPROVE

## Acceptance
- Candidate SHA / Tag：aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
- Acceptance Agent：limingfeng
- Acceptance Record path：docs/testing/acceptance/M0-acceptance.md
- 状态：GO
"""


class SoloDevAppendixATest(unittest.TestCase):
    def test_solo_dev_with_appendix_a_skips_identity_independence(self) -> None:
        """SOP Appendix A 豁免三身份独立;单人双角色签字可通过。

        附录 A 声明行格式:`- SOP Appendix A:applies`
        (label 精确匹配,值为 'applies')。
        """
        errors = check_pr_body(SOLO_DEV_BODY)
        identity_errors = [e for e in errors if "independent" in e]
        self.assertEqual(
            [],
            identity_errors,
            f"Appendix A must skip identity independence check; got {identity_errors}",
        )

    def test_solo_dev_without_appendix_a_still_requires_independence(self) -> None:
        """无附录 A 声明时,同身份字符串仍触发独立检查。"""
        body = SOLO_DEV_BODY.replace("- SOP Appendix A：applies\n", "")
        errors = check_pr_body(body)
        self.assertTrue(any("independent" in e for e in errors))

    def test_solo_dev_appendix_a_must_use_exact_phrase(self) -> None:
        """附录 A 声明值必须精确为 'applies',防误触发。"""
        body = SOLO_DEV_BODY.replace("- SOP Appendix A：applies", "- SOP Appendix A：maybe")
        errors = check_pr_body(body)
        self.assertTrue(any("independent" in e for e in errors))


class HistoricalCandidateShaTest(unittest.TestCase):
    def test_candidate_sha_may_be_historical_existing_commit(self) -> str | None:
        """Acceptance Candidate SHA 允许是仓库历史 commit,不强制等于 PR head。

        场景:M0 实现在 PR #1 合并(候选 3591987),验收记录在本 PR 合并。
        Reviewed SHA 仍必须等于 PR head(审查当前代码)。
        """
        errors = check_pr_body(SOLO_DEV_BODY, expected_head_sha="b" * 40)
        candidate_errors = [e for e in errors if "Candidate SHA" in e and "head" in e]
        self.assertEqual(
            [],
            candidate_errors,
            f"Candidate SHA mismatch with PR head must not be an error; got {candidate_errors}",
        )
        return None

    def test_reviewed_sha_still_must_equal_pr_head(self) -> None:
        """附录 A 不豁免 Reviewed SHA == PR head 检查(审查必须针对当前 PR 代码)。"""
        errors = check_pr_body(SOLO_DEV_BODY, expected_head_sha="c" * 40)
        self.assertTrue(any("current PR head" in e for e in errors))

    def test_candidate_sha_must_still_be_40_char_hex(self) -> None:
        """Candidate SHA 仍必须是 40 字符 hex(格式校验不豁免)。"""
        body = SOLO_DEV_BODY.replace(
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "not-a-sha"
        )
        errors = check_pr_body(body)
        self.assertTrue(any("40-character" in e for e in errors))
