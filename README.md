# ECM3408: LLM Guardrails

A Python microservices project that applies configurable regular-expression guardrails to LLM prompts and responses. Guardrails are stored in Firebase Realtime Database, and text generation uses the Mistral API.

## How it works

The project runs three Flask services:

| Service | File | Port | Purpose |
| --- | --- | --- | --- |
| LLM | `llm.py` | 3000 | Sends prompts to Mistral and returns generated text. |
| Guardrails | `guardrails.py` | 3001 | Creates, retrieves, lists, and deletes guardrails in Firebase. |
| Auberge | `auberge.py` | 3002 | Applies guardrails before and after calling the LLM service. |

For each request to Auberge:

1. Fetch the guardrail IDs and their definitions from the Guardrails service.
2. Apply each regex substitution to the prompt.
3. Send the resulting prompt to the LLM service.
4. Apply the same substitutions to the generated response.
5. Return the filtered text as `{"output": "..."}`.

Guardrails run sequentially in sorted ID order. Each substitution operates on the result of the previous one. With no guardrails stored, text passes through unchanged by the filtering step.

## Setup

You need Python 3, a Mistral API key, and a Firebase Realtime Database in `europe-west1`. The code uses the model identifier `mistral-small-latest`.

Clone the repository:

```bash
git clone https://github.com/Lucask-d/llm-guardrails.git
cd llm-guardrails
```

If you already have a local copy, use its existing directory instead. Its folder name does not need to match the GitHub repository name.

From the project directory, create a virtual environment and install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install Flask requests
```

Set these environment variables in each terminal used to run a service or the tests:

```bash
export MISTRAL_API_KEY='your-mistral-api-key'
export FIREBASE_DB='your-firebase-project-id'
```

`FIREBASE_DB` is the prefix used to construct this database URL:

```text
https://<FIREBASE_DB>-default-rtdb.europe-west1.firebasedatabase.app
```

Use a value such as `my-project`, rather than the full URL. Firebase access rules must permit the operations used by the application; the current code sends no Firebase authentication credentials. Use a dedicated development database.

The services read configuration from the process environment. The `.env` file is not loaded automatically.

## Run locally

Open three terminals, activate the virtual environment, and set the required environment variables in each. Run one service per terminal:

```bash
# Terminal 1
python llm.py
```

```bash
# Terminal 2
python guardrails.py
```

```bash
# Terminal 3
python auberge.py
```

Auberge connects to `http://127.0.0.1:3000` and `http://127.0.0.1:3001` by default. To change its downstream service addresses, set `LLM_URL` and `GUARDRAILS_URL` before starting Auberge. These values are base URLs without endpoint paths.

## Example

Create a guardrail that replaces `SECRET` with `[REDACTED]`:

```bash
curl -X PUT http://127.0.0.1:3001/guardrails/redact-secret \
  -H 'Content-Type: application/json' \
  -d '{"id":"redact-secret","regx":"SECRET","sub":"[REDACTED]"}'
```

Send a prompt through Auberge:

```bash
curl -X POST http://127.0.0.1:3002/auberge \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Repeat this word: SECRET"}'
```

Auberge replaces `SECRET` in the prompt before sending it to Mistral and filters the generated text using the same rule. The response has the form `{"output":"..."}`; the generated wording may vary.

List stored guardrail IDs:

```bash
curl http://127.0.0.1:3001/guardrails
```

## API

| Method | Endpoint | Request body | Successful response |
| --- | --- | --- | --- |
| POST | `:3000/llm` | `{"prompt":"..."}` | `200`, `{"output":"..."}` |
| PUT | `:3001/guardrails/<id>` | `{"id":"<id>","regx":"...","sub":"..."}` | `201` when created or `200` when updated; returns the stored object |
| GET | `:3001/guardrails/<id>` | None | `200`, stored guardrail object |
| GET | `:3001/guardrails` | None | `200`, sorted JSON array of IDs |
| DELETE | `:3001/guardrails/<id>` | None | `200`, `{"deleted":"<id>"}` |
| POST | `:3002/auberge` | `{"prompt":"..."}` | `200`, `{"output":"..."}` |

Prompts must be non-empty strings. A guardrail requires string fields `id`, `regx`, and `sub`; `id` and `regx` must be non-empty, and the body ID must match the URL ID. The regex must compile using Python's `re` module. An empty substitution string is allowed and removes matched text.

Validation errors return `400`. Retrieving or deleting a missing guardrail returns `404`. Missing required configuration and downstream service failures return `500`.

Calling `/llm` directly sends the prompt to Mistral without applying guardrails. Use `/auberge` for filtering.

## Testing

The test suites make HTTP requests to running services. Start all three services first and configure the test terminal with `FIREBASE_DB`.

**Tests can delete all data under `/guardrails` in the configured Firebase database.** Run them against a dedicated test database. Tests that generate text also make live Mistral requests and may incur API charges.

Run the service-focused suites:

```bash
python -m unittest -v test_llm test_guardrails test_auberge
```

Additional suites are available in `test5.py`, `tests10.py`, `test25.py`, and `test50.py`. For example:

```bash
python -m unittest -v test50
```

## Project files

| Path | Description |
| --- | --- |
| `llm.py` | Mistral API wrapper. |
| `guardrails.py` | Guardrail validation and Firebase CRUD operations. |
| `auberge.py` | Prompt and response filtering workflow. |
| `database.py` | Database cleanup helper used by tests. |
| `test*.py` | HTTP-based service and integration tests. |
| `submission/` | Submission copies of the service modules and database helper. |

## Limitations

Filtering uses Python regex substitutions and only covers patterns explicitly configured in the database. It does not provide semantic moderation or guarantee protection against prompt injection. The services expose no application authentication and use Flask's development server when launched directly.
