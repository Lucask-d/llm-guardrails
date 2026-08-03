"""
test_llm_and_guardrails.py

10 core functional tests for:
- LLM microservice (port 3000): POST /llm -> {"output": "..."}
- Guardrails microservice (port 3001): PUT/GET/DELETE /guardrails/<id>, GET /guardrails

Run:
    python -m unittest -v test_llm_and_guardrails.py

Assumptions:
- Services are already running locally:
    LLM       http://localhost:3000
    Guardrails http://localhost:3001
"""

import json
import socket
import time
import uuid
import unittest
from urllib import request, error

LLM_BASE = "http://localhost:3000"
GUARD_BASE = "http://localhost:3001"

DEFAULT_TIMEOUT_SECS = 15


def _tcp_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_json(method: str, url: str, payload=None, timeout: int = DEFAULT_TIMEOUT_SECS):
    """
    Perform an HTTP request with JSON body (if payload not None) and parse JSON response (if any).
    Returns: (status_code:int, response_json_or_None, raw_text:str)
    """
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url=url, data=data, headers=headers, method=method)

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8", errors="replace").strip()
            if raw:
                try:
                    return status, json.loads(raw), raw
                except json.JSONDecodeError:
                    return status, None, raw
            return status, None, ""
    except error.HTTPError as e:
        status = e.code
        raw = e.read().decode("utf-8", errors="replace").strip()
        try:
            return status, json.loads(raw) if raw else None, raw
        except json.JSONDecodeError:
            return status, None, raw
    except Exception as e:
        # Connection errors, timeouts, etc.
        raise RuntimeError(f"Request failed: {method} {url} ({type(e).__name__}: {e})")


def is_2xx(code: int) -> bool:
    return 200 <= code <= 299


class TestLLMService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _tcp_open("localhost", 3000):
            raise unittest.SkipTest("LLM service not reachable on localhost:3000")
        # Give the service a moment if it was just started
        time.sleep(0.2)

    def test_01_llm_happy_path_returns_output_string(self):
        status, body, raw = http_json(
            "POST",
            f"{LLM_BASE}/llm",
            payload={"prompt": "Reply with a single short sentence."},
        )
        self.assertTrue(is_2xx(status), f"Expected 2xx, got {status}. Raw: {raw}")
        self.assertIsInstance(body, dict, f"Expected JSON object, got: {body} raw={raw}")
        self.assertIn("output", body, f"Missing 'output'. Body: {body}")
        self.assertIsInstance(body["output"], str, f"'output' should be str. Body: {body}")
        self.assertGreater(len(body["output"].strip()), 0, f"'output' should be non-empty. Body: {body}")

    def test_02_llm_missing_prompt_should_be_4xx(self):
        status, body, raw = http_json("POST", f"{LLM_BASE}/llm", payload={})
        self.assertTrue(400 <= status <= 499, f"Expected 4xx, got {status}. Raw: {raw}")

    def test_03_llm_prompt_not_string_should_be_4xx(self):
        status, body, raw = http_json("POST", f"{LLM_BASE}/llm", payload={"prompt": {"oops": 1}})
        self.assertTrue(400 <= status <= 499, f"Expected 4xx, got {status}. Raw: {raw}")

    def test_04_llm_wrong_method_get_should_not_succeed(self):
        # Spec only defines POST /llm. GET should not succeed.
        status, body, raw = http_json("GET", f"{LLM_BASE}/llm")
        self.assertFalse(is_2xx(status), f"Expected non-2xx for GET /llm, got {status}. Raw: {raw}")


class TestGuardrailsService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _tcp_open("localhost", 3001):
            raise unittest.SkipTest("Guardrails service not reachable on localhost:3001")
        time.sleep(0.2)

    def setUp(self):
        # Create a unique guardrail id per test run to avoid clashes in Firebase.
        self.gid = f"t-{uuid.uuid4().hex[:12]}"
        self.url_item = f"{GUARD_BASE}/guardrails/{self.gid}"

    def _create_guardrail(self, regx=r"\bSECRET\b", sub="[REDACTED]"):
        payload = {"id": self.gid, "regx": regx, "sub": sub}
        return http_json("PUT", self.url_item, payload=payload)

    def _delete_guardrail(self):
        return http_json("DELETE", self.url_item)

    def test_05_guardrails_put_create_returns_2xx_and_echoes_fields(self):
        status, body, raw = self._create_guardrail()
        self.assertTrue(is_2xx(status), f"Expected 2xx, got {status}. Raw: {raw}")
        self.assertIsInstance(body, dict, f"Expected JSON object, got: {body} raw={raw}")
        # Many implementations echo the object back; if yours doesn't, adjust this part.
        for k in ("id", "regx", "sub"):
            self.assertIn(k, body, f"Missing '{k}' in response. Body: {body}")
        self.assertEqual(body["id"], self.gid, f"Returned id mismatch. Body: {body}")

    def test_06_guardrails_get_after_put_returns_same_guardrail(self):
        s1, b1, r1 = self._create_guardrail(regx=r"\d{16}", sub="[CARD]")
        self.assertTrue(is_2xx(s1), f"Create failed: {s1} raw={r1}")

        status, body, raw = http_json("GET", self.url_item)
        self.assertTrue(is_2xx(status), f"Expected 2xx, got {status}. Raw: {raw}")
        self.assertIsInstance(body, dict)
        self.assertEqual(body.get("id"), self.gid)
        self.assertEqual(body.get("regx"), r"\d{16}")
        self.assertEqual(body.get("sub"), "[CARD]")

    def test_07_guardrails_list_contains_created_id(self):
        s1, b1, r1 = self._create_guardrail(regx="foo", sub="bar")
        self.assertTrue(is_2xx(s1), f"Create failed: {s1} raw={r1}")

        status, body, raw = http_json("GET", f"{GUARD_BASE}/guardrails")
        self.assertTrue(is_2xx(status), f"Expected 2xx, got {status}. Raw: {raw}")
        self.assertIsInstance(body, list, f"Expected a JSON list of ids. Body: {body} raw={raw}")
        self.assertIn(self.gid, body, f"Created id not found in list. list={body}")

    def test_08_guardrails_delete_then_get_should_be_404(self):
        s1, b1, r1 = self._create_guardrail()
        self.assertTrue(is_2xx(s1), f"Create failed: {s1} raw={r1}")

        sdel, bdel, rdel = self._delete_guardrail()
        self.assertTrue(is_2xx(sdel) or sdel == 404, f"Expected 2xx/404 on delete, got {sdel}. Raw: {rdel}")

        status, body, raw = http_json("GET", self.url_item)
        self.assertTrue(status == 404 or (400 <= status <= 499), f"Expected 404/4xx, got {status}. Raw: {raw}")

    def test_09_guardrails_put_missing_fields_should_be_4xx(self):
        # Missing regx/sub
        status, body, raw = http_json("PUT", self.url_item, payload={"id": self.gid})
        self.assertTrue(400 <= status <= 499, f"Expected 4xx, got {status}. Raw: {raw}")

    def test_10_guardrails_put_invalid_regex_should_be_4xx(self):
        # A regex that should fail to compile in Python's re module
        invalid = r"([A-Z"  # missing closing bracket/paren
        status, body, raw = self._create_guardrail(regx=invalid, sub="X")
        # Recommended behaviour: reject invalid regex with 4xx.
        self.assertTrue(
            400 <= status <= 499,
            f"Expected 4xx for invalid regex, got {status}. Raw: {raw}\n"
            f"If you intentionally allow storing invalid regex, adjust this test."
        )

    def tearDown(self):
        # Best-effort cleanup (don't fail tests if cleanup fails)
        try:
            self._delete_guardrail()
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
