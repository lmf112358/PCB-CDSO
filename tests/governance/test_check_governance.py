from __future__ import annotations

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
    "contracts/seeds/seed-manifest.schema.json",
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
    "M5-results-export-delivery.md",
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_valid_repository(root: Path, include_milestones: bool = True) -> None:
    for relative in REQUIRED_FILES:
        path = root / relative
        if path.suffix == ".json":
            write(path, json.dumps({"valid": True}))
        elif relative == "docs/sop/DEVELOPMENT_SOP.md":
            write(path, "# SOP\n\n| 状态 | approved |\n")
        else:
            write(path, f"# {path.stem}\n")
    if include_milestones:
        for name in MILESTONES:
            write(
                root / "docs" / "milestones" / name,
                f"# {name}\n\n| 状态 | approved |\n",
            )


def run_checker(root: Path, acceptance_ready: bool = False) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(CHECKER), "--root", str(root)]
    if acceptance_ready:
        command.append("--acceptance-ready")
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
            write(
                root / "docs" / "milestones" / MILESTONES[0],
                "# M0\n\n| 状态 | approved |\n\nTODO define gate\n",
            )

            result = run_checker(root)

            self.assertEqual(1, result.returncode)
            self.assertIn("unfinished marker", result.stdout)
            self.assertIn(MILESTONES[0], result.stdout)

    def test_invalid_governed_document_status_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root)
            write(
                root / "docs" / "milestones" / MILESTONES[1],
                "# M1\n\n| 状态 | almost_done |\n",
            )

            result = run_checker(root)

            self.assertEqual(1, result.returncode)
            self.assertIn("invalid or missing status", result.stdout)

    def test_acceptance_ready_requires_all_milestones(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            make_valid_repository(root, include_milestones=False)

            result = run_checker(root, acceptance_ready=True)

            self.assertEqual(1, result.returncode)
            self.assertIn("acceptance requires", result.stdout)
            self.assertIn(MILESTONES[0], result.stdout)


if __name__ == "__main__":
    unittest.main()

