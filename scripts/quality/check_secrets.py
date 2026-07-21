from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENT = re.compile(
    r"^\s*(?:-\s*)?(?P<key>[A-Z0-9_]*(?:PASSWORD|SECRET|TOKEN|API_KEY)[A-Z0-9_]*)"
    r"\s*(?:=|:)\s*[\"']?(?P<value>[^\"'\s#]+)",
    re.IGNORECASE,
)
ALLOWED_MARKERS = ("replace", "example", "placeholder", "dummy", "<", "${", "secrets.")
CONFIG_SUFFIXES = {".env", ".ini", ".json", ".toml", ".yaml", ".yml"}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    key: str


def find_secret_assignments(path: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = ASSIGNMENT.match(line)
        if match is None:
            continue
        value = match.group("value").lower()
        if not value or any(marker in value for marker in ALLOWED_MARKERS):
            continue
        findings.append(Finding(path=path, line=line_number, key=match.group("key")))
    return findings


def candidate_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / item for item in result.stdout.splitlines() if item]


def should_scan(path: Path) -> bool:
    return path.name.startswith(".env") or path.suffix.lower() in CONFIG_SUFFIXES


def main() -> int:
    findings: list[Finding] = []
    for path in candidate_files():
        if not should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        findings.extend(find_secret_assignments(path.relative_to(ROOT).as_posix(), text))
    for finding in findings:
        print(f"{finding.path}:{finding.line}: concrete value assigned to {finding.key}", file=sys.stderr)
    if findings:
        print(f"FAIL potential secrets found: {len(findings)}", file=sys.stderr)
        return 1
    print("PASS no concrete secret assignments found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
