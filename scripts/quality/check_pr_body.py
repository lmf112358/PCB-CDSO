#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$", re.IGNORECASE)


def section(body: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}.*$", body, re.MULTILINE)
    if not match:
        return ""
    next_heading = re.search(r"^##\s+", body[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(body)
    return body[match.end() : end]


def field(text: str, label: str) -> str:
    match = re.search(
        rf"^-[ \t]*{re.escape(label)}[ \t]*[：:][ \t]*([^\r\n]*)$",
        text,
        re.MULTILINE,
    )
    return match.group(1).strip() if match else ""


def check_pr_body(body: str, expected_head_sha: str | None = None) -> list[str]:
    errors: list[str] = []
    handoff = section(body, "Agent Handoff")
    spec_review = section(body, "Spec Review")
    quality_review = section(body, "Code Quality Review")
    acceptance = section(body, "Acceptance")

    implementer = field(handoff, "Implementer / Tool")
    handoff_path = field(handoff, "Handoff path")
    if not implementer:
        errors.append("Agent Handoff requires Implementer / Tool")
    if not handoff_path:
        errors.append("Agent Handoff requires Handoff path")

    reviewers: list[str] = []
    for label, review in (("Spec Review", spec_review), ("Code Quality Review", quality_review)):
        reviewer = field(review, "Reviewer / Tool")
        reviewed_sha = field(review, "Reviewed SHA")
        conclusion = field(review, "结论")
        if not reviewer:
            errors.append(f"{label} reviewer is required")
        else:
            reviewers.append(reviewer.casefold())
        if not SHA_PATTERN.fullmatch(reviewed_sha):
            errors.append(f"{label} requires a 40-character Reviewed SHA")
        elif expected_head_sha and reviewed_sha.lower() != expected_head_sha.lower():
            errors.append(f"{label} Reviewed SHA must equal the current PR head")
        if conclusion != "APPROVE":
            errors.append(f"{label} conclusion must be APPROVE")

    identities = ([implementer.casefold()] if implementer else []) + reviewers
    if len(identities) != len(set(identities)):
        errors.append("Implementer and both reviewers must be independent identities")

    acceptance_status = field(acceptance, "状态")
    if acceptance_status not in {"not-required", "GO", "NO-GO", "CONDITIONAL-GO", "EXPIRED"}:
        errors.append("Acceptance status is missing or invalid")
    if acceptance_status != "not-required":
        candidate = field(acceptance, "Candidate SHA / Tag")
        record_path = field(acceptance, "Acceptance Record path")
        if not SHA_PATTERN.fullmatch(candidate):
            errors.append("Candidate SHA must be a 40-character commit SHA")
        elif expected_head_sha and candidate.lower() != expected_head_sha.lower():
            errors.append("Candidate SHA must equal the current PR head")
        if not record_path:
            errors.append("Acceptance Record path is required for a milestone candidate")
        elif not re.fullmatch(r"docs/testing/acceptance/M[0-6]-acceptance\.md", record_path):
            errors.append("Acceptance Record path must use the standard milestone path")
    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate required PR body governance evidence.")
    parser.add_argument("--body-env", default="PR_BODY", help="Environment variable containing PR body")
    parser.add_argument("--head-sha-env", default="PR_HEAD_SHA", help="Environment variable containing PR head SHA")
    parser.add_argument("--validate-acceptance-root", type=Path, help="Run milestone acceptance validation in this repository")
    return parser.parse_args(argv)


def load_pr_context(body_env: str, head_sha_env: str) -> tuple[str, str]:
    body = os.environ.get(body_env, "")
    head_sha = os.environ.get(head_sha_env, "")
    if body and head_sha:
        return body, head_sha

    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path:
        return body, head_sha
    try:
        event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return body, head_sha

    pull_request = event.get("pull_request", {})
    if not isinstance(pull_request, dict):
        return body, head_sha
    event_body = pull_request.get("body")
    event_head = pull_request.get("head", {})
    event_sha = event_head.get("sha") if isinstance(event_head, dict) else None
    return body or (event_body if isinstance(event_body, str) else ""), head_sha or (
        event_sha if isinstance(event_sha, str) else ""
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    body, head_sha = load_pr_context(args.body_env, args.head_sha_env)
    errors = check_pr_body(body, expected_head_sha=head_sha or None)
    acceptance = section(body, "Acceptance")
    acceptance_status = field(acceptance, "状态")
    record_path = field(acceptance, "Acceptance Record path")
    record_match = re.fullmatch(r"docs/testing/acceptance/(M[0-6])-acceptance\.md", record_path)
    if args.validate_acceptance_root and acceptance_status != "not-required" and record_match and not errors:
        milestone = record_match.group(1)
        checker = Path(__file__).with_name("check_governance.py")
        result = subprocess.run(
            [sys.executable, str(checker), "--root", str(args.validate_acceptance_root), "--acceptance-ready", milestone],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            errors.append(f"{milestone} acceptance-ready failed: {result.stdout.strip() or result.stderr.strip()}")
    if errors:
        print(f"PR governance check failed with {len(errors)} issue(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PR review and acceptance metadata valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
