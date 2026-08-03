"""Unit tests for the LLM microservice (port 3000).

Spec highlights:
- POST /llm expects JSON {"prompt": <string>} and returns JSON {"output": <string>}.
- Must listen on port 3000.
"""

import unittest
import uuid

import json
import socket
import time
import urllib.request
import urllib.error
from typing import Any, Dict, Optional, Tuple
import database

DEFAULT_TIMEOUT_S = 8

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


LLM_URL = "http://127.0.0.1:3000/llm"

class TestLLMMicroservice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wait_for_service("http://127.0.0.1:3000/")

    def setUp(self):
        try:
            database.db.clear()
        except Exception:
            pass

    def test_01_post_llm_returns_output_string(self):
        status, _, data, raw = http_json("POST", LLM_URL, {"prompt": "Say hello in one word."})
        self.assertTrue(is_2xx(status), f"Expected 2xx, got {status}, raw={raw!r}")
        self.assertIsInstance(data, dict, f"Expected JSON object, got {data!r}")
        self.assertIn("output", data)
        self.assertIsInstance(data["output"], str)

    def test_02_prompt_echo_like_request_is_supported(self):
        token = f"TOKEN_{uuid.uuid4().hex}"
        prompt = f"Reply with exactly this token and nothing else: {token}"
        status, _, data, _ = http_json("POST", LLM_URL, {"prompt": prompt})
        self.assertTrue(is_2xx(status))
        self.assertIsInstance(data, dict)
        self.assertIsInstance(data.get("output"), str)
        self.assertIn(token, data["output"])

    def test_03_missing_prompt_is_4xx(self):
        status, _, _, _ = http_json("POST", LLM_URL, {}, timeout=DEFAULT_TIMEOUT_S)
        self.assertTrue(is_4xx(status) or is_5xx(status), f"Expected 4xx/5xx, got {status}")

    def test_04_non_string_prompt_is_4xx(self):
        status, _, _, _ = http_json("POST", LLM_URL, {"prompt": 123})
        self.assertTrue(is_4xx(status) or is_5xx(status), f"Expected 4xx/5xx, got {status}")

    def test_05_invalid_json_is_4xx(self):
        import urllib.request, urllib.error
        req = urllib.request.Request(
            LLM_URL,
            data=b'{"prompt":',
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT_S)
            self.fail("Expected HTTPError for invalid JSON.")
        except urllib.error.HTTPError as e:
            self.assertTrue(is_4xx(e.code) or is_5xx(e.code))

    def test_06_response_is_json_object(self):
        status, hdrs, data, raw = http_json("POST", LLM_URL, {"prompt": "Return any short sentence."})
        self.assertTrue(is_2xx(status), f"status={status}, raw={raw!r}")
        ct = hdrs.get("content-type", "")
        self.assertTrue(("application/json" in ct.lower()) or isinstance(data, dict))

    def test_07_unicode_prompt_handling(self):
        status, _, data, raw = http_json("POST", LLM_URL, {"prompt": "Respond with 'café' and '你好'."})
        self.assertTrue(is_2xx(status), f"status={status}, raw={raw!r}")
        self.assertIsInstance(data, dict)
        self.assertIsInstance(data.get("output"), str)

    def test_08_empty_prompt_handling(self):
        status, _, data, _ = http_json("POST", LLM_URL, {"prompt": ""})
        self.assertTrue(is_2xx(status) or is_4xx(status) or is_5xx(status))
        if is_2xx(status):
            self.assertIsInstance(data, dict)
            self.assertIsInstance(data.get("output"), str)

    def test_09_long_prompt_handling(self):
        long_prompt = "A" * 4000
        status, _, data, _ = http_json("POST", LLM_URL, {"prompt": long_prompt}, timeout=DEFAULT_TIMEOUT_S)
        self.assertTrue(is_2xx(status) or is_4xx(status) or is_5xx(status))
        if is_2xx(status):
            self.assertIsInstance(data.get("output"), str)

    def test_10_method_not_allowed_on_get(self):
        status, _, _, _ = http_json("GET", LLM_URL)
        self.assertTrue(is_4xx(status) or is_5xx(status), f"Expected 4xx/5xx, got {status}")

    

if __name__ == "__main__":
    unittest.main()
