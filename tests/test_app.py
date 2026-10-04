import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node is required for frontend regression tests")
class ReportLinkTests(unittest.TestCase):
    def test_report_titles_are_unique_and_preserve_class_and_template(self):
        result = subprocess.run(
            ["node", "-e", r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");
const elements = new Map();
const context = vm.createContext({
  crypto: webcrypto,
  document: {
    getElementById(id) {
      if (!elements.has(id)) {
        elements.set(id, { parentElement: {}, setAttribute() {} });
      }
      return elements.get(id);
    },
  },
});
const source = fs.readFileSync("app.js", "utf8").replace(/^initialize\(\);$/m, "");
vm.runInContext(source, context);
vm.runInContext("renderVoluntary = () => {};", context);
const titles = new Set();
function checkLink(year) {
  const url = new URL(elements.get("report-link").href);
  assert.equal(url.origin, "https://github.com");
  assert.equal(url.pathname, "/ColtonKawamura/whos-still-in/issues/new");
  assert.equal(url.searchParams.get("template"), "voluntary-report.yml");
  const title = url.searchParams.get("title");
  assert.match(title, new RegExp(`^\\[Voluntary report\\] Class of ${year} — [0-9a-f]{32}$`));
  assert.ok(!titles.has(title), "Each new report link must have a unique title");
  titles.add(title);
}
for (const year of [2012, 2013, 2012]) {
  vm.runInContext(`render({
    year: ${year}, commissioned_total: 100, as_of: "2026-10-04",
    voluntary: { reported_still_in: 0, reported_out: 0 },
  });`, context);
  checkLink(year);
  const link = elements.get("report-link");
  for (let i = 0; i < 20; i++) {
    link.onclick();
    checkLink(year);
    link.onauxclick();
    checkLink(year);
  }
}
"""],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
