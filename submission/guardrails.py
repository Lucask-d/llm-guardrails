from flask import Flask, request, jsonify
import os
import json
import re
import urllib.request
import urllib.error

app = Flask(__name__)

REGION = "europe-west1"

def firebase_base_url() -> str:
    FIREBASE_DB = os.environ.get("FIREBASE_DB")  # read it at runtime
    if not FIREBASE_DB:
        raise RuntimeError("FIREBASE_DB not set")
    return f"https://{FIREBASE_DB}-default-rtdb.{REGION}.firebasedatabase.app"

def firebase_request(method: str, path: str, body_obj=None):
    url = firebase_base_url() + path

    data = None
    headers = {"Content-Type": "application/json"}

    if body_obj is not None:
        data = json.dumps(body_obj).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else ""
        try:
            payload = json.loads(raw) if raw else None
        except Exception:
            payload = raw
        return e.code, payload
    except Exception as e:
        return 0, str(e)

def validate_guardrail_json(data: dict, url_id: str):
    if data is None:
        return False, "Request body must be JSON"

    for k in ("id", "regx", "sub"):
        if k not in data:
            return False, f"Missing '{k}'"
        if not isinstance(data[k], str):
            return False, f"'{k}' must be a string"
        if k in ("id", "regx") and not data[k].strip():
            return False, f"'{k}' must be a non-empty string"

    if data["id"] != url_id:
        return False, "JSON 'id' must match the URL id"

    try:
        re.compile(data["regx"])
    except re.error as ex:
        return False, f"Invalid regular expression: {ex}"

    return True, None


@app.route("/guardrails/<gid>", methods=["PUT"])
def put_guardrail(gid):
    if not os.environ.get("FIREBASE_DB"):
        return jsonify({"error": "FIREBASE_DB not set"}), 500

    data = request.get_json(silent=True)
    ok, err = validate_guardrail_json(data, gid)
    if not ok:
        return jsonify({"error": err}), 400

    # Check if it already exists
    status, existing = firebase_request("GET", f"/guardrails/{gid}.json")
    if status == 0:
        return jsonify({"error": "Failed to reach Firebase", "details": existing}), 500
    if status < 200 or status >= 300:
        return jsonify({"error": "Firebase error", "status": status, "body": existing}), 500

    created = (existing is None)

    # Now write it
    status, payload = firebase_request("PUT", f"/guardrails/{gid}.json", body_obj=data)
    if status == 0:
        return jsonify({"error": "Failed to reach Firebase", "details": payload}), 500
    if status < 200 or status >= 300:
        return jsonify({"error": "Firebase error", "status": status, "body": payload}), 500

    return jsonify(payload), (201 if created else 200)


@app.route("/guardrails/<gid>", methods=["GET"])
def get_guardrail(gid):
    if not os.environ.get("FIREBASE_DB"):
        return jsonify({"error": "FIREBASE_DB not set"}), 500

    status, payload = firebase_request("GET", f"/guardrails/{gid}.json")

    if status == 0:
        return jsonify({"error": "Failed to reach Firebase", "details": payload}), 500
    if status < 200 or status >= 300:
        return jsonify({"error": "Firebase error", "status": status, "body": payload}), 500

    if payload is None:
        return jsonify({"error": "Guardrail not found"}), 404

    return jsonify(payload), 200


@app.route("/guardrails/<gid>", methods=["DELETE"])
def delete_guardrail(gid):
    if not os.environ.get("FIREBASE_DB"):
        return jsonify({"error": "FIREBASE_DB not set"}), 500

    status, existing = firebase_request("GET", f"/guardrails/{gid}.json")
    if status == 0:
        return jsonify({"error": "Failed to reach Firebase", "details": existing}), 500
    if status < 200 or status >= 300:
        return jsonify({"error": "Firebase error", "status": status, "body": existing}), 500
    if existing is None:
        return jsonify({"error": "Guardrail not found"}), 404

    status, payload = firebase_request("DELETE", f"/guardrails/{gid}.json")
    if status == 0:
        return jsonify({"error": "Failed to reach Firebase", "details": payload}), 500
    if status < 200 or status >= 300:
        return jsonify({"error": "Firebase error", "status": status, "body": payload}), 500

    return jsonify({"deleted": gid}), 200


@app.route("/guardrails", methods=["GET"])
def list_guardrails():
    if not os.environ.get("FIREBASE_DB"):
        return jsonify({"error": "FIREBASE_DB not set"}), 500

    status, payload = firebase_request("GET", "/guardrails.json")

    if status == 0:
        return jsonify({"error": "Failed to reach Firebase", "details": payload}), 500
    if status < 200 or status >= 300:
        return jsonify({"error": "Firebase error", "status": status, "body": payload}), 500

    if payload is None:
        return jsonify([]), 200

    if isinstance(payload, dict):
        return jsonify(sorted(payload.keys())), 200

    return jsonify({"error": "Unexpected data format in Firebase"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)
