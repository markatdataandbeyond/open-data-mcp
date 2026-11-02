#!/usr/bin/env python3
"""Round 22 TDD: catalog listing verification + scholar live for draft. Never prints secrets."""
from __future__ import annotations

import json
import os
import re
import select
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET_KEYS = ("APIFY_TOKEN", "OPENALEX_API_KEY", "NCBI_API_KEY")
README = (ROOT / "README.md").read_text(encoding="utf-8")

GLAMA = "https://glama.ai/mcp/servers/markatdataandbeyond/open-data-mcp"
LOBEHUB = "https://market.lobehub.com/s/plugins/markatdataandbeyond-open-data-mcp"
SMITHERY = "https://www.smithery.ai/server/@markatdataandbeyond/open-data-mcp"
MCPSO = "https://mcp.so/server/open-data-mcp"
SCHOLAR_GIF = "https://raw.githubusercontent.com/markatdataandbeyond/open-data-mcp/main/assets/demo/scholar-search.gif"


def redact(s: str) -> str:
    out = s
    for k in SECRET_KEYS:
        v = os.environ.get(k)
        if v and len(v) > 8:
            out = out.replace(v, "***")
    return out


def http_get(url: str, timeout: int = 45):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "open-data-mcp-round22-tests/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return r.status, r.geturl(), body
    except urllib.error.HTTPError as e:
        return e.code, url, e.read() if e.fp else b""


def env_clean():
    e = {k: v for k, v in os.environ.items() if k not in SECRET_KEYS}
    for k in SECRET_KEYS:
        e.pop(k, None)
    return e


class McpClient:
    def __init__(self, cmd, env=None, cwd=None):
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env,
            cwd=cwd or str(ROOT),
        )

    def send(self, obj):
        assert self.proc.stdin
        self.proc.stdin.write(json.dumps(obj) + "\n")
        self.proc.stdin.flush()

    def recv(self, timeout=120):
        assert self.proc.stdout
        end = time.time() + timeout
        buf = ""
        while time.time() < end:
            r, _, _ = select.select([self.proc.stdout], [], [], 0.25)
            if not r:
                if self.proc.poll() is not None:
                    err = self.proc.stderr.read() if self.proc.stderr else ""
                    raise RuntimeError(redact(f"exited: {self.proc.returncode} {err[:400]}"))
                continue
            chunk = self.proc.stdout.readline()
            if not chunk:
                break
            buf += chunk
            try:
                return json.loads(buf)
            except json.JSONDecodeError:
                continue
        raise TimeoutError(redact(buf[:500] or "no MCP output"))

    def close(self):
        try:
            self.proc.terminate()
        except Exception:
            pass


class Round22Catalog(unittest.TestCase):
    def test_01_readme_open_source_first(self):
        self.assertIn("open-source MCP server", README)
        self.assertIn("## Try in 30 seconds", README)
        self.assertIn("## Hosted version", README)
        # Hosted comes after Tools / Run locally
        self.assertLess(README.index("## Tools"), README.index("## Hosted version"))

    def test_02_glama_listing_http_200(self):
        status, final, body = http_get(GLAMA)
        self.assertEqual(status, 200, f"glama {status} {final}")
        text = body.decode("utf-8", errors="replace")
        self.assertIn("markatdataandbeyond/open-data-mcp", text)
        self.assertTrue(
            "open data" in text.lower() or "open-data" in text.lower(),
            "glama page missing open-data wording",
        )

    def test_03_lobehub_listing_http_200(self):
        status, final, body = http_get(LOBEHUB)
        self.assertEqual(status, 200, f"lobehub {status} {final}")
        text = body.decode("utf-8", errors="replace")
        self.assertIn("markatdataandbeyond-open-data-mcp", text)
        self.assertIn("github.com/markatdataandbeyond/open-data-mcp", text)

    def test_04_lobehub_metadata_vs_readme(self):
        """Live LobeHub page is Apify-remote-first; README is local OSS-first. Document gap."""
        status, _, body = http_get(LOBEHUB)
        self.assertEqual(status, 200)
        text = body.decode("utf-8", errors="replace")
        # Matching: repo URL + identifier
        self.assertIn("github.com/markatdataandbeyond/open-data-mcp", text)
        self.assertIn("markatdataandbeyond-open-data-mcp", text)
        # Known drift (update needs LobeHub OAuth — not done this round)
        self.assertIn("Apify", text)
        self.assertIn("APIFY_TOKEN", text)
        self.assertRegex(text, r"Connection Type:\*\*\s*remote|Connection Type:</[^>]+>\s*remote|remote")
        # README still leads with local free server
        self.assertIn("no Apify token required for the local server", README)

    def test_05_smithery_not_listed(self):
        status, _, _ = http_get(SMITHERY)
        self.assertEqual(status, 404, "unexpected smithery listing")

    def test_06_mcpso_not_listed(self):
        status, _, _ = http_get(MCPSO)
        self.assertEqual(status, 404, "unexpected mcp.so listing")

    def test_07_scholar_gif_raw_200(self):
        status, _, body = http_get(SCHOLAR_GIF)
        self.assertEqual(status, 200)
        self.assertGreater(len(body), 1000)

    def test_08_testdok_exists(self):
        p = ROOT / "tests" / "round22-testdok.md"
        self.assertTrue(p.is_file())
        t = p.read_text(encoding="utf-8")
        self.assertIn("Smithery", t)
        self.assertIn("mcp.so", t)
        self.assertIn("PulseMCP", t)
        self.assertIn("LobeHub", t)
        self.assertIn("kant", t.lower())


class Round22LiveScholar(unittest.TestCase):
    def setUp(self):
        self.client = McpClient(["node", "src/index.js"], env=env_clean())
        self.client.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "round22", "version": "1"},
        }})
        self.client.recv()
        self.client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def tearDown(self):
        self.client.close()

    def _call(self, name, arguments):
        self.client.send({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        })
        return self.client.recv()

    def test_09_scholar_live_kge(self):
        resp = self._call(
            "dataandbeyond--scholar-search",
            {"queries": ["knowledge graph embedding"], "maxResults": 2},
        )
        result = resp.get("result") or {}
        self.assertFalse(result.get("isError"), redact(json.dumps(resp)[:400]))
        text = ""
        for c in result.get("content") or []:
            if c.get("type") == "text":
                text += c.get("text") or ""
        self.assertIn("10.1016/j.knosys.2018.10.008", text)

    def test_10_edge_empty_queries(self):
        resp = self._call("dataandbeyond--scholar-search", {"queries": []})
        result = resp.get("result") or {}
        self.assertTrue(result.get("isError") or "error" in json.dumps(resp).lower())

    def test_11_edge_blank_query(self):
        resp = self._call("dataandbeyond--scholar-search", {"queries": ["   "]})
        result = resp.get("result") or {}
        self.assertTrue(result.get("isError") or "error" in json.dumps(resp).lower())

    def test_12_edge_missing_queries_key(self):
        resp = self._call("dataandbeyond--scholar-search", {"query": "knowledge graph embedding"})
        result = resp.get("result") or {}
        # Wrong field name must fail loudly
        self.assertTrue(result.get("isError") or "error" in json.dumps(resp).lower())


class Round22Secrets(unittest.TestCase):
    def test_13_no_secrets_in_round22_artefacts(self):
        paths = [
            ROOT / "tests" / "test_round22.py",
            ROOT / "tests" / "round22-testdok.md",
            ROOT / "README.md",
        ]
        draft = Path("/workspace/venture/apify-actors/drafts/devto-scholar-search-2026-11-02.md")
        if draft.is_file():
            paths.append(draft)
        for p in paths:
            text = p.read_text(encoding="utf-8")
            for k in SECRET_KEYS:
                v = os.environ.get(k)
                if v and len(v) > 8:
                    self.assertNotIn(v, text, f"secret leaked in {p}")
            self.assertNotRegex(text, r"apify_api_[A-Za-z0-9]{10,}")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
