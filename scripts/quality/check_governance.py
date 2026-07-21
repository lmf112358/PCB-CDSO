#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


REQUIRED_FILES = (
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/product/PRD_v0.6.md",
    "docs/sop/DEVELOPMENT_SOP.md",
    "docs/testing/DATA_AND_FIXTURE_REQUIREMENTS.md",
    "contracts/seeds/seed-manifest.schema.json",
    "fixtures/README.md",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/ISSUE_TEMPLATE/bug.yml",
)

MILESTONE_FILES = (
    "M0-repository-baseline.md",
    "M1-identity-template-project.md",
    "M2-controlled-data-collection.md",
    "M3-static-calculation.md",
    "M4-weather-simulation-forecast.md",
    "M5-results-export-delivery.md",
)

ALLOWED_STATUSES = {"draft", "approved", "implementing", "verified", "superseded"}
STATUS_PATTERN = re.compile(r"\|\s*状态\s*\|\s*([a-z_]+)\s*\|", re.IGNORECASE)
UNFINISHED_PATTERNS = (
    ("TODO", re.compile(r"\bTODO\b", re.IGNORECASE)),
    ("TBD", re.compile(r"\bTBD\b", re.IGNORECASE)),
    ("待补充", re.compile("待补充")),
    ("在此填入", re.compile("在此填入")),
)
TEXT_SUFFIXES = {".md", ".json", ".yml", ".yaml", ".py", ".txt", ".csv"}


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {
            "AGENTS.md",
            "CLAUDE.md",
            "README.md",
        }:
            files.append(path)
    return files


def is_template(path: Path) -> bool:
    return path.name.endswith("_TEMPLATE.md")


def requires_status(path: Path, root: Path) -> bool:
    rel = relative(path, root)
    if is_template(path):
        return False
    return rel.startswith("docs/milestones/") or rel.startswith("docs/specs/") or rel.startswith(
        "docs/sop/"
    )


def check_repository(root: Path, acceptance_ready: bool = False) -> list[str]:
    errors: list[str] = []

    for required in REQUIRED_FILES:
        if not (root / required).is_file():
            errors.append(f"missing required file: {required}")

    if acceptance_ready:
        for name in MILESTONE_FILES:
            path = root / "docs" / "milestones" / name
            if not path.is_file():
                errors.append(f"acceptance requires milestone: docs/milestones/{name}")

    decoded: dict[Path, str] = {}
    for path in text_files(root):
        try:
            decoded[path] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"invalid UTF-8: {relative(path, root)} ({exc})")

    for path, text in decoded.items():
        if path.suffix.lower() == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(
                    f"invalid JSON: {relative(path, root)} line {exc.lineno} column {exc.colno}"
                )

        if path.suffix.lower() != ".md" or is_template(path):
            continue

        status_match = STATUS_PATTERN.search(text)
        status = status_match.group(1).lower() if status_match else None
        if requires_status(path, root) and status not in ALLOWED_STATUSES:
            errors.append(f"invalid or missing status: {relative(path, root)}")

        if status == "approved":
            for label, pattern in UNFINISHED_PATTERNS:
                if pattern.search(text):
                    errors.append(
                        f"unfinished marker {label!r} in approved document: {relative(path, root)}"
                    )

    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PCB-CDSO repository governance.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument(
        "--acceptance-ready",
        action="store_true",
        help="Require the complete M0-M5 milestone set",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    root = args.root.resolve()
    errors = check_repository(root, acceptance_ready=args.acceptance_ready)
    if errors:
        print(f"Governance check failed with {len(errors)} issue(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Governance baseline valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

