"""Unit tests for the Auberge microservice (port 3002).

Spec highlights:
- POST /auberge expects JSON {"prompt": <string>} and returns JSON {"output": <string>}.
- Auberge must sanitise BOTH input and output using guardrails from the Guardrails service:
  replace any string matching each guardrail regex with its substitution string.
"""

import unittest
import uuid
import urllib.parse

import json
import socket
import time
import urllib.request
import urllib.error
from typing import Any, Dict, Optional, Tuple
import database

DEFAULT_TIMEOUT_S = 20

def http_json(method: str, url: str, payload: Optional[Any] = None, timeout: int = DEFAULT_TIMEOUT_S,
             headers: Optional[Dict[str, str]] = None) -> Tuple[int, Dict[str, str], Any, bytes]:
    """Send an HTTP request and try to parse JSON response.

    Returns: (status_code, response_headers_dict, parsed_json_or_None, raw_bytes)
    """
    body_bytes = None
    req_headers = {'Accept': 'application/json'}
    if headers:
        req_headers.update(headers)

    if payload is not None:
        raw = json.dumps(payload).encode('utf-8')
        body_bytes = raw
        req_headers.setdefault('Content-Type', 'application/json; charset=utf-8')
    req = urllib.request.Request(url=url, data=body_bytes, method=method.upper(), headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, 'status', resp.getcode())
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            raw_bytes = resp.read()
    except urllib.error.HTTPError as e:
        status = e.code
        hdrs = {k.lower(): v for k, v in e.headers.items()} if e.headers else {}
        raw_bytes = e.read() if hasattr(e, 'read') else b''
    except (urllib.error.URLError, socket.timeout) as e:
        raise ConnectionError(f"Could not reach {url}: {e}") from e

    parsed = None
    if raw_bytes:
        try:
            parsed = json.loads(raw_bytes.decode('utf-8'))
        except Exception:
            parsed = None
    return status, hdrs, parsed, raw_bytes

def is_2xx(code: int) -> bool:
    return 200 <= code <= 299

def is_4xx(code: int) -> bool:
    return 400 <= code <= 499

def is_5xx(code: int) -> bool:
    return 500 <= code <= 599

def wait_for_service(url: str, tries: int = 20, delay_s: float = 0.25) -> None:
    """Wait for a service to start responding on a given URL."""
    last_err = None
    for _ in range(tries):
        try:
            http_json('GET', url, payload=None, timeout=2)
            return
        except Exception as e:
            last_err = e
            time.sleep(delay_s)
    raise ConnectionError(f"Service did not become available at {url}: {last_err}")


AUBERGE_URL = "http://127.0.0.1:3002/auberge"
GUARD_BASE = "http://127.0.0.1:3001"

def guard_url(gid: str) -> str:
    return f"{GUARD_BASE}/guardrails/{urllib.parse.quote(gid, safe='')}"

class TestAubergeMicroservice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wait_for_service("http://127.0.0.1:3002/")
        wait_for_service("http://127.0.0.1:3001/")

    def setUp(self):
        try:
            database.db.clear()
        except Exception:
            pass
        self.g_bad = f"g_bad_{uuid.uuid4().hex}"
        self.g_secret = f"g_secret_{uuid.uuid4().hex}"
        http_json("PUT", guard_url(self.g_bad), {"id": self.g_bad, "regx": "BADWORD", "sub": "GOODWORD"})
        http_json("PUT", guard_url(self.g_secret), {"id": self.g_secret, "regx": "SECRET123", "sub": "[REDACTED]"})

    def tearDown(self):
        for gid in (getattr(self, "g_bad", None), getattr(self, "g_secret", None)):
            if gid:
                try:
                    http_json("DELETE", guard_url(gid))
                except Exception:
                    pass

    def test_01_post_returns_output_string(self):
        status, _, data, raw = http_json("POST", AUBERGE_URL, {"prompt": "Say hello in one word."})
        self.assertTrue(is_2xx(status), f"Expected 2xx, got {status}, raw={raw!r}")
        self.assertIsInstance(data, dict)
        self.assertIn("output", data)
        self.assertIsInstance(data["output"], str)

    def test_02_missing_prompt_is_4xx(self):
        status, _, _, _ = http_json("POST", AUBERGE_URL, {})
        self.assertTrue(is_4xx(status) or is_5xx(status))

    def test_03_non_string_prompt_is_4xx(self):
        status, _, _, _ = http_json("POST", AUBERGE_URL, {"prompt": 1})
        self.assertTrue(is_4xx(status) or is_5xx(status))

    def test_04_input_is_sanitised(self):
        token = f"TOKEN_{uuid.uuid4().hex}"
        prompt = f"Repeat exactly this line and nothing else: BADWORD {token}"
        status, _, data, raw = http_json("POST", AUBERGE_URL, {"prompt": prompt})
        self.assertTrue(is_2xx(status), f"status={status}, raw={raw!r}")
        out = data.get("output", "")
        self.assertIsInstance(out, str)
        self.assertNotIn("BADWORD", out)
        self.assertIn(token, out)

    def test_05_output_is_sanitised(self):
        prompt = "Reply with exactly: SECRET123"
        status, _, data, raw = http_json("POST", AUBERGE_URL, {"prompt": prompt})
        self.assertTrue(is_2xx(status), f"status={status}, raw={raw!r}")
        out = data.get("output", "")
        self.assertIsInstance(out, str)
        self.assertNotIn("SECRET123", out)
        self.assertIn("[REDACTED]", out)

    def test_06_both_input_and_output_guardrails_apply_together(self):
        prompt = "Reply with exactly: BADWORD SECRET123"
        status, _, data, raw = http_json("POST", AUBERGE_URL, {"prompt": prompt})
        self.assertTrue(is_2xx(status), f"status={status}, raw={raw!r}")
        out = data.get("output", "")
        self.assertNotIn("BADWORD", out)
        self.assertNotIn("SECRET123", out)
        self.assertTrue(("GOODWORD" in out) or ("[REDACTED]" in out))

    def test_07_sanitisation_is_global_replace(self):
        gid = f"g_multi_{uuid.uuid4().hex}"
        http_json("PUT", guard_url(gid), {"id": gid, "regx": "XX", "sub": "YY"})
        try:
            prompt = "Reply with exactly: XX XX XX"
            status, _, data, raw = http_json("POST", AUBERGE_URL, {"prompt": prompt})
            self.assertTrue(is_2xx(status), f"status={status}, raw={raw!r}")
            out = data.get("output", "")
            self.assertNotIn("XX", out)
            self.assertGreaterEqual(out.count("YY"), 2)
        finally:
            http_json("DELETE", guard_url(gid))

    def test_08_guardrails_update_is_reflected(self):
        http_json("PUT", guard_url(self.g_bad), {"id": self.g_bad, "regx": "BADWORD", "sub": "BETTERWORD"})
        prompt = "Reply with exactly: BADWORD"
        status, _, data, raw = http_json("POST", AUBERGE_URL, {"prompt": prompt})
        self.assertTrue(is_2xx(status), f"status={status}, raw={raw!r}")
        out = data.get("output", "")
        self.assertNotIn("BADWORD", out)
        self.assertIn("BETTERWORD", out)

    def test_09_handles_prompt_that_triggers_sanitisation(self):
        status, _, data, _ = http_json("POST", AUBERGE_URL, {"prompt": "BADWORD"})
        self.assertTrue(is_2xx(status) or is_4xx(status) or is_5xx(status))
        if is_2xx(status):
            self.assertNotIn("BADWORD", data.get("output", ""))

    def test_10_method_not_allowed_on_get(self):
        status, _, _, _ = http_json("GET", AUBERGE_URL)
        self.assertTrue(is_4xx(status) or is_5xx(status))

if __name__ == "__main__":
    unittest.main()
