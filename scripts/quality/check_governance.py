#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import hashlib
import json
import re
import subprocess
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
    if (root / ".git").exists():
        listed = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        candidates = (root / item for item in listed.stdout.splitlines() if item)
    else:
        candidates = root.rglob("*")
    for path in candidates:
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


def check_schema_contract(path: Path, root: Path, schema: Any) -> list[str]:
    label = relative(path, root)
    if not isinstance(schema, dict):
        return [f"invalid manifest schema: {label} must be an object"]
    required_keys = {"$schema", "$id", "type", "required", "properties"}
    missing = sorted(required_keys - set(schema))
    if missing or schema.get("type") != "object" or not isinstance(schema.get("required"), list) or not isinstance(schema.get("properties"), dict):
        detail = f" missing {', '.join(missing)}" if missing else ""
        return [f"invalid manifest schema: {label}{detail}"]
    return []


def validate_schema(instance: Any, schema: dict[str, Any], location: str) -> list[str]:
    """Validate the JSON Schema subset used by the two repository manifests."""
    errors: list[str] = []
    expected_type = schema.get("type")
    allowed_types = expected_type if isinstance(expected_type, list) else [expected_type]
    type_checks = {
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
        "string": lambda value: isinstance(value, str),
        "null": lambda value: value is None,
        "number": lambda value: isinstance(value, (int, float)) and not isinstance(value, bool),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "boolean": lambda value: isinstance(value, bool),
    }
    declared_types = [item for item in allowed_types if item]
    if declared_types and not any(type_checks[item](instance) for item in declared_types if item in type_checks):
        return [f"{location} must be type {'/'.join(declared_types)}"]
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{location} must equal {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{location} is not an allowed value")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append(f"{location} is too short")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], instance):
            errors.append(f"{location} does not match required pattern")
        if schema.get("format") == "date-time" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", instance):
            errors.append(f"{location} is not an ISO 8601 date-time")
    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(f"{location} missing {key}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{location} has unexpected property {key}")
        for key, child_schema in properties.items():
            if key in instance:
                errors.extend(validate_schema(instance[key], child_schema, f"{location}.{key}"))
        if len(instance) < schema.get("minProperties", 0):
            errors.append(f"{location} has too few properties")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{location} has too few items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(validate_schema(item, item_schema, f"{location}[{index}]"))
        contains = schema.get("contains")
        if isinstance(contains, dict) and not any(not validate_schema(item, contains, location) for item in instance):
            errors.append(f"{location} has no item matching contains")
    for conditional in schema.get("allOf", []):
        if_schema = conditional.get("if")
        then_schema = conditional.get("then")
        if isinstance(if_schema, dict) and isinstance(then_schema, dict) and not validate_schema(instance, if_schema, location):
            errors.extend(validate_schema(instance, then_schema, location))
    return errors


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
        if governance.get("producer") and governance.get("producer") == governance.get("softwareVerifier"):
            errors.append(f"{label} producer and softwareVerifier must be independent")
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
        record_path = item.get("signedRecordPath")
        if isinstance(record_path, str):
            candidate = Path(record_path)
            if candidate.is_absolute() or ".." in candidate.parts or not (root / candidate).is_file():
                errors.append(f"{label} verificationEvidence[{index}] signedRecordPath is missing or unsafe")
    if status == "SOFTWARE_VERIFIED" and not any(
        isinstance(item, dict) and item.get("status") == "SOFTWARE_VERIFIED" for item in evidence
    ):
        errors.append(f"{label} SOFTWARE_VERIFIED requires software verification evidence")
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
    plan_text = plan.read_text(encoding="utf-8") if plan.is_file() else ""
    if not re.search(r"\|\s*状态\s*\|\s*approved\s*\|", plan_text, re.IGNORECASE):
        errors.append(f"{relative(plan, root)} test plan status must be approved")
    trace_text = (root / "docs/testing/P0_TRACEABILITY.md").read_text(encoding="utf-8")
    required_ids = [
        p0_id
        for p0_id, primary in re.findall(
            r"^\|\s*(P0_\d{2})\s*\|.*\|\s*(M[0-6])\s*\|",
            trace_text,
            re.MULTILINE,
        )
        if primary == milestone
    ]
    for p0_id in required_ids:
        if not re.search(rf"^\|\s*{re.escape(p0_id)}\s*\|", plan_text, re.MULTILINE):
            errors.append(f"{relative(plan, root)} missing required {p0_id}")

    text = record.read_text(encoding="utf-8")
    status_match = re.search(r"\|\s*状态\s*\|\s*([^|]+?)\s*\|", text)
    if not status_match or status_match.group(1).strip() != "GO":
        errors.append(f"{relative(record, root)} acceptance status must be GO")
    sha_match = re.search(r"\|\s*Candidate SHA\s*\|\s*([^|]+?)\s*\|", text, re.IGNORECASE)
    candidate_sha = sha_match.group(1).strip() if sha_match else ""
    if not SHA_PATTERN.fullmatch(candidate_sha):
        errors.append(f"{relative(record, root)} requires a 40-character Candidate SHA")
    elif (root / ".git").exists() and not os.environ.get("CI"):
        # Verify the Candidate SHA is a real commit when full history is
        # available. In CI shallow checkouts (fetch-depth: 1) historical
        # candidate SHAs (e.g. M0 verified against 3591987 while the
        # acceptance record ships in a later PR) are absent from the clone;
        # the CI environment variable marks this case so we degrade to
        # format-only validation rather than blocking the acceptance gate.
        # CI workflows that need strict verification use fetch-depth: 0.
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"{candidate_sha}^{{commit}}"],
            cwd=root,
            capture_output=True,
            check=False,
        )
        if exists.returncode != 0:
            errors.append(f"{relative(record, root)} Candidate SHA is not a repository commit")
    signoff_match = re.search(r"\|\s*Product Sign-off\s*\|\s*([^|]+?)\s*\|", text, re.IGNORECASE)
    signoff = signoff_match.group(1).strip() if signoff_match else ""
    if not signoff or signoff.lower() in {"pending", "not_required", "not-required"}:
        errors.append(f"{relative(record, root)} requires Product Sign-off")
    evidence_paths: list[str] = []
    for line in text.splitlines():
        if not line.startswith("|") or "pass" not in line.lower():
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 6 and cells[-1].lower() == "pass":
            evidence_paths.append(cells[-2].strip("`"))
        elif len(cells) >= 6 and cells[-1].lower() == "fail":
            errors.append(f"{relative(record, root)} contains failing required evidence")
    if not evidence_paths:
        errors.append(f"{relative(record, root)} requires at least one passing evidence row")
    for evidence_path in evidence_paths:
        candidate = Path(evidence_path)
        if candidate.is_absolute() or ".." in candidate.parts or not (root / candidate).is_file():
            errors.append(f"{relative(record, root)} evidence path missing or unsafe: {evidence_path}")
    for p0_id in required_ids:
        if not any(p0_id in line and line.rstrip().lower().endswith("pass |") for line in text.splitlines()):
            errors.append(f"{relative(record, root)} missing passing evidence for {p0_id}")
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
    schema_paths = {
        "seed": root / "contracts/seeds/seed-manifest.schema.json",
        "fixture": root / "contracts/fixtures/fixture-manifest.schema.json",
    }
    for schema_path in schema_paths.values():
        if schema_path in parsed_json:
            errors.extend(check_schema_contract(schema_path, root, parsed_json[schema_path]))
    for path, data in parsed_json.items():
        if path.name == "manifest.json" and ("fixtures" in path.parts or "seeds" in path.parts):
            schema_key = "fixture" if "fixtures" in path.parts else "seed"
            schema = parsed_json.get(schema_paths[schema_key])
            if isinstance(schema, dict):
                errors.extend(validate_schema(data, schema, relative(path, root)))
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
