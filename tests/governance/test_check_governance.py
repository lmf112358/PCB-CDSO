from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHECKER = PROJECT_ROOT / "scripts" / "quality" / "check_governance.py"

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

MILESTONES = (
    "M0-repository-baseline.md",
    "M1-identity-template-project.md",
    "M2-controlled-data-collection.md",
    "M3-static-calculation.md",
    "M4-weather-simulation-forecast.md",
    "M5-results-center.md",
    "M6-export-delivery-closure.md",
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_valid_repository(root: Path, include_milestones: bool = True) -> None:
    p0_lines = "\n".join(f"- P0_{index:02d}" for index in range(1, 15))
    trace_rows = "\n".join(
        f"| P0_{index:02d} | requirement | M{min((index - 1) // 2, 6)} | spec.md | evidence |"
        for index in range(1, 15)
    )
    for relative in REQUIRED_FILES:
        path = root / relative
        if path.suffix == ".json":
            write(path, json.dumps({"valid": True}))
        elif relative == "docs/sop/DEVELOPMENT_SOP.md":
            write(path, "# SOP\n\n| 状态 | approved |\n")
        elif relative == "docs/product/PRD_v0.6.md":
            write(path, f"# PRD\n\n{p0_lines}\n")
        elif relative == "docs/testing/P0_TRACEABILITY.md":
            write(
                path,
                "# P0 Traceability\n\n"
                "| P0 ID | Requirement | Primary Milestone | Spec | Evidence |\n"
                "|---|---|---|---|---|\n"
                f"{trace_rows}\n",
            )
        else:
            write(path, f"# {path.stem}\n")
    if include_milestones:
        for name in MILESTONES:
            write(root / "docs" / "milestones" / name, f"# {name}\n\n| 状态 | approved |\n")


def make_acceptance_artifacts(root: Path, milestone: str = "M0") -> None:
    evidence = root / "artifacts" / "acceptance" / milestone / "governance.txt"
    write(evidence, "all checks passed\n")
    write(
        root / "docs" / "testing" / "plans" / f"{milestone}-test-plan.md",
        f"# {milestone} Test Plan\n\n| Requirement ID | Command | Expected |\n|---|---|---|\n| P0_01 | make test | exit 0 |\n",
    )
    write(
        root / "docs" / "testing" / "acceptance" / f"{milestone}-acceptance.md",
        "\n".join(
            (
                f"# {milestone} Acceptance Record",
                "",
                "| 属性 | 填写值 |",
                "|---|---|",
                "| 状态 | GO |",
                f"| Candidate SHA | {'a' * 40} |",
                "| Product Sign-off | product-owner@2026-07-21T12:00:00+08:00 |",
                "",
                "## 执行证据",
                "",
                "| 场景/命令 | 预期 | 实际 | 退出码 | 证据路径 | 结论 |",
                "|---|---|---|---:|---|---|",
                f"| governance | exit 0 | exit 0 | 0 | artifacts/acceptance/{milestone}/governance.txt | pass |",
            )
        ),
    )


def make_fixture_manifest(root: Path, checksum_matches: bool = True) -> Path:
    data_path = root / "fixtures" / "calculation" / "case-1" / "1.0.0" / "input.csv"
    write(data_path, "value\n1\n")
    checksum = hashlib.sha256(data_path.read_bytes()).hexdigest()
    if not checksum_matches:
        checksum = "0" * 64
    manifest_path = data_path.with_name("manifest.json")
    manifest = {
        "schemaVersion": "1.0.0",
        "datasetId": "case-1",
        "datasetVersion": "1.0.0",
        "verificationStatus": "SOFTWARE_VERIFIED",
        "governance": {
            "producer": "Calculation Agent",
            "softwareVerifier": "Test Agent",
            "expertApprover": None,
        },
        "verificationEvidence": [
            {
                "status": "SOFTWARE_VERIFIED",
                "verifiedBy": "Test Agent",
                "verifiedAt": "2026-07-21T12:00:00+08:00",
                "method": "unit test",
                "signedRecordPath": "docs/testing/acceptance/M3-acceptance.md",
            }
        ],
        "files": [{"path": "input.csv", "sha256": checksum, "mediaType": "text/csv"}],
        "expectations": {"rows": 1},
    }
    write(manifest_path, json.dumps(manifest))
    return manifest_path


def run_checker(root: Path, milestone: str | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(CHECKER), "--root", str(root)]
    if milestone is not None:
        command.extend(("--acceptance-ready", milestone))
    return subprocess.run(command, capture_output=True, text=True, check=False)


class GovernanceCheckerTest(unittest.TestCase):
    def test_valid_repository_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            result = run_checker(root)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("Governance baseline valid", result.stdout)

    def test_missing_required_file_fails_with_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            (root / "AGENTS.md").unlink()
            result = run_checker(root)
            self.assertEqual(1, result.returncode)
            self.assertIn("AGENTS.md", result.stdout)

    def test_malformed_json_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            write(root / "contracts" / "seeds" / "broken.json", "{not-json")
            result = run_checker(root)
            self.assertEqual(1, result.returncode)
            self.assertIn("broken.json", result.stdout)
            self.assertIn("invalid JSON", result.stdout)

    def test_unfinished_marker_in_approved_document_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            write(root / "docs" / "milestones" / MILESTONES[0], "# M0\n\n| 状态 | approved |\n\nTODO define gate\n")
            result = run_checker(root)
            self.assertEqual(1, result.returncode)
            self.assertIn("unfinished marker", result.stdout)

    def test_invalid_governed_document_status_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            write(root / "docs" / "milestones" / MILESTONES[1], "# M1\n\n| 状态 | almost_done |\n")
            result = run_checker(root)
            self.assertEqual(1, result.returncode)
            self.assertIn("invalid or missing status", result.stdout)

    def test_p0_ids_must_exist_in_prd_and_traceability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            write(root / "docs" / "testing" / "P0_TRACEABILITY.md", "# incomplete\nP0_01\n")
            result = run_checker(root)
            self.assertEqual(1, result.returncode)
            self.assertIn("P0_14", result.stdout)

    def test_acceptance_ready_requires_m6_milestone_spec(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            make_acceptance_artifacts(root, "M6")
            (root / "docs" / "milestones" / MILESTONES[6]).unlink()
            result = run_checker(root, "M6")
            self.assertEqual(1, result.returncode)
            self.assertIn(MILESTONES[6], result.stdout)

    def test_acceptance_ready_rejects_empty_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            write(root / "docs" / "testing" / "plans" / "M0-test-plan.md", "")
            write(root / "docs" / "testing" / "acceptance" / "M0-acceptance.md", "")
            result = run_checker(root, "M0")
            self.assertEqual(1, result.returncode)
            self.assertIn("test plan", result.stdout)
            self.assertIn("acceptance record", result.stdout)

    def test_acceptance_ready_rejects_bad_sha_status_and_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            make_acceptance_artifacts(root)
            record = root / "docs" / "testing" / "acceptance" / "M0-acceptance.md"
            write(record, "# M0\n\n| 状态 | NO-GO |\n| Candidate SHA | abc |\n\n## 执行证据\n\nmissing.txt\n")
            result = run_checker(root, "M0")
            self.assertEqual(1, result.returncode)
            self.assertIn("GO", result.stdout)
            self.assertIn("40-character", result.stdout)
            self.assertIn("evidence", result.stdout)

    def test_acceptance_ready_passes_with_plan_record_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            make_acceptance_artifacts(root)
            result = run_checker(root, "M0")
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("M0 acceptance evidence valid", result.stdout)

    def test_fixture_manifest_checksum_must_match_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            make_fixture_manifest(root, checksum_matches=False)
            result = run_checker(root)
            self.assertEqual(1, result.returncode)
            self.assertIn("checksum mismatch", result.stdout)

    def test_fixture_manifest_requires_independent_governance_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            manifest_path = make_fixture_manifest(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["governance"]["softwareVerifier"]
            write(manifest_path, json.dumps(manifest))
            result = run_checker(root)
            self.assertEqual(1, result.returncode)
            self.assertIn("softwareVerifier", result.stdout)


if __name__ == "__main__":
    unittest.main()
