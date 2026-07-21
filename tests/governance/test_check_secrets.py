from __future__ import annotations

import unittest

from scripts.quality.check_secrets import find_secret_assignments


class SecretScannerTests(unittest.TestCase):
    def test_rejects_concrete_password(self) -> None:
        findings = find_secret_assignments("config.env", "DATABASE_PASSWORD=SuperSecret123!\n")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].line, 1)

    def test_allows_local_placeholders_and_environment_references(self) -> None:
        text = "\n".join(
            [
                "MYSQL_PASSWORD=local_only_replace_me",
                "API_TOKEN=${API_TOKEN}",
                "password: ${{ secrets.DEPLOY_PASSWORD }}",
                "BOOTSTRAP_ADMIN_PASSWORD=example_only",
            ]
        )
        self.assertEqual(find_secret_assignments(".env.example", text), [])

    def test_does_not_flag_documentation_prose(self) -> None:
        self.assertEqual(
            find_secret_assignments("README.md", "Set MYSQL_PASSWORD through your environment."),
            [],
        )


if __name__ == "__main__":
    unittest.main()
