#!/usr/bin/env python3
"""Round 19 TDD: local open-data MCP server (no Apify proxy). Never prints secret values."""
from __future__ import annotations

import json
import os
import re
import select
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTORS = [
    "eu-company-verify",
    "dk-statistics",
    "scholar-search",
    "pubmed-search",
    "eu-tenders",
    "france-company-search",
    "nordic-company-registry",
    "clinical-trials",
    "vin-decoder-recalls",
    "weather-forecast",
]
EXPECTED = [f"dataandbeyond--{a}" for a in ACTORS]
SECRET_KEYS = ("APIFY_TOKEN", "OPENALEX_API_KEY", "NCBI_API_KEY")


def redact(s: str) -> str:
    out = s
    for k in SECRET_KEYS:
        v = os.environ.get(k)
        if v and len(v) > 8:
            out = out.replace(v, "***")
    return out


def docker_bin():
    return shutil.which("docker")


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

    def recv(self, timeout=60):
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


def env_clean():
    e = {k: v for k, v in os.environ.items() if k not in SECRET_KEYS}
    for k in SECRET_KEYS:
        e.pop(k, None)
    return e


def mcp_init_list(client):
    client.send(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "round19", "version": "0"},
            },
        }
    )
    init = client.recv(20)
    assert "result" in init, init
    client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return init


def mcp_call(client, name, arguments, timeout=120):
    client.send(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    )
    return client.recv(timeout)


def result_text(res):
    result = res.get("result") or {}
    parts = [x.get("text", "") for x in (result.get("content") or []) if x.get("type") == "text"]
    return "\n".join(parts), result.get("isError", False)


class TestRound19LocalMcp(unittest.TestCase):
    image = "open-data-mcp:round19"

    # --- overall ---
    def test_01_required_files(self):
        for rel in (
            "Dockerfile",
            "LICENSE",
            "glama.json",
            "package.json",
            "README.md",
            "src/index.js",
            "src/tools.js",
            "src/lib/http.js",
            "src/lib/runTool.js",
            "catalog/tools.json",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_02_mit_license(self):
        text = (ROOT / "LICENSE").read_text()
        self.assertIn("MIT License", text)
        self.assertIn("Data and Beyond", text)

    def test_03_package_and_readme_local(self):
        pkg = json.loads((ROOT / "package.json").read_text())
        self.assertNotIn("proxy", (pkg.get("description") or "").lower())
        readme = (ROOT / "README.md").read_text()
        self.assertIn("Hosted version", readme)
        self.assertIn("apify.com/dataandbeyond", readme)
        self.assertNotIn("thin stdio proxy", readme.lower())
        self.assertNotIn("Actor code itself runs on Apify", readme)

    def test_04_catalog_schemas_10(self):
        tools = json.loads((ROOT / "catalog/tools.json").read_text())
        self.assertEqual(len(tools), 10)
        for t in tools:
            self.assertIn(t["name"], EXPECTED)
            self.assertIsInstance(t.get("inputSchema"), dict)
            self.assertNotIn("This tool calls the Actor", t.get("description", ""))
            self.assertNotIn("mcp.apify.com", t.get("description", ""))

    def test_05_no_apify_forward_in_index(self):
        idx = (ROOT / "src/index.js").read_text()
        self.assertNotIn("callUpstreamTool", idx)
        self.assertNotIn("mcp.apify.com", idx)
        self.assertIn("runTool", idx)

    def test_06_secret_scan(self):
        pats = [
            re.compile(r"apify_api_[A-Za-z0-9]{20,}"),
            re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
            re.compile(r"sk-[A-Za-z0-9]{20,}"),
        ]
        known = [os.environ[k] for k in SECRET_KEYS if os.environ.get(k) and len(os.environ[k]) > 8]
        hits = []
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(ROOT))
            if rel.startswith(("node_modules/", ".git/", "assets/demo/")):
                continue
            if "/.git/" in rel or path.suffix in {".png", ".jpg", ".gif", ".cast", ".lock"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for p in pats:
                if p.search(text):
                    hits.append(f"{rel}:pattern")
            for v in known:
                if v in text:
                    hits.append(f"{rel}:env")
        self.assertEqual(hits, [], hits[:10])

    def test_07_node_tools_list_no_keys(self):
        c = McpClient(["node", "src/index.js"], env=env_clean())
        try:
            mcp_init_list(c)
            c.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            listed = c.recv(15)
            tools = listed["result"]["tools"]
            self.assertEqual(sorted(t["name"] for t in tools), sorted(EXPECTED))
            for t in tools:
                self.assertIn("inputSchema", t)
        finally:
            c.close()

    def test_08_docker_build_and_tools_list(self):
        d = docker_bin()
        self.assertTrue(d, "docker missing")
        build = [d, "build", "--network=host", "-t", self.image, str(ROOT)]
        if os.geteuid() != 0:
            build = ["sudo"] + build
        r = subprocess.run(build, capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, redact((r.stdout + r.stderr)[-1500:]))
        run = [d, "run", "--rm", "-i", "--network", "host", self.image]
        if os.geteuid() != 0:
            run = ["sudo"] + run
        c = McpClient(run, env=env_clean())
        try:
            init = mcp_init_list(c)
            self.assertEqual(init["result"]["serverInfo"]["name"], "open-data-mcp")
            c.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            listed = c.recv(20)
            self.assertEqual(len(listed["result"]["tools"]), 10)
        finally:
            c.close()

    # --- live spot checks (one per tool, no Apify) ---
    def _live(self, name, args, must_contain, timeout=90):
        c = McpClient(["node", "src/index.js"], env=env_clean())
        try:
            mcp_init_list(c)
            res = mcp_call(c, name, args, timeout=timeout)
            blob = json.dumps(res)
            for k in SECRET_KEYS:
                v = os.environ.get(k)
                if v and len(v) > 8:
                    self.assertNotIn(v, blob)
            text, is_err = result_text(res)
            self.assertFalse(is_err, redact(text[:500]))
            self.assertTrue(text.strip(), "empty")
            low = text.lower()
            for needle in must_contain:
                self.assertIn(needle.lower(), low, redact(text[:400]))
            return redact(text[:400])
        finally:
            c.close()

    def test_10_live_eu_company(self):
        ex = self._live(
            "dataandbeyond--eu-company-verify",
            {"queries": ["DK24256790"], "includeParents": False},
            ["verdict", "vat"],
            60,
        )
        print("LIVE_eu-company-verify:", ex[:200])

    def test_11_live_dk_statistics(self):
        ex = self._live(
            "dataandbeyond--dk-statistics",
            {"mode": "search", "search": "population municipality", "maxTables": 2},
            ["tableId"],
            60,
        )
        print("LIVE_dk-statistics:", ex[:200])

    def test_12_live_scholar(self):
        ex = self._live(
            "dataandbeyond--scholar-search",
            {"queries": ["knowledge graph embedding"], "maxResultsPerQuery": 3, "sources": ["crossref", "arxiv"]},
            ["title"],
            90,
        )
        print("LIVE_scholar-search:", ex[:200])

    def test_13_live_pubmed(self):
        ex = self._live(
            "dataandbeyond--pubmed-search",
            {"queries": ["crispr gene editing"], "maxResultsPerQuery": 2},
            ["pmid"],
            60,
        )
        print("LIVE_pubmed-search:", ex[:200])

    def test_14_live_eu_tenders(self):
        ex = self._live(
            "dataandbeyond--eu-tenders",
            {"keywords": "software", "countries": ["DK"], "maxResults": 2, "publishedWithinDays": 90},
            ["publication"],
            90,
        )
        print("LIVE_eu-tenders:", ex[:200])

    def test_15_live_france(self):
        ex = self._live(
            "dataandbeyond--france-company-search",
            {"queries": ["383474814"], "maxResultsPerQuery": 1},
            ["siren"],
            60,
        )
        print("LIVE_france-company-search:", ex[:200])

    def test_16_live_nordic(self):
        ex = self._live(
            "dataandbeyond--nordic-company-registry",
            {"queries": ["923609016"], "countries": ["NO"], "maxResultsPerQuery": 1},
            ["registryId"],
            60,
        )
        print("LIVE_nordic-company-registry:", ex[:200])

    def test_17_live_clinical(self):
        ex = self._live(
            "dataandbeyond--clinical-trials",
            {"condition": "diabetes", "maxResults": 2},
            ["nctId"],
            60,
        )
        print("LIVE_clinical-trials:", ex[:200])

    def test_18_live_vin(self):
        # well-known NHTSA sample VIN pattern; may decode with make
        ex = self._live(
            "dataandbeyond--vin-decoder-recalls",
            {"vins": ["1HGCM82633A004352"], "includeRecalls": False},
            ["vin"],
            60,
        )
        print("LIVE_vin-decoder-recalls:", ex[:200])

    def test_19_live_weather(self):
        ex = self._live(
            "dataandbeyond--weather-forecast",
            {"locations": ["55.6761,12.5683"], "output": "daily", "days": 1},
            ["temperature"],
            60,
        )
        print("LIVE_weather-forecast:", ex[:200])

    # --- edge cases ---
    def test_20_edge_empty_input(self):
        c = McpClient(["node", "src/index.js"], env=env_clean())
        try:
            mcp_init_list(c)
            res = mcp_call(c, "dataandbeyond--weather-forecast", {"locations": []}, 30)
            text, is_err = result_text(res)
            self.assertTrue(is_err or "provide" in text.lower() or "location" in text.lower(), redact(text[:300]))
        finally:
            c.close()

    def test_21_edge_invalid_vin(self):
        c = McpClient(["node", "src/index.js"], env=env_clean())
        try:
            mcp_init_list(c)
            res = mcp_call(
                c,
                "dataandbeyond--vin-decoder-recalls",
                {"vins": ["!!!INVALID!!!"], "includeRecalls": False},
                30,
            )
            text, is_err = result_text(res)
            self.assertFalse(is_err, redact(text[:300]))
            low = text.lower()
            self.assertTrue("invalid" in low or "valid\": false" in low or '"valid":false' in low.replace(" ", ""), redact(text[:400]))
        finally:
            c.close()

    def test_22_edge_invalid_vat_or_spaces(self):
        c = McpClient(["node", "src/index.js"], env=env_clean())
        try:
            mcp_init_list(c)
            res = mcp_call(c, "dataandbeyond--eu-company-verify", {"queries": ["   "]}, 30)
            text, is_err = result_text(res)
            self.assertTrue(is_err or "invalid" in text.lower() or "provide" in text.lower(), redact(text[:300]))
        finally:
            c.close()

    def test_23_edge_unknown_tool(self):
        c = McpClient(["node", "src/index.js"], env=env_clean())
        try:
            mcp_init_list(c)
            res = mcp_call(c, "dataandbeyond--nope", {}, 15)
            text, is_err = result_text(res)
            self.assertTrue(is_err)
            self.assertIn("Unknown tool", text)
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
