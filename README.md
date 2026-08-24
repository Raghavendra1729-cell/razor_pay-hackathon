# PaisaMatch AI

**Verifiable settlement reconciliation for merchant finance teams.**

PaisaMatch reconciles merchant orders, Razorpay-style settlements and bank
deposits. The engine uses deterministic rules for all monetary decisions and
uses a Hugging Face hosted LLM only to resolve a tightly constrained set of
ambiguous references. A proposed match must still pass independent amount, fee,
tax and bank-deposit checks.

> Built for Razorpay AI Buildathon — Track 4: AI Finance Controller.

## Why it exists

A merchant may know an order was paid, but still need to manually establish
which settlement and bank entry correspond to it. This becomes difficult when
references are messy, fees alter the deposited amount or records are delayed.
PaisaMatch closes one finance-operations loop and returns an exception list
instead of guessing.

## What the demo proves

The included synthetic batch has **72 merchant orders**:

| Outcome | Records | Behaviour |
| --- | ---: | --- |
| Exact match | 48 | Reference, settlement and bank evidence agree. |
| Assisted match | 12 | A constrained candidate is resolved, then independently verified. |
| Needs review | 12 | Missing, duplicate or financially inconsistent evidence is not force-matched. |

The deterministic test run reports **83.33% match rate**, **100% precision**,
**100% recall** against hidden demo ground truth, and **₹0 financial variance**
for accepted matches. These are reproducible synthetic-demo results, not claims
about live merchant performance.

## Architecture

```text
React operator dashboard
          |
          v
FastAPI reconciliation service
  |-- normalise amounts and dates
  |-- exact matcher
  |-- constrained candidate generator
  |-- Hugging Face JSON-schema resolver (ambiguous records only)
  '-- financial verifier --> matched result or exception + audit trail
```

### Safety boundaries

- Money arithmetic, fees, tax and bank matching are verified in Python.
- The model can choose only a supplied candidate ID or abstain.
- Invalid/malformed/unavailable model output becomes `needs_review`.
- The demo uses synthetic labels only; no customer PII or payment credentials
  are sent to the model.
- The repository contains no secrets. Configure `HF_TOKEN` locally or as a
  deployment secret.

## Run locally

Requirements: Python 3.11+ and Node 20+.

```bash
git clone https://github.com/Raghavendra1729-cell/razor_pay-hackathon.git
cd razor_pay-hackathon

python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt

cd frontend
npm install
cd ..
```

Start the API in one terminal:

```bash
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --port 8000
```

Start React in another terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`, select **Run 72-record demo**, then inspect a
record or filter the exception queue.

## Hugging Face setup

The project works without a token using a labelled deterministic fallback for
local development. For the final demo, use a Hugging Face Inference Providers
token and a model/provider combination that supports strict JSON schema output.

```bash
export HF_TOKEN=hf_your_token
export HF_MODEL=Qwen/Qwen3-32B
```

The UI reports the resolver mode. Only call a demo AI-assisted when it shows
`Hugging Face structured output`.

## Test and build

```bash
PYTHONPATH=backend .venv/bin/pytest -q backend/tests
PYTHONPATH=backend .venv/bin/ruff format --check backend
PYTHONPATH=backend .venv/bin/ruff check backend
cd frontend && npm run build
```

GitHub Actions runs the same backend checks and frontend production build for
every push to `main` and every pull request.

## API

- `GET /api/health` — service health check
- `POST /api/reconcile/demo` — run the labelled 72-record synthetic batch

Interactive FastAPI docs are available at `http://localhost:8000/docs`.

## Deploy as one container

The production image builds React and serves it from FastAPI, so the browser
and API use the same origin. It is suitable for a Docker-based host or a
Hugging Face Docker Space.

```bash
docker build -t paisamatch .
docker run --rm -p 7860:7860 -e HF_TOKEN=hf_your_token paisamatch
```

Open `http://localhost:7860`. Add `HF_TOKEN` as a platform secret; never place
it in the repository or browser environment.

## Pitch video

Use the ready-to-record [five-minute script](docs/VIDEO_SCRIPT.md). It covers
the product flow, AI boundary, a handled failure, architecture and measured
evaluation without overclaiming.
