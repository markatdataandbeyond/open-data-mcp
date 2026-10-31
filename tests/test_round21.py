#!/usr/bin/env python3
"""Round 21 TDD: 'Try in 30 seconds' sections + live spot checks. Never prints secrets."""
from __future__ import annotations

import json
import os
import re
import select
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTORS = Path("/workspace/venture/apify-actors")
SECRET_KEYS = ("APIFY_TOKEN", "OPENALEX_API_KEY", "NCBI_API_KEY")
TOP3 = ("eu-company-verify", "scholar-search", "eu-tenders")
SECTION_RE = re.compile(r"^## Try in 30 seconds\s*$", re.M)


def redact(s: str) -> str:
    out = s
    for k in SECRET_KEYS:
        v = os.environ.get(k)
        if v and len(v) > 8:
            out = out.replace(v, "***")
    return out


class McpClient:
    def __init__(self, cmd, env=None, cwd=None):
        e = {k: v for k, v in os.environ.items() if k not in SECRET_KEYS}
        if env:
            e.update(env)
        for k in SECRET_KEYS:
            e.pop(k, None)
        # keep OPENALEX optional if explicitly passed via env arg
        if env and "OPENALEX_API_KEY" in env:
            e["OPENALEX_API_KEY"] = env["OPENALEX_API_KEY"]
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=e,
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
                    raise RuntimeError(redact(f"process exited: {self.proc.returncode} {err[:400]}"))
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
            self.proc.wait(timeout=3)
        except Exception:
            self.proc.kill()


def call_tool(name: str, arguments: dict, timeout=120):
    c = McpClient(["node", "src/index.js"])
    try:
        c.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "round21", "version": "0"},
                },
            }
        )
        c.recv(timeout=30)
        c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        c.send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        r = c.recv(timeout=timeout)
        text = (r.get("result") or {}).get("content", [{}])[0].get("text") or ""
        is_err = (r.get("result") or {}).get("isError", False)
        try:
            data = json.loads(text)
        except Exception:
            data = text
        return data, is_err, r
    finally:
        c.close()


class TestRound21Sections(unittest.TestCase):
    def test_01_open_data_mcp_readme_has_try_section_near_top(self):
        md = (ROOT / "README.md").read_text(encoding="utf-8")
        m = SECTION_RE.search(md)
        self.assertIsNotNone(m, "README.md missing '## Try in 30 seconds'")
        # Must appear before ## Tools
        tools = md.find("## Tools")
        self.assertGreater(tools, 0)
        self.assertLess(m.start(), tools, "Try section must be above ## Tools")

    def test_02_open_data_mcp_readme_has_copy_paste_and_live_marker(self):
        md = (ROOT / "README.md").read_text(encoding="utf-8")
        sec = md[md.index("## Try in 30 seconds") : md.index("## Tools")]
        self.assertIn("```bash", sec)
        self.assertIn("demo-mcp-call.mjs", sec)
        self.assertIn("DK24256790", sec)
        self.assertIn("NOVO NORDISK A/S", sec)
        self.assertIn("549300DAQ1CVT6CXN342", sec)

    def test_03_04_05_actor_readmes_have_try_section(self):
        for name in TOP3:
            with self.subTest(actor=name):
                md = (ACTORS / name / "README.md").read_text(encoding="utf-8")
                m = SECTION_RE.search(md)
                self.assertIsNotNone(m, f"{name} missing Try in 30 seconds")
                # Near top: before ## Example input or ## Demo or ## How it works
                rest = md[m.end() :]
                self.assertIn("```", rest[:800], f"{name} missing code fence near section")
                self.assertRegex(rest[:2500], r"```(?:bash|json|sh)")

    def test_06_eu_company_actor_readme_output(self):
        md = (ACTORS / "eu-company-verify" / "README.md").read_text(encoding="utf-8")
        sec = md[md.index("## Try in 30 seconds") :][:2500]
        self.assertIn("DK24256790", sec)
        self.assertIn("NOVO NORDISK A/S", sec)
        self.assertIn("run-sync-get-dataset-items", sec)

    def test_07_scholar_actor_readme_output(self):
        md = (ACTORS / "scholar-search" / "README.md").read_text(encoding="utf-8")
        sec = md[md.index("## Try in 30 seconds") :][:2500]
        self.assertIn("knowledge graph embedding", sec)
        self.assertTrue(
            "10.1016/j.knosys.2018.10.008" in sec or "DOI" in sec,
            "scholar section needs a real DOI or DOI label from live output",
        )

    def test_08_eu_tenders_actor_readme_output(self):
        md = (ACTORS / "eu-tenders" / "README.md").read_text(encoding="utf-8")
        sec = md[md.index("## Try in 30 seconds") :][:3000]
        self.assertTrue("ted.europa.eu" in sec.lower() or "TED" in sec)
        self.assertIn("run-sync-get-dataset-items", sec)
        self.assertTrue(
            any(x in sec for x in ("753508-2026", "AffaldPlus", "publicationNumber", "buyerName")),
            "eu-tenders section needs a real live field",
        )

    def test_09_secret_scan_touched_readmes(self):
        paths = [ROOT / "README.md"] + [ACTORS / n / "README.md" for n in TOP3]
        for p in paths:
            text = p.read_text(encoding="utf-8")
            for k in SECRET_KEYS:
                v = os.environ.get(k)
                if v and len(v) > 8:
                    self.assertNotIn(v, text, f"{p} leaked {k}")
            self.assertNotRegex(text, r"apify_api_[A-Za-z0-9]{10,}")


class TestRound21Live(unittest.TestCase):
    def test_10_live_eu_company(self):
        data, err, _ = call_tool(
            "dataandbeyond--eu-company-verify", {"queries": ["DK24256790"]}
        )
        self.assertFalse(err)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        row = data[0]
        self.assertEqual(row.get("vat", {}).get("name"), "NOVO NORDISK A/S")
        self.assertTrue(row.get("vat", {}).get("valid"))
        self.assertEqual(row.get("lei", {}).get("lei"), "549300DAQ1CVT6CXN342")

    def test_11_live_scholar(self):
        data, err, _ = call_tool(
            "dataandbeyond--scholar-search",
            {"queries": ["knowledge graph embedding"], "maxResultsPerQuery": 2},
        )
        self.assertFalse(err)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        self.assertTrue(any(r.get("doi") for r in data))

    def test_12_live_eu_tenders(self):
        data, err, _ = call_tool(
            "dataandbeyond--eu-tenders",
            {"countries": ["DK"], "publishedWithinDays": 14, "maxResults": 2},
        )
        self.assertFalse(err)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        self.assertTrue(data[0].get("publicationNumber") or data[0].get("title"))


class TestRound21Edges(unittest.TestCase):
    def test_13_empty_queries_eu_company(self):
        data, err, raw = call_tool("dataandbeyond--eu-company-verify", {"queries": []})
        # empty should error or return clear failure
        text = json.dumps(data) if not isinstance(data, str) else data
        text += json.dumps(raw)
        self.assertTrue(err or re.search(r"empty|required|at least|invalid|queries", text, re.I))

    def test_14_whitespace_query(self):
        data, err, raw = call_tool(
            "dataandbeyond--eu-company-verify", {"queries": ["   "]}
        )
        text = json.dumps(data) if not isinstance(data, str) else data
        text += json.dumps(raw)
        self.assertTrue(err or re.search(r"space|empty|invalid|FAILED|whitespace", text, re.I))

    def test_15_invalid_cpv_eu_tenders(self):
        data, err, raw = call_tool(
            "dataandbeyond--eu-tenders",
            {"cpvCodes": ["abc"], "maxResults": 1},
        )
        text = json.dumps(data) if not isinstance(data, str) else data
        text += json.dumps(raw)
        self.assertTrue(err or re.search(r"Invalid CPV|CPV|invalid", text, re.I))


if __name__ == "__main__":
    # Expect FAIL before README edits
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    r = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if r.wasSuccessful() else 1)
