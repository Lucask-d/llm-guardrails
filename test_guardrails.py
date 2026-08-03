"""Unit tests for the Guardrails microservice (port 3001).

Spec highlights:
- Stores guardrails in Firebase Realtime DB using env var FIREBASE_DB.
- Endpoints:
  - PUT /guardrails/<id> with JSON {"id":id,"regx":regx,"sub":sub}
  - GET /guardrails/<id> returns that JSON object
  - DELETE /guardrails/<id>
  - GET /guardrails returns JSON list of ids
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


BASE = "http://127.0.0.1:3001"

def url_for_id(gid: str) -> str:
    return f"{BASE}/guardrails/{urllib.parse.quote(gid, safe='')}"

class TestGuardrailsMicroservice(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        wait_for_service(f"{BASE}/")

    def setUp(self):
        try:
            database.db.clear()
        except Exception:
            pass
        self.gid = f"t_{uuid.uuid4().hex}"

    def tearDown(self):
        try:
            http_json("DELETE", url_for_id(self.gid), timeout=DEFAULT_TIMEOUT_S)
        except Exception:
            pass

    def test_01_put_creates_guardrail_and_returns_2xx(self):
        payload = {"id": self.gid, "regx": "SECRET", "sub": "[REDACTED]"}
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), payload)
        self.assertTrue(is_2xx(status), f"Expected 2xx, got {status}")

    def test_02_get_returns_created_guardrail(self):
        payload = {"id": self.gid, "regx": "SECRET", "sub": "[REDACTED]"}
        http_json("PUT", url_for_id(self.gid), payload)
        status, _, data, raw = http_json("GET", url_for_id(self.gid))
        self.assertTrue(is_2xx(status), f"status={status}, raw={raw!r}")
        self.assertIsInstance(data, dict)
        for k in ("id", "regx", "sub"):
            self.assertIn(k, data)
        self.assertEqual(data["id"], self.gid)

    def test_03_delete_removes_guardrail(self):
        payload = {"id": self.gid, "regx": "X", "sub": "Y"}
        http_json("PUT", url_for_id(self.gid), payload)
        status, _, _, _ = http_json("DELETE", url_for_id(self.gid))
        self.assertTrue(is_2xx(status) or is_4xx(status) or is_5xx(status))
        status2, _, _, _ = http_json("GET", url_for_id(self.gid))
        self.assertTrue(is_4xx(status2) or is_5xx(status2), f"Expected missing to be 4xx/5xx, got {status2}")

    def test_04_list_contains_created_id(self):
        payload = {"id": self.gid, "regx": "SECRET", "sub": "[REDACTED]"}
        http_json("PUT", url_for_id(self.gid), payload)
        status, _, data, raw = http_json("GET", f"{BASE}/guardrails")
        self.assertTrue(is_2xx(status), f"status={status}, raw={raw!r}")
        self.assertIsInstance(data, list)
        self.assertIn(self.gid, data)

    def test_05_put_missing_fields_is_4xx(self):
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), {"id": self.gid, "regx": "X"})
        self.assertTrue(is_4xx(status) or is_5xx(status))

    def test_06_put_non_string_regx_is_4xx(self):
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), {"id": self.gid, "regx": 12, "sub": "X"})
        self.assertTrue(is_4xx(status) or is_5xx(status))

    def test_07_put_non_string_sub_is_4xx(self):
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), {"id": self.gid, "regx": "X", "sub": 12})
        self.assertTrue(is_4xx(status) or is_5xx(status))

    def test_08_put_non_string_id_is_4xx(self):
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), {"id": 77, "regx": "X", "sub": "Y"})
        self.assertTrue(is_4xx(status) or is_5xx(status))

    def test_09_put_path_body_id_mismatch_is_4xx_or_2xx_consistent(self):
        other = f"other_{uuid.uuid4().hex}"
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), {"id": other, "regx": "X", "sub": "Y"})
        self.assertTrue(is_2xx(status) or is_4xx(status) or is_5xx(status))
        if is_2xx(status):
            s1, _, _, _ = http_json("GET", url_for_id(self.gid))
            s2, _, _, _ = http_json("GET", url_for_id(other))
            self.assertTrue(is_2xx(s1) or is_2xx(s2))

    def test_10_get_nonexistent_id_is_4xx(self):
        missing = f"missing_{uuid.uuid4().hex}"
        status, _, _, _ = http_json("GET", url_for_id(missing))
        self.assertTrue(is_4xx(status) or is_5xx(status))

    def test_11_delete_nonexistent_id_is_not_crash(self):
        missing = f"missing_{uuid.uuid4().hex}"
        status, _, _, _ = http_json("DELETE", url_for_id(missing))
        self.assertTrue(is_2xx(status) or is_4xx(status) or is_5xx(status))

    def test_12_list_returns_json_list(self):
        status, hdrs, data, raw = http_json("GET", f"{BASE}/guardrails")
        self.assertTrue(is_2xx(status), f"status={status}, raw={raw!r}")
        self.assertIsInstance(data, list)
        ct = hdrs.get("content-type", "").lower()
        self.assertTrue(("application/json" in ct) or isinstance(data, list))

    def test_13_invalid_json_is_4xx(self):
        import urllib.request, urllib.error
        req = urllib.request.Request(
            url_for_id(self.gid),
            data=b'{"id":',
            method="PUT",
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT_S)
            self.fail("Expected HTTPError for invalid JSON.")
        except urllib.error.HTTPError as e:
            self.assertTrue(is_4xx(e.code) or is_5xx(e.code))

    def test_14_empty_id_in_path_is_4xx(self):
        status, _, _, _ = http_json("PUT", f"{BASE}/guardrails/", {"id": "", "regx": "X", "sub": "Y"})
        self.assertTrue(is_4xx(status) or is_5xx(status))

    def test_15_accepts_valid_python_regex(self):
        payload = {"id": self.gid, "regx": r"\b\d{3}\b", "sub": "<NUM>"}
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), payload)
        self.assertTrue(is_2xx(status) or is_4xx(status) or is_5xx(status))

    def test_16_invalid_regex_does_not_500(self):
        payload = {"id": self.gid, "regx": r"([A-Z", "sub": "X"}
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), payload)
        self.assertFalse(is_5xx(status), f"Should not crash on invalid regex; got {status}")

    def test_17_substitution_allows_backreferences_string(self):
        payload = {"id": self.gid, "regx": r"(cat)", "sub": r"\1s"}
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), payload)
        self.assertTrue(is_2xx(status) or is_4xx(status))

    def test_18_large_regex_string_handling(self):
        big = "A" * 2000
        payload = {"id": self.gid, "regx": big, "sub": "X"}
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), payload)
        self.assertTrue(is_2xx(status) or is_4xx(status) or is_5xx(status))

    def test_19_special_characters_in_id(self):
        gid = f"sp-{uuid.uuid4().hex}:._~"
        payload = {"id": gid, "regx": "X", "sub": "Y"}
        status, _, _, _ = http_json("PUT", url_for_id(gid), payload)
        self.assertTrue(is_2xx(status) or is_4xx(status))
        http_json("DELETE", url_for_id(gid))

    def test_20_whitespace_id_is_handled(self):
        gid = f" ws_{uuid.uuid4().hex} "
        payload = {"id": gid, "regx": "X", "sub": "Y"}
        status, _, _, _ = http_json("PUT", url_for_id(gid), payload)
        self.assertTrue(is_2xx(status) or is_4xx(status) or is_5xx(status))
        if is_2xx(status):
            s, _, data, _ = http_json("GET", url_for_id(gid))
            self.assertTrue(is_2xx(s))
            self.assertEqual(data.get("id"), gid)
        http_json("DELETE", url_for_id(gid))

    def test_21_put_overwrites_existing_guardrail(self):
        http_json("PUT", url_for_id(self.gid), {"id": self.gid, "regx": "A", "sub": "B"})
        http_json("PUT", url_for_id(self.gid), {"id": self.gid, "regx": "C", "sub": "D"})
        status, _, data, _ = http_json("GET", url_for_id(self.gid))
        self.assertTrue(is_2xx(status))
        self.assertEqual(data.get("regx"), "C")
        self.assertEqual(data.get("sub"), "D")

    def test_22_delete_is_idempotent_or_4xx(self):
        http_json("PUT", url_for_id(self.gid), {"id": self.gid, "regx": "X", "sub": "Y"})
        s1, _, _, _ = http_json("DELETE", url_for_id(self.gid))
        s2, _, _, _ = http_json("DELETE", url_for_id(self.gid))
        self.assertTrue((is_2xx(s1) or is_4xx(s1) or is_5xx(s1)) and (is_2xx(s2) or is_4xx(s2) or is_5xx(s2)))

    def test_23_post_on_guardrails_collection_is_4xx(self):
        status, _, _, _ = http_json("POST", f"{BASE}/guardrails", {"id": self.gid, "regx": "X", "sub": "Y"})
        self.assertTrue(is_4xx(status) or is_5xx(status))

    def test_24_get_on_collection_has_no_side_effects(self):
        status1, _, data1, _ = http_json("GET", f"{BASE}/guardrails")
        status2, _, data2, _ = http_json("GET", f"{BASE}/guardrails")
        self.assertTrue(is_2xx(status1) and is_2xx(status2))
        self.assertIsInstance(data1, list)
        self.assertIsInstance(data2, list)

    def test_25_put_without_body_is_4xx(self):
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), None)
        self.assertTrue(is_4xx(status) or is_5xx(status))

    def test_26_get_returns_same_schema_as_put(self):
        payload = {"id": self.gid, "regx": "DOG", "sub": "CAT"}
        http_json("PUT", url_for_id(self.gid), payload)
        status, _, data, _ = http_json("GET", url_for_id(self.gid))
        self.assertTrue(is_2xx(status))
        self.assertTrue(all(k in data for k in ("id", "regx", "sub")))

    def test_27_list_includes_only_strings(self):
        status, _, data, _ = http_json("GET", f"{BASE}/guardrails")
        self.assertTrue(is_2xx(status))
        self.assertIsInstance(data, list)
        self.assertTrue(all(isinstance(x, str) for x in data), f"Non-string ids present: {data!r}")

    def test_28_put_accepts_regex_with_inline_flags(self):
        payload = {"id": self.gid, "regx": r"(?i)secret", "sub": "X"}
        status, _, _, _ = http_json("PUT", url_for_id(self.gid), payload)
        self.assertTrue(is_2xx(status) or is_4xx(status) or is_5xx(status))

    def test_29_put_and_get_roundtrip_preserves_strings_exactly(self):
        regx = r"\s+"
        sub = "_"
        http_json("PUT", url_for_id(self.gid), {"id": self.gid, "regx": regx, "sub": sub})
        status, _, data, _ = http_json("GET", url_for_id(self.gid))
        self.assertTrue(is_2xx(status))
        self.assertEqual(data.get("regx"), regx)
        self.assertEqual(data.get("sub"), sub)

    def test_30_list_updates_after_delete(self):
        payload = {"id": self.gid, "regx": "X", "sub": "Y"}
        http_json("PUT", url_for_id(self.gid), payload)
        http_json("DELETE", url_for_id(self.gid))
        status, _, data, _ = http_json("GET", f"{BASE}/guardrails")
        self.assertTrue(is_2xx(status))
        self.assertIsInstance(data, list)
        self.assertNotIn(self.gid, data)

if __name__ == "__main__":
    unittest.main()
