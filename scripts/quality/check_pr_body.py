#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys


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


def check_pr_body(body: str) -> list[str]:
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
        if not record_path:
            errors.append("Acceptance Record path is required for a milestone candidate")
    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate required PR body governance evidence.")
    parser.add_argument("--body-env", default="PR_BODY", help="Environment variable containing PR body")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    body = os.environ.get(args.body_env, "")
    errors = check_pr_body(body)
    if errors:
        print(f"PR governance check failed with {len(errors)} issue(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PR review and acceptance metadata valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
