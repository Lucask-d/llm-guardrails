# database.py
import os
import json
import urllib.request

REGION = "europe-west1"

def _base_url() -> str:
    db = os.environ.get("FIREBASE_DB")
    if not db:
        raise RuntimeError("FIREBASE_DB not set (needed to clear Firebase in tests)")
    return f"https://{db}-default-rtdb.{REGION}.firebasedatabase.app"

def _request(method: str, path: str):
    url = _base_url() + path
    req = urllib.request.Request(
        url,
        data=None,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
        return resp.status, (json.loads(raw) if raw else None)

class _DB:
    def clear(self):
        """
        Deletes all guardrails stored under /guardrails.
        This matches how your service stores items at /guardrails/<id>.json
        """
        status, _ = _request("DELETE", "/guardrails.json")
        if status < 200 or status >= 300:
            raise RuntimeError(f"Failed to clear Firebase guardrails: HTTP {status}")

db = _DB()
