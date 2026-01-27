from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODEL = "mistral-small-latest" 

'''
def load_env_file(path=".env"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass

load_env_file()
'''


@app.post("/llm")
def llm():
    data = request.get_json(silent=True)

    if data is None:
        return jsonify({"error": "Request body must be JSON"}), 400

    prompt = data.get("prompt")
    if prompt is None:
        return jsonify({"error": "Missing 'prompt'"}), 400
    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "'prompt' must be a non-empty string"}), 400

    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        return jsonify({"error": "MISTRAL_API_KEY not set"}), 500
   
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(MISTRAL_URL, json=payload, headers=headers, timeout=20)
    except requests.RequestException as e:
        return jsonify({"error": "Failed to reach Mistral", "details": str(e)}), 500

    if r.status_code < 200 or r.status_code >= 300:
        # Bubble up something useful for debugging, but keep it a 500 for your service
        return jsonify({"error": "Mistral API error", "status": r.status_code, "body": r.text}), 500

    try:
        res = r.json()
        output = res["choices"][0]["message"]["content"]
        if not isinstance(output, str):
            raise ValueError("content not a string")
    except Exception as e:
        return jsonify({"error": "Unexpected Mistral response format", "details": str(e)}), 500

    return jsonify({"output": output}), 200



    # placeholder until minstral is added
    return jsonify({"output": "Mistral key detected"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
