#!/usr/bin/env python3
"""Round 20 TDD: local demos (VIES/NHTSA), README Demo, catalog PR hygiene. Never prints secrets."""
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
DEMO = ROOT / "assets" / "demo"
SECRET_KEYS = ("APIFY_TOKEN", "OPENALEX_API_KEY", "NCBI_API_KEY")


def redact(s: str) -> str:
    out = s
    for k in SECRET_KEYS:
        v = os.environ.get(k)
        if v and len(v) > 8:
            out = out.replace(v, "***")
    return out


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


def cast_text(path: Path) -> str:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line.startswith("["):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, list) and len(ev) >= 3 and ev[1] == "o":
            out.append(ev[2])
    return "".join(out)


class Round20DemoAssets(unittest.TestCase):
    def test_01_demo_files_exist(self):
        for name in ("eu-company-verify", "vin-decoder-recalls", "scholar-search"):
            for ext in ("cast", "gif", "png"):
                p = DEMO / f"{name}.{ext}"
                self.assertTrue(p.is_file(), f"missing {p}")
                self.assertGreater(p.stat().st_size, 500, f"too small {p}")

    def test_02_vies_cast_live(self):
        text = cast_text(DEMO / "eu-company-verify.cast")
        self.assertNotIn("Invalid JSON", text)
        self.assertIn("NOVO NORDISK", text)
        self.assertIn("valid=true", text)
        self.assertIn("no Apify token", text)

    def test_03_vin_cast_live(self):
        text = cast_text(DEMO / "vin-decoder-recalls.cast")
        self.assertNotIn("Invalid JSON", text)
        self.assertIn("HONDA", text)
        self.assertIn("recalls:", text)
        self.assertIn("1HGCM82633A004352", text)

    def test_04_scholar_cast_live(self):
        text = cast_text(DEMO / "scholar-search.cast")
        self.assertNotIn("Invalid JSON", text)
        self.assertIn("Knowledge graph", text)
        self.assertIn("DOI", text)

    def test_05_manifest_local_mode(self):
        man = json.loads((DEMO / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(man.get("mode"), "local-stdio")
        for a in ("eu-company-verify", "vin-decoder-recalls", "scholar-search"):
            self.assertIn(a, man["actors"])

    def test_06_readme_demo_local(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Demo", readme)
        self.assertIn("local stdio", readme.lower())
        self.assertIn("NOVO NORDISK", readme)
        self.assertIn("NHTSA", readme)
        self.assertIn("record-local-demos.sh", readme)
        self.assertNotIn("stdio proxy", readme)
        self.assertNotIn("APIFY_TOKEN=… bash scripts/record-demos.sh", readme)

    def test_07_demo_scripts_no_apify_required(self):
        call = (ROOT / "scripts" / "demo-mcp-call.mjs").read_text(encoding="utf-8")
        self.assertNotIn("APIFY_TOKEN env var is required", call)
        local = (ROOT / "scripts" / "demo-local.sh").read_text(encoding="utf-8")
        self.assertIn("DEMO_ARGS", local)
        rec = (ROOT / "scripts" / "record-local-demos.sh").read_text(encoding="utf-8")
        self.assertIn("eu-company-verify", rec)
        self.assertIn("vin-decoder-recalls", rec)

    def test_08_secret_scan_demo_assets(self):
        pat = re.compile(r"(apify_api_[A-Za-z0-9]{10,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,})")
        for p in DEMO.rglob("*"):
            if not p.is_file() or p.suffix in {".gif", ".png"}:
                continue
            data = p.read_text(encoding="utf-8", errors="ignore")
            self.assertIsNone(pat.search(data), f"secret-like token in {p}")
            for k in SECRET_KEYS:
                v = os.environ.get(k)
                if v and len(v) > 8:
                    self.assertNotIn(v, data, f"env secret leaked in {p}")


class Round20LiveSpot(unittest.TestCase):
    def _call(self, tool: str, args: dict):
        client = McpClient(["node", "src/index.js"], env=env_clean())
        try:
            client.send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "round20", "version": "1"},
                    },
                }
            )
            init = client.recv()
            self.assertIn("result", init)
            client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            client.send(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool, "arguments": args},
                }
            )
            res = client.recv(timeout=180)
            self.assertIn("result", res)
            return res["result"]
        finally:
            client.close()

    def test_09_live_vies(self):
        result = self._call("dataandbeyond--eu-company-verify", {"queries": ["DK24256790"]})
        self.assertFalse(result.get("isError"))
        text = "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
        self.assertIn("NOVO NORDISK", text)
        self.assertIn('"valid": true', text)

    def test_10_live_vin(self):
        result = self._call(
            "dataandbeyond--vin-decoder-recalls",
            {"vins": ["1HGCM82633A004352"]},
        )
        self.assertFalse(result.get("isError"))
        text = "".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
        self.assertIn("HONDA", text)
        self.assertIn("Accord", text)

    def test_11_edge_empty_queries(self):
        result = self._call("dataandbeyond--eu-company-verify", {"queries": []})
        self.assertTrue(result.get("isError") or "Provide at least one" in json.dumps(result))

    def test_12_edge_invalid_vin(self):
        result = self._call("dataandbeyond--vin-decoder-recalls", {"vins": ["!!!INVALID!!!"]})
        text = json.dumps(result)
        self.assertTrue(
            result.get("isError")
            or '"valid": false' in text
            or "Invalid" in text
            or "invalid" in text.lower()
        )

    def test_13_edge_whitespace_query(self):
        result = self._call("dataandbeyond--eu-company-verify", {"queries": ["   "]})
        text = json.dumps(result)
        self.assertTrue(result.get("isError") or "Provide at least one" in text or "Invalid" in text)


class Round20Regression(unittest.TestCase):
    def test_14_tools_list_ten(self):
        client = McpClient(["node", "src/index.js"], env=env_clean())
        try:
            client.send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "round20", "version": "1"},
                    },
                }
            )
            client.recv()
            client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            client.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            listed = client.recv()
            names = [t["name"] for t in listed["result"]["tools"]]
            self.assertEqual(len(names), 10)
            self.assertIn("dataandbeyond--eu-company-verify", names)
            self.assertIn("dataandbeyond--vin-decoder-recalls", names)
        finally:
            client.close()

    def test_15_no_apify_proxy_in_index(self):
        idx = (ROOT / "src" / "index.js").read_text(encoding="utf-8")
        self.assertNotIn("mcp.apify.com", idx)
        self.assertNotIn("callUpstreamTool", idx)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(Round20DemoAssets))
    suite.addTests(loader.loadTestsFromTestCase(Round20LiveSpot))
    suite.addTests(loader.loadTestsFromTestCase(Round20Regression))
    # Also run round19 for full suite confidence
    round19 = ROOT / "tests" / "test_round19.py"
    if round19.exists():
        import importlib.util

        spec = importlib.util.spec_from_file_location("test_round19", round19)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        suite.addTests(loader.loadTestsFromModule(mod))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"\nSUMMARY: ran={result.testsRun} failures={len(result.failures)} errors={len(result.errors)}")
    sys.exit(0 if result.wasSuccessful() else 1)
