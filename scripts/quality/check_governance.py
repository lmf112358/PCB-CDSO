#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/product/PRD_v0.6.md",
    "docs/sop/DEVELOPMENT_SOP.md",
    "docs/testing/DATA_AND_FIXTURE_REQUIREMENTS.md",
    "docs/testing/P0_TRACEABILITY.md",
    "contracts/seeds/seed-manifest.schema.json",
    "contracts/fixtures/fixture-manifest.schema.json",
    "fixtures/README.md",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/ISSUE_TEMPLATE/bug.yml",
)

MILESTONES = {
    "M0": "M0-repository-baseline.md",
    "M1": "M1-identity-template-project.md",
    "M2": "M2-controlled-data-collection.md",
    "M3": "M3-static-calculation.md",
    "M4": "M4-weather-simulation-forecast.md",
    "M5": "M5-results-center.md",
    "M6": "M6-export-delivery-closure.md",
}

ALLOWED_STATUSES = {"draft", "approved", "implementing", "verified", "superseded"}
VERIFICATION_STATUSES = {"UNVERIFIED", "SOFTWARE_VERIFIED", "EXPERT_VERIFIED"}
STATUS_PATTERN = re.compile(r"\|\s*(?:状态|status)\s*\|\s*([a-z_-]+)\s*\|", re.IGNORECASE)
SHA_PATTERN = re.compile(r"^[a-f0-9]{40}$", re.IGNORECASE)
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
P0_IDS = {f"P0_{index:02d}" for index in range(1, 15)}
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
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"AGENTS.md", "CLAUDE.md", "README.md"}:
            files.append(path)
    return files


def is_template(path: Path) -> bool:
    return path.name.endswith("_TEMPLATE.md")


def requires_status(path: Path, root: Path) -> bool:
    rel = relative(path, root)
    if is_template(path):
        return False
    return rel.startswith(("docs/milestones/", "docs/specs/", "docs/sop/"))


def check_p0_traceability(root: Path, decoded: dict[Path, str]) -> list[str]:
    errors: list[str] = []
    prd_path = root / "docs/product/PRD_v0.6.md"
    trace_path = root / "docs/testing/P0_TRACEABILITY.md"
    prd_ids = set(re.findall(r"\bP0_\d{2}\b", decoded.get(prd_path, "")))
    trace_text = decoded.get(trace_path, "")
    trace_ids = set(re.findall(r"\bP0_\d{2}\b", trace_text))
    for p0_id in sorted(P0_IDS):
        if p0_id not in prd_ids:
            errors.append(f"missing {p0_id} in docs/product/PRD_v0.6.md")
        if p0_id not in trace_ids:
            errors.append(f"missing {p0_id} in docs/testing/P0_TRACEABILITY.md")
    unexpected = sorted((prd_ids | trace_ids) - P0_IDS)
    if unexpected:
        errors.append(f"unexpected P0 IDs: {', '.join(unexpected)}")
    table_rows = re.findall(r"^\|\s*(P0_\d{2})\s*\|.*\|\s*(M[0-6])\s*\|", trace_text, re.MULTILINE)
    row_ids = [item[0] for item in table_rows]
    for p0_id in sorted(P0_IDS):
        if row_ids.count(p0_id) != 1:
            errors.append(f"{p0_id} must have exactly one Primary Milestone row")
    return errors


def _required_string(container: dict[str, Any], key: str, label: str, errors: list[str]) -> None:
    if not isinstance(container.get(key), str) or not container[key].strip():
        errors.append(f"{label} requires non-empty {key}")


def check_manifest(path: Path, root: Path, data: Any) -> list[str]:
    errors: list[str] = []
    label = relative(path, root)
    if not isinstance(data, dict):
        return [f"manifest must be an object: {label}"]
    for key in ("datasetId", "datasetVersion", "verificationStatus", "governance", "verificationEvidence"):
        if key not in data:
            errors.append(f"{label} missing {key}")
    status = data.get("verificationStatus")
    if status not in VERIFICATION_STATUSES:
        errors.append(f"{label} invalid verificationStatus")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append(f"{label} governance must be an object")
    else:
        _required_string(governance, "producer", label, errors)
        _required_string(governance, "softwareVerifier", label, errors)
        if "expertApprover" not in governance:
            errors.append(f"{label} missing expertApprover")
    evidence = data.get("verificationEvidence")
    if not isinstance(evidence, list):
        errors.append(f"{label} verificationEvidence must be an array")
        evidence = []
    for index, item in enumerate(evidence):
        if not isinstance(item, dict):
            errors.append(f"{label} verificationEvidence[{index}] must be an object")
            continue
        for key in ("status", "verifiedBy", "verifiedAt", "method", "signedRecordPath"):
            _required_string(item, key, f"{label} verificationEvidence[{index}]", errors)
    if status == "EXPERT_VERIFIED" and not any(
        isinstance(item, dict) and item.get("status") == "EXPERT_VERIFIED" for item in evidence
    ):
        errors.append(f"{label} EXPERT_VERIFIED requires expert verification evidence")

    is_fixture = "fixtures" in path.parts
    if is_fixture:
        files = data.get("files")
        if not isinstance(files, list) or not files:
            errors.append(f"{label} requires non-empty files")
        else:
            for index, item in enumerate(files):
                if not isinstance(item, dict):
                    errors.append(f"{label} files[{index}] must be an object")
                    continue
                file_name = item.get("path")
                checksum = item.get("sha256")
                if not isinstance(file_name, str) or not file_name or Path(file_name).is_absolute() or ".." in Path(file_name).parts:
                    errors.append(f"{label} files[{index}] has unsafe path")
                    continue
                if not isinstance(checksum, str) or not SHA256_PATTERN.fullmatch(checksum):
                    errors.append(f"{label} files[{index}] has invalid sha256")
                    continue
                target = path.parent / file_name
                if not target.is_file():
                    errors.append(f"{label} fixture file missing: {file_name}")
                    continue
                actual = hashlib.sha256(target.read_bytes()).hexdigest()
                if actual != checksum:
                    errors.append(f"{label} checksum mismatch: {file_name}")
        if not isinstance(data.get("expectations"), dict) or not data["expectations"]:
            errors.append(f"{label} requires non-empty expectations")
    else:
        checksum = data.get("checksum")
        if not isinstance(checksum, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", checksum):
            errors.append(f"{label} has invalid checksum")
    return errors


def check_acceptance(root: Path, milestone: str) -> list[str]:
    errors: list[str] = []
    spec = root / "docs/milestones" / MILESTONES[milestone]
    plan = root / "docs/testing/plans" / f"{milestone}-test-plan.md"
    record = root / "docs/testing/acceptance" / f"{milestone}-acceptance.md"
    if not spec.is_file():
        errors.append(f"acceptance requires milestone spec: {relative(spec, root)}")
    if not plan.is_file() or plan.stat().st_size == 0:
        errors.append(f"acceptance requires non-empty test plan: {relative(plan, root)}")
    if not record.is_file() or record.stat().st_size == 0:
        errors.append(f"acceptance requires non-empty acceptance record: {relative(record, root)}")
        return errors
    text = record.read_text(encoding="utf-8")
    status_match = re.search(r"\|\s*状态\s*\|\s*([^|]+?)\s*\|", text)
    if not status_match or status_match.group(1).strip() != "GO":
        errors.append(f"{relative(record, root)} acceptance status must be GO")
    sha_match = re.search(r"\|\s*Candidate SHA\s*\|\s*([^|]+?)\s*\|", text, re.IGNORECASE)
    candidate_sha = sha_match.group(1).strip() if sha_match else ""
    if not SHA_PATTERN.fullmatch(candidate_sha):
        errors.append(f"{relative(record, root)} requires a 40-character Candidate SHA")
    evidence_paths: list[str] = []
    for line in text.splitlines():
        if not line.startswith("|") or "pass" not in line.lower():
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 6 and cells[-1].lower() == "pass":
            evidence_paths.append(cells[-2].strip("`"))
    if not evidence_paths:
        errors.append(f"{relative(record, root)} requires at least one passing evidence row")
    for evidence_path in evidence_paths:
        candidate = Path(evidence_path)
        if candidate.is_absolute() or ".." in candidate.parts or not (root / candidate).is_file():
            errors.append(f"{relative(record, root)} evidence path missing or unsafe: {evidence_path}")
    return errors


def check_repository(root: Path, acceptance_ready: str | None = None) -> list[str]:
    errors: list[str] = []
    for required in REQUIRED_FILES:
        if not (root / required).is_file():
            errors.append(f"missing required file: {required}")

    decoded: dict[Path, str] = {}
    parsed_json: dict[Path, Any] = {}
    for path in text_files(root):
        try:
            decoded[path] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            errors.append(f"invalid UTF-8: {relative(path, root)} ({exc})")
            continue
        if path.suffix.lower() == ".json":
            try:
                parsed_json[path] = json.loads(decoded[path])
            except json.JSONDecodeError as exc:
                errors.append(f"invalid JSON: {relative(path, root)} line {exc.lineno} column {exc.colno}")

    for path, text in decoded.items():
        if path.suffix.lower() != ".md" or is_template(path):
            continue
        status_match = STATUS_PATTERN.search(text)
        status = status_match.group(1).lower() if status_match else None
        if requires_status(path, root) and status not in ALLOWED_STATUSES:
            errors.append(f"invalid or missing status: {relative(path, root)}")
        if status == "approved":
            for label, pattern in UNFINISHED_PATTERNS:
                if pattern.search(text):
                    errors.append(f"unfinished marker {label!r} in approved document: {relative(path, root)}")

    errors.extend(check_p0_traceability(root, decoded))
    for path, data in parsed_json.items():
        if path.name == "manifest.json" and ("fixtures" in path.parts or "seeds" in path.parts):
            errors.extend(check_manifest(path, root, data))
    if acceptance_ready:
        errors.extend(check_acceptance(root, acceptance_ready))
    return errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate PCB-CDSO repository governance.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument(
        "--acceptance-ready",
        choices=tuple(MILESTONES),
        metavar="MILESTONE",
        help="Validate one milestone's spec, test plan, GO record, candidate SHA and evidence",
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
    if args.acceptance_ready:
        print(f"Governance baseline and {args.acceptance_ready} acceptance evidence valid.")
    else:
        print("Governance baseline valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
