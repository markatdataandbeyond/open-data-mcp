#!/usr/bin/env python3
"""TDD: Glama server-listing readiness (not the connector page). No secrets printed."""
from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from pathlib import Path
from urllib.request import urlopen, Request

ROOT = Path(__file__).resolve().parents[1]
OWNER_REPO = "markatdataandbeyond/open-data-mcp"
BADGE = f"https://glama.ai/mcp/servers/{OWNER_REPO}/badges/score.svg"
SERVER = f"https://glama.ai/mcp/servers/{OWNER_REPO}"
CONNECTOR = "https://glama.ai/mcp/connectors/io.github.markatdataandbeyond/open-data-mcp"
SHORT = "Ten tools I built to get facts from official open data, not guesses."
SECRET_KEYS = ("APIFY_TOKEN", "OPENALEX_API_KEY")


def redact(s: str) -> str:
    out = s
    for k in SECRET_KEYS:
        v = os.environ.get(k)
        if v and len(v) > 8:
            out = out.replace(v, "***")
    return out


class TestGlamaListing(unittest.TestCase):
    def test_01_dockerfile_cmd_not_entrypoint(self):
        df = (ROOT / "Dockerfile").read_text()
        self.assertRegex(df, r'(?m)^CMD\s+\[')
        self.assertNotRegex(df, r'(?m)^ENTRYPOINT\s+')
        self.assertIn("node", df)
        self.assertIn("src/index.js", df)
        self.assertIn("USER node", df)

    def test_02_glama_json_maintainers(self):
        g = json.loads((ROOT / "glama.json").read_text())
        self.assertEqual(g["$schema"], "https://glama.ai/mcp/schemas/server.json")
        self.assertEqual(g["maintainers"], ["markatdataandbeyond"])

    def test_03_readme_has_glama_badge(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn(BADGE, readme)
        self.assertIn(SERVER, readme)

    def test_04_no_secrets_in_dockerfile_or_readme(self):
        blobs = [
            (ROOT / "Dockerfile").read_text(),
            (ROOT / "README.md").read_text(),
            (ROOT / "glama.json").read_text(),
        ]
        pats = [
            re.compile(r"apify_api_[A-Za-z0-9]{20,}"),
            re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
            re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
        ]
        known = [os.environ[k] for k in SECRET_KEYS if os.environ.get(k) and len(os.environ[k]) > 8]
        for text in blobs:
            for p in pats:
                self.assertIsNone(p.search(text), redact(text[:200]))
            for v in known:
                self.assertNotIn(v, text)

    def test_05_short_description_documented(self):
        # Approved short text used for Glama description field (katalog-tekster.json).
        drafts = Path("/workspace/venture/apify-actors/drafts/katalog-tekster.json")
        self.assertTrue(drafts.is_file())
        data = json.loads(drafts.read_text())
        self.assertEqual(data["kort"], SHORT)

    # --- live spot checks ---
    def test_06_connector_exists_and_server_status(self):
        """Connector is live; server may still be 404 until Venture Lead finishes Add MCP Server."""
        from urllib.error import HTTPError

        req_c = Request(CONNECTOR, headers={"User-Agent": "open-data-mcp-tdd"})
        with urlopen(req_c, timeout=30) as r:
            self.assertEqual(r.status, 200)
            html = r.read(8000).decode("utf-8", "ignore")
        self.assertIn("open-data-mcp", html)
        req_s = Request(SERVER, headers={"User-Agent": "open-data-mcp-tdd"})
        try:
            with urlopen(req_s, timeout=30) as r:
                self.assertEqual(r.status, 200)
                body = r.read(4000).decode("utf-8", "ignore")
            self.assertIn("open-data-mcp", body.lower())
            self._server_listed = True
        except HTTPError as e:
            self.assertEqual(e.code, 404)
            self._server_listed = False


    def test_07_badge_svg_reachable(self):
        req = Request(BADGE, headers={"User-Agent": "open-data-mcp-tdd"})
        with urlopen(req, timeout=30) as r:
            svg = r.read().decode("utf-8", "ignore")
        self.assertTrue("glama" in svg.lower() or "mcp" in svg.lower() or "not listed" in svg.lower())


    def test_08_dbu_waste_finder_server_live(self):
        """Reference: sibling experiment is listed as a Glama *server* (has-glama path)."""
        url = "https://glama.ai/mcp/servers/markatdataandbeyond/dbu-waste-finder"
        req = Request(url, headers={"User-Agent": "open-data-mcp-tdd"})
        with urlopen(req, timeout=30) as r:
            self.assertEqual(r.status, 200)
            body = r.read(4000).decode("utf-8", "ignore")
        self.assertIn("DBU Waste Finder", body)

    # --- edge cases ---
    def test_09_dockerfile_no_hardcoded_token_assignment(self):
        df = (ROOT / "Dockerfile").read_text()
        # Comment mentioning APIFY_TOKEN is OK; ENV APIFY_TOKEN=secret is not.
        self.assertNotRegex(df, r'(?m)^ENV\s+APIFY_TOKEN=.+')
        self.assertNotRegex(df, r'(?m)^ARG\s+APIFY_TOKEN=.+')

    def test_10_package_start_matches_cmd(self):
        pkg = json.loads((ROOT / "package.json").read_text())
        self.assertEqual(pkg["scripts"]["start"], "node src/index.js")
        df = (ROOT / "Dockerfile").read_text()
        self.assertIn('CMD ["node", "src/index.js"]', df)

    def test_11_github_topics_include_mcp(self):
        r = subprocess.run(
            ["gh", "api", "repos/markatdataandbeyond/open-data-mcp", "--jq", ".topics"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(r.returncode, 0, redact(r.stderr))
        topics = json.loads(r.stdout)
        self.assertIn("mcp", topics)
        self.assertIn("model-context-protocol", topics)


if __name__ == "__main__":
    unittest.main(verbosity=2)
