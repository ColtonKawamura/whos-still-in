import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_add_report import body

ROOT = Path(__file__).resolve().parents[1]


class VoluntaryPrTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for directory in ("scripts", "data", "tests", "bin"):
            (self.root / directory).mkdir()
        for name in ("voluntary_pr.sh", "add_report.py", "build_data.py"):
            shutil.copy(ROOT / "scripts" / name, self.root / "scripts" / name)
        shutil.copy(ROOT / "data" / "cohorts.csv", self.root / "data" / "cohorts.csv")
        for name in ("test_add_report.py", "test_build_data.py"):
            shutil.copy(ROOT / "tests" / name, self.root / "tests" / name)
        form = Path(".github") / "ISSUE_TEMPLATE" / "voluntary-report.yml"
        (self.root / form).parent.mkdir(parents=True)
        shutil.copy(ROOT / form, self.root / form)
        self.log = self.root / "commands"
        self.log.touch()
        self.issue = {
            "number": 8, "state": "OPEN", "title": "[Voluntary report] Class of 2012",
            "body": body(), "labels": [], "author": {"login": "reporter", "is_bot": False},
        }
        self.write_command("gh", """#!/usr/bin/env bash
set -eu
printf 'gh %s\\n' "$*" >> "$COMMAND_LOG"
case "$1 $2" in
  "issue view") cat "$ISSUE_JSON" ;;
  "api "*|"issue list"|"label create"|"issue edit"|"issue comment"|"pr list"|"pr create") ;;
  *) echo "Unexpected gh command: $*" >&2; exit 1 ;;
esac
""")
        self.write_command("git", """#!/usr/bin/env bash
set -eu
printf 'git %s\\n' "$*" >> "$COMMAND_LOG"
case "$1" in
  diff) exit 1 ;;
  fetch|checkout|config|add|commit|push) ;;
  *) echo "Unexpected git command: $*" >&2; exit 1 ;;
esac
""")

    def write_command(self, name, content):
        path = self.root / "bin" / name
        path.write_text(content)
        path.chmod(0o755)

    def sync(self):
        issue_json = self.root / "issue.json"
        issue_json.write_text(json.dumps(self.issue))
        result = subprocess.run(
            ["bash", str(self.root / "scripts" / "voluntary_pr.sh"), "sync", "8"],
            env=os.environ | {
                "PATH": f"{self.root / 'bin'}{os.pathsep}{os.environ['PATH']}",
                "GITHUB_REPOSITORY": "example/reports",
                "ISSUE_JSON": str(issue_json), "COMMAND_LOG": str(self.log),
            },
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        commands = self.log.read_text()
        self.assertIn("--json number,state,title,body,labels,author", commands)
        return result.stdout, commands

    def test_unlabelled_title_report_creates_pr_and_self_labels(self):
        output, commands = self.sync()
        self.assertIn("Synced #8 -> voluntary-report/issue-8", output)
        self.assertIn("git checkout --quiet --force -B voluntary-report/issue-8 FETCH_HEAD", commands)
        self.assertIn("git push --quiet --force origin voluntary-report/issue-8", commands)
        self.assertIn("gh pr create --repo example/reports --base main --head voluntary-report/issue-8", commands)
        self.assertIn("gh issue edit 8 --repo example/reports --add-label voluntary-report", commands)
        self.assertIn(",voluntary,", (self.root / "data" / "cohorts.csv").read_text())
        self.assertTrue((self.root / "data" / "2012.json").exists())
        self.assertTrue((self.root / "data" / "index.json").exists())

    def test_labelled_report_without_title_prefix_is_accepted(self):
        self.issue.update(title="Report", labels=[{"name": "voluntary-report"}])
        output, commands = self.sync()
        self.assertIn("Synced #8", output)
        self.assertIn("gh pr create", commands)

    def test_unrelated_issues_are_skipped(self):
        for title in ("Report", "Question about [Voluntary report]", ""):
            with self.subTest(title=title):
                self.log.write_text("")
                self.issue.update(title=title, labels=[{"name": "other"}])
                output, commands = self.sync()
                self.assertIn("is not a voluntary report; skipping", output)
                self.assertEqual(len(commands.splitlines()), 1)

    def test_bot_reports_are_skipped(self):
        self.issue["author"]["is_bot"] = True
        for labels in ([], [{"name": "voluntary-report"}]):
            with self.subTest(labels=labels):
                self.log.write_text("")
                self.issue["labels"] = labels
                output, commands = self.sync()
                self.assertIn("is not a voluntary report; skipping", output)
                self.assertEqual(len(commands.splitlines()), 1)

    def test_invalid_title_report_is_not_labelled_or_published(self):
        self.issue["body"] = body(consent="- [ ] Not consenting")
        _, commands = self.sync()
        self.assertIn("gh issue comment", commands)
        self.assertNotIn("gh issue edit", commands)
        self.assertNotIn("git push", commands)
        self.assertNotIn("gh pr create", commands)


if __name__ == "__main__":
    unittest.main()
