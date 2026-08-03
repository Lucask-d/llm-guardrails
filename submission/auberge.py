from flask import Flask, request, jsonify
import os
import re
import requests

app = Flask(__name__)


LLM_BASE_URL = os.environ.get("LLM_URL", "http://127.0.0.1:3000").rstrip("/")
GUARDRAILS_BASE_URL = os.environ.get("GUARDRAILS_URL", "http://127.0.0.1:3001").rstrip("/")

HTTP_TIMEOUT_SECS = 20


class GuardrailFetchError(RuntimeError):
    pass


def fetch_guardrails():
    """Fetch guardrails from Guardrails microservice.

    Returns:
        List[dict]: each dict has keys: id, regx, sub (all strings).
    Raises:
        GuardrailFetchError: on network errors or unexpected responses.
    """
    try:
        r = requests.get(f"{GUARDRAILS_BASE_URL}/guardrails", timeout=HTTP_TIMEOUT_SECS)
    except requests.RequestException as e:
        raise GuardrailFetchError(f"Failed to reach Guardrails: {e}")

    if r.status_code < 200 or r.status_code >= 300:
        raise GuardrailFetchError(f"Guardrails API error: {r.status_code} {r.text}")

    try:
        ids = r.json()
    except Exception as e:
        raise GuardrailFetchError(f"Guardrails list not JSON: {e}")

    if ids is None:
        return []

    if not isinstance(ids, list):
        raise GuardrailFetchError("Guardrails list response must be a JSON list")

    guardrails = []
    for gid in ids:
        if not isinstance(gid, str) or not gid.strip():
            raise GuardrailFetchError("Guardrails list contains a non-string id")

        try:
            gr = requests.get(f"{GUARDRAILS_BASE_URL}/guardrails/{gid}", timeout=HTTP_TIMEOUT_SECS)
        except requests.RequestException as e:
            raise GuardrailFetchError(f"Failed to reach Guardrails for id '{gid}': {e}")

        if gr.status_code < 200 or gr.status_code >= 300:
            # Spec for Auberge doesn't mention 404; treat all downstream errors as 500.
            raise GuardrailFetchError(f"Guardrails API error for id '{gid}': {gr.status_code} {gr.text}")

        try:
            obj = gr.json()
        except Exception as e:
            raise GuardrailFetchError(f"Guardrail '{gid}' not JSON: {e}")

        if not isinstance(obj, dict):
            raise GuardrailFetchError(f"Guardrail '{gid}' must be a JSON object")

        # Validate presence of keys (guardrails.py ensures these on write, but be defensive).
        if "id" not in obj or "regx" not in obj or "sub" not in obj:
            raise GuardrailFetchError(f"Guardrail '{gid}' missing required fields")

        if obj.get("id") != gid:
            # Inconsistency shouldn't happen; fail fast.
            raise GuardrailFetchError(f"Guardrail '{gid}' has mismatched id field")

        if not isinstance(obj["regx"], str) or not isinstance(obj["sub"], str):
            raise GuardrailFetchError(f"Guardrail '{gid}' has invalid field types")

        guardrails.append(obj)

    return guardrails


def apply_guardrails(text: str, guardrails):
    """Apply all guardrails to a string in list order."""
    out = text
    for gr in guardrails:
        regx = gr.get("regx", "")
        sub = gr.get("sub", "")
        try:
            out = re.sub(regx, sub, out)
        except re.error as e:
            # Stored regex should already be validated by Guardrails service.
            raise GuardrailFetchError(f"Invalid regex in guardrail '{gr.get('id', '')}': {e}")
    return out


def call_llm(prompt: str) -> str:
    """Call LLM microservice and return its output string."""
    try:
        r = requests.post(
            f"{LLM_BASE_URL}/llm",
            json={"prompt": prompt},
            timeout=HTTP_TIMEOUT_SECS,
        )
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to reach LLM: {e}")

    if r.status_code < 200 or r.status_code >= 300:
        raise RuntimeError(f"LLM API error: {r.status_code} {r.text}")

    try:
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"LLM response not JSON: {e}")

    if not isinstance(data, dict) or "output" not in data:
        raise RuntimeError("LLM response missing 'output'")

    output = data.get("output")
    if not isinstance(output, str):
        raise RuntimeError("LLM 'output' must be a string")

    return output


@app.route("/auberge", methods=["POST"])
def auberge():
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Request body must be JSON"}), 400

    prompt = data.get("prompt")
    if prompt is None:
        return jsonify({"error": "Missing 'prompt'"}), 400
    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "'prompt' must be a non-empty string"}), 400

    try:
        guardrails = fetch_guardrails()
        clean_prompt = apply_guardrails(prompt, guardrails)
        llm_output = call_llm(clean_prompt)
        clean_output = apply_guardrails(llm_output, guardrails)
    except GuardrailFetchError as e:
        return jsonify({"error": "Guardrails error", "details": str(e)}), 500
    except Exception as e:
        return jsonify({"error": "LLM error", "details": str(e)}), 500

    return jsonify({"output": clean_output}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3002)
