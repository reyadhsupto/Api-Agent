# Technical Documentation - Api-Agent

## 1. Tech Stack
| Layer | Technology | Reason |
|-------|-----------|--------|
| Backend Language | Python 3.11+ | Project convention, rich AI/HTTP ecosystem |
| Backend Framework | FastAPI | Async support, automatic OpenAPI docs, easy routing |
| HTTP Client | python requests | User-specified standard for outbound API calls |
| Frontend | Streamlit | Pure Python, single-process deployment, no Node.js |
| LLM Providers | Groq, OpenRouter, Cohere, HuggingFace | Free tiers, multiple for fallback |
| cURL Parsing | shlex + custom logic | No heavy dependency, easy to understand |
| Memory Store | Python module-level dict | No database for MVP |
| Testing | pytest | Unit tests |

## 2. Architecture
```
Streamlit UI (port 8501) <--> FastAPI Backend (port 8000) <--> Target API
                                               |
                                               v
                                        LLM Providers (fallback chain)
```

## 3. Module Responsibilities

### app/main.py
- FastAPI application instance
- CORS middleware
- All API routes (health, curl parse, test cases generate, execute)
- In-memory storage (module-level variables)

### app/parser.py
- parse_curl(curl_string) -> dict with method, url, headers, body

### app/generator.py
- generate_test_cases(parsed_curl, business_requirements) -> list of dicts
- LLM fallback logic inside this module

### app/executor.py
- execute_test_case(test_case, base_url) -> dict with request/response/latency/assertion
- Uses python requests

### app/schemas.py
- Minimal Pydantic models for request/response validation

### frontend/app.py
- Streamlit app with 2 tabs
- Tab 1: Endpoints - Parse cURL, add/edit multiple endpoints with include/exclude checkbox, method, url, headers, query params, path params, body
- Tab 2: Test Cases - generate and execute merged with per-test-case cards
- Each test case card: visual separation, assertion editor (enable/disable checkbox, expected status, body assertion type: Body Contains or Exact Field JSONPath, expected value input), execute button, verbose request/response results
- Calls FastAPI endpoints via python requests
- Logs all API requests/responses to browser devtools console via st.iframe console.log
- Endpoints stored as list in session state (future-ready for flow/sequence mapping)

## 4. API Endpoints

### GET /health
Returns {"status": "ok"}.

### POST /api/v1/curl/parse
Body: {"curl": "..."}
Returns parsed request components (method, url, headers, body).
Frontend allows user to edit these components before generating test cases.

### POST /api/v1/test-cases/generate
Body: {"parsed_curl": {...}, "business_requirements": "..."}
Returns list of test cases. Accepts the (optionally edited) parsed_curl from the frontend.
Prompt instructs LLM to generate as many test cases as possible (positive, negative, edge, race).

### POST /api/v1/test-cases/execute
Body: {"test_case_id": "...", "base_url": "..."}
Returns execution result with assertion status.

## 5. Multi-Endpoint Support
Endpoints are stored as a list in Streamlit session state. Each endpoint has a unique ID and can be independently configured and selected for test case generation. This lays the groundwork for future flow/sequence mapping between endpoints.

## 7. LLM Fallback Strategy
Provider order (configurable via env):
1. Groq (free tier) — dynamically selects the model with the largest context window from `/v1/models`
2. OpenRouter (free tier) — uses model from `OPENROUTER_MODEL` env var (default: `nvidia/nemotron-3-ultra-550b-a55b:free`)
3. Cohere (free tier)
4. HuggingFace (free tier)

Simple function tries providers in order. On 429 or error, moves to next. If all fail, returns error.

### Groq Dynamic Model Selection
Before calling the chat completion API, the system calls `GET /v1/models` to list available models, then selects the one with the largest `context_window` (currently `llama-3.1-8b-instant` with 131072 tokens).

### OpenRouter Configuration
Set `OPENROUTER_API_KEY` in `.env` and optionally `OPENROUTER_MODEL` to choose a specific model. OpenRouter provides access to many free models from various providers.

## 8. Deployment
- Run FastAPI on port 8000: uvicorn app.main:app --reload
- Run Streamlit on port 8501: streamlit run frontend/app.py
- Single user, local only, no auth
- Frontend API timeout: 300 seconds (5 minutes) for LLM generation
- Clean caches: make clean-cache (keeps venv), make clean (removes venv + caches)
