# Module 1 — Python AI Setup, FastAPI & Streaming Endpoints

## Architecture Overview

```
Client (curl / browser / frontend)
        │
        ▼
   FastAPI app  (≈ Laravel/Slim router)
        │
        ├── POST /chat         → AsyncOpenAI.chat.completions.create()  → JSON
        └── POST /chat/stream  → AsyncOpenAI (stream=True) → SSE chunks
```

**PHP → Python mental model map**

| PHP concept | Python equivalent |
|---|---|
| `getenv()` / `$_ENV` | `os.getenv()` + `python-dotenv` |
| DTO / Form Request | `pydantic.BaseModel` |
| `ob_flush()` chunked output | `StreamingResponse` + async generator |
| Laravel route closure | FastAPI `@app.post(...)` decorator |
| Guzzle HTTP client | `httpx` / `openai` SDK |
| `try/catch` | `try/except` |

---

## Project Structure

```
c:\Projects\AI\
├── .env                   ← your secrets (copy from .env.example)
├── .env.example           ← template
├── .venv\                 ← isolated Python environment
├── requirements.txt
├── module1_streaming.py   ← this module's code
└── Docs\
    └── module1.md         ← this file
```

---

## Setup Commands

```powershell
# 1. Create a virtual environment (≈ composer install sandbox)
python -m venv .venv

# 2. Activate it (must do this every terminal session)
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and fill in secrets
Copy-Item .env.example .env
# Then edit .env and paste your OPENAI_API_KEY
```

> **Why venv?**
> Same reason you wouldn't install PHP packages globally — it isolates project
> dependencies so different projects can use different library versions without conflict.

---

## Code Walkthrough — module1_streaming.py

### 1. load_dotenv()
Reads your `.env` file and injects values into the process environment.
Equivalent to: `$dotenv = Dotenv\Dotenv::createImmutable(__DIR__); $dotenv->load();`

### 2. AsyncOpenAI
The async version of the OpenAI client. FastAPI is fully async (built on asyncio), so we
always use `await` when calling the API — this lets the server handle other requests while
waiting for the LLM response. Same concept as non-blocking I/O in Node.js.

### 3. ChatRequest (Pydantic BaseModel)
```python
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
```
FastAPI **automatically** parses the JSON body, validates types, and returns a
`422 Unprocessable Entity` if validation fails — all for free. You never write
manual `$request->validate([...])` logic.

### 4. POST /chat — Baseline
Standard request/response. Waits for the full LLM reply and returns it as JSON
including token usage stats (important for cost tracking in Module 6).

### 5. token_stream() — Async Generator
```python
async def token_stream(...) -> AsyncGenerator[str, None]:
    async for chunk in stream:
        yield f"data: {delta}\n\n"
```
A Python **async generator** — a function that can pause and resume, yielding one
token at a time. The `data: ...\n\n` format is the Server-Sent Events (SSE) protocol.

### 6. POST /chat/stream — Streaming
```python
return StreamingResponse(token_stream(request), media_type="text/event-stream")
```
FastAPI wraps the generator in an HTTP response that keeps the connection open and
flushes data as it arrives — like PHP's `ob_flush()` but without the hack.

---

## Running the Server

```powershell
# Activate venv first
.venv\Scripts\Activate.ps1

# Start with auto-reload on file changes
uvicorn module1_streaming:app --reload --port 8000
```

Server: http://127.0.0.1:8000
Interactive docs: http://127.0.0.1:8000/docs  (try it in the browser!)

---

## Testing

### Health check
```powershell
curl http://127.0.0.1:8000/health
```

### Non-streaming
```powershell
curl -X POST http://127.0.0.1:8000/chat `
  -H "Content-Type: application/json" `
  -d '{"message": "What is FastAPI in one sentence?"}'
```

### Streaming (watch tokens arrive one by one)
```powershell
curl -X POST http://127.0.0.1:8000/chat/stream `
  -H "Content-Type: application/json" `
  -d '{"message": "Explain async/await to a PHP developer in 3 bullet points."}'
```

---

## Key LLM Parameters

| Parameter | Effect | Range |
|---|---|---|
| `temperature` | Randomness/creativity (0=deterministic, 2=chaotic) | 0.0–2.0 |
| `max_tokens` | Maximum output length (controls cost) | 1–4096 |
| `system_prompt` | Sets the AI persona/role | any string |

---

## Hands-On Task

Before moving to Module 2, complete this challenge:

**Add `POST /chat/system-test`** that hardcodes system_prompt to:
> "You are a senior PHP developer. Always explain Python concepts using PHP analogies."

Then call it with: `{"message": "Explain Python list comprehensions"}`
and verify the response speaks your language.

Hint: ~15 extra lines — one new route function reusing the same OpenAI client.
