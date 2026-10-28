#!/usr/bin/env python3
"""TDD tests for Glama stdio MCP proxy. Never prints secret values."""
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
EXPECTED_TOOLS = [f"dataandbeyond--{a}" for a in ACTORS]
SECRET_KEYS = ("APIFY_TOKEN", "OPENALEX_API_KEY")
TOKEN = os.environ.get("APIFY_TOKEN", "")


def redact(s: str) -> str:
    out = s
    for k in SECRET_KEYS:
        v = os.environ.get(k)
        if v and len(v) > 8:
            out = out.replace(v, "***")
    return out


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

    def recv(self, timeout=30):
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


def env_without_token():
    e = {k: v for k, v in os.environ.items() if k != "APIFY_TOKEN"}
    e.pop("APIFY_TOKEN", None)
    return e


class TestGlamaProxy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docker = shutil_which_docker()
        cls.image = "open-data-mcp:test"

    # --- overall ---
    def test_01_files_present(self):
        for rel in (
            "Dockerfile",
            "glama.json",
            "package.json",
            "src/index.js",
            "src/forward.js",
            "src/tools.js",
            "catalog/tools.json",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_02_glama_json(self):
        g = json.loads((ROOT / "glama.json").read_text())
        self.assertEqual(g.get("$schema"), "https://glama.ai/mcp/schemas/server.json")
        self.assertIn("markatdataandbeyond", g.get("maintainers") or [])

    def test_03_catalog_exactly_10(self):
        tools = json.loads((ROOT / "catalog/tools.json").read_text())
        self.assertEqual(len(tools), 10)
        names = [t["name"] for t in tools]
        self.assertEqual(sorted(names), sorted(EXPECTED_TOOLS))

    def test_04_no_secrets_in_repo_files(self):
        pats = [
            re.compile(r"apify_api_[A-Za-z0-9]{20,}"),
            re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
        ]
        known = [os.environ[k] for k in SECRET_KEYS if os.environ.get(k) and len(os.environ[k]) > 8]
        hits = 0
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(ROOT))
            if rel.startswith("node_modules/") or "/.git/" in rel or rel.startswith(".git/"):
                continue
            if path.suffix in {".png", ".jpg", ".lock"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            hits += sum(1 for p in pats if p.search(text))
            hits += sum(1 for v in known if v in text)
        self.assertEqual(hits, 0, "secret-like values found in repo files")

    def test_05_docker_build(self):
        self.assertTrue(self.docker, "docker CLI missing")
        # host network: local dockerd has no bridge/iptables; Glama's builders are fine
        cmd = [self.docker, "build", "--network=host", "-t", self.image, str(ROOT)]
        if os.geteuid() != 0 and self.docker == "docker":
            cmd = ["sudo"] + cmd
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        out = redact(r.stdout + "\n" + r.stderr)
        self.assertEqual(r.returncode, 0, out[-1500:])

    def test_06_docker_start_tools_list_no_token(self):
        self.assertTrue(self.docker)
        run = [self.docker, "run", "--rm", "-i", "--network", "host", self.image]
        if os.geteuid() != 0 and self.docker == "docker":
            run = ["sudo"] + run
        c = McpClient(run, env=env_without_token())
        try:
            c.send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "glama-test", "version": "0"},
                    },
                }
            )
            init = c.recv(20)
            self.assertIn("result", init)
            self.assertEqual(init["result"]["serverInfo"]["name"], "open-data-mcp")
            c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            c.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            listed = c.recv(20)
            tools = listed["result"]["tools"]
            names = [t["name"] for t in tools]
            self.assertEqual(len(tools), 10)
            self.assertEqual(sorted(names), sorted(EXPECTED_TOOLS))
        finally:
            c.close()

    def test_07_node_tools_list_no_token(self):
        c = McpClient(["node", "src/index.js"], env=env_without_token())
        try:
            c.send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "t", "version": "0"},
                    },
                }
            )
            c.recv(10)
            c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            c.send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            listed = c.recv(10)
            self.assertEqual(len(listed["result"]["tools"]), 10)
        finally:
            c.close()

    # --- live spot check ---
    def test_08_live_weather_call_with_token(self):
        if not TOKEN:
            self.skipTest("APIFY_TOKEN not set")
        env = dict(os.environ)
        c = McpClient(["node", "src/index.js"], env=env)
        try:
            c.send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "live", "version": "0"},
                    },
                }
            )
            c.recv(10)
            c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            c.send(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "dataandbeyond--weather-forecast",
                        "arguments": {"locations": ["Copenhagen"], "output": "daily", "days": 1},
                    },
                }
            )
            res = c.recv(120)
            blob = json.dumps(res)
            self.assertNotIn(TOKEN, blob)
            result = res.get("result") or {}
            self.assertFalse(result.get("isError"), redact(json.dumps(result)[:400]))
            text = "\n".join(
                x.get("text", "") for x in (result.get("content") or []) if x.get("type") == "text"
            )
            self.assertTrue(text, "empty live result")
            # write excerpt for testdok (no secrets)
            excerpt = redact(text[:500])
            (ROOT / "tests" / "_live_weather_excerpt.txt").write_text(excerpt + "\n", encoding="utf-8")
            self.assertTrue(
                "weather-forecast" in text or "Copenhagen" in text or "SUCCEEDED" in text or "location" in text.lower(),
                excerpt,
            )
            print("LIVE_EXCERPT:", excerpt[:240])
        finally:
            c.close()

    # --- edge cases ---
    def test_09_edge_missing_token_clear_error(self):
        c = McpClient(["node", "src/index.js"], env=env_without_token())
        try:
            c.send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "t", "version": "0"},
                    },
                }
            )
            c.recv(10)
            c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            c.send(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "dataandbeyond--weather-forecast",
                        "arguments": {"locations": ["Copenhagen"], "days": 1},
                    },
                }
            )
            res = c.recv(10)
            result = res["result"]
            self.assertTrue(result.get("isError"))
            text = result["content"][0]["text"]
            self.assertIn("APIFY_TOKEN", text)
            self.assertIn("required", text.lower())
        finally:
            c.close()

    def test_10_edge_unknown_tool(self):
        c = McpClient(["node", "src/index.js"], env=env_without_token())
        try:
            c.send(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "t", "version": "0"},
                    },
                }
            )
            c.recv(10)
            c.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            c.send(
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "dataandbeyond--does-not-exist", "arguments": {}},
                }
            )
            res = c.recv(10)
            self.assertTrue(res["result"].get("isError"))
            self.assertIn("Unknown tool", res["result"]["content"][0]["text"])
        finally:
            c.close()

    def test_11_edge_timeout_or_upstream_error(self):
        """Force a fast timeout against a blackhole host via injected fetch in unit style.

        Uses OPEN_DATA_MCP_TIMEOUT_MS=1 with a fake upstream by patching through env
        is hard; instead call forward.js via a tiny node harness that stubs fetch.
        """
        harness = r"""
import { callUpstreamTool } from './src/forward.js';
const fakeFetch = (url, opts = {}) => new Promise((resolve, reject) => {
  const signal = opts.signal;
  if (signal) {
    if (signal.aborted) return reject(Object.assign(new Error('aborted'), { name: 'AbortError' }));
    signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })));
  }
  // never resolve — timeout must win
});
try {
  await callUpstreamTool({
    name: 'dataandbeyond--weather-forecast',
    args: { locations: ['X'] },
    token: 'dummy-token-not-real-000',
    timeoutMs: 30,
    fetchImpl: fakeFetch,
  });
  console.log(JSON.stringify({ ok: false, reason: 'expected timeout' }));
} catch (e) {
  console.log(JSON.stringify({ ok: e.code === 'TIMEOUT', code: e.code, message: e.message }));
}
"""
        r = subprocess.run(
            ["node", "--input-type=module", "-e", harness],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(r.returncode, 0, redact(r.stderr))
        data = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertTrue(data.get("ok"), data)
        self.assertEqual(data.get("code"), "TIMEOUT")

    def test_12_edge_upstream_http_error_redacted(self):
        harness = r"""
import { callUpstreamTool } from './src/forward.js';
const fakeFetch = async () => new Response('nope UPSTREAM_BODY_SHOULD_NOT_LEAK_TOKEN', { status: 502 });
try {
  await callUpstreamTool({
    name: 'dataandbeyond--weather-forecast',
    args: {},
    token: 'dummy-token-not-real-000',
    timeoutMs: 5000,
    fetchImpl: fakeFetch,
  });
  console.log(JSON.stringify({ ok: false }));
} catch (e) {
  console.log(JSON.stringify({
    ok: e.code === 'UPSTREAM_ERROR',
    code: e.code,
    hasFakeTokenLeak: String(e.message).includes('dummy-token-not-real-000'),
    statusPhrase: String(e.message).includes('502'),
  }));
}
"""
        r = subprocess.run(
            ["node", "--input-type=module", "-e", harness],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(r.returncode, 0, redact(r.stderr))
        data = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertTrue(data.get("ok"), data)
        self.assertFalse(data.get("hasFakeTokenLeak"))
        self.assertTrue(data.get("statusPhrase"))


def shutil_which_docker():
    for cand in ("docker", "/usr/local/bin/docker"):
        if Path(cand).name == "docker" and subprocess.run(["which", "docker"], capture_output=True).returncode == 0:
            return "docker"
        if Path(cand).is_file():
            return cand
    return None


if __name__ == "__main__":
    # Compact PASS/FAIL lines for Mark/Venture Lead
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestGlamaProxy)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"\n{result.testsRun - len(result.failures) - len(result.errors)}/{result.testsRun} passed")
    sys.exit(0 if result.wasSuccessful() else 1)
