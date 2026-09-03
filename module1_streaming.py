"""
Module 1 – FastAPI Streaming Endpoint
======================================
PHP analogy:
  - FastAPI  ≈ Laravel/Slim (routing + middleware)
  - Pydantic ≈ DTO / request validation classes
  - StreamingResponse ≈ flushing chunked output via ob_flush()

Architecture:
  Client → POST /chat          → full JSON response  (baseline)
  Client → POST /chat/stream   → Server-Sent Events  (token-by-token streaming)
"""

import os
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv()  # reads .env file  ← equivalent to $_ENV / getenv() in PHP

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(
    title="AI Learning – Module 1",
    description="FastAPI + OpenAI streaming demo",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Request schema  (Pydantic ≈ PHP DTO / form-request validator)
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message")
    system_prompt: str = Field(
        default="You are a helpful AI assistant.",
        description="System-level persona/instructions",
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=4096)


# ---------------------------------------------------------------------------
# Helper: async generator that yields SSE-formatted chunks
# ---------------------------------------------------------------------------
async def token_stream(request: ChatRequest) -> AsyncGenerator[str, None]:
    """
    Calls OpenAI with stream=True and yields each token as an SSE event.
    SSE format expected by browsers / curl:  data: <payload>\n\n
    """
    stream = await client.chat.completions.create(
        model="gpt-4o-mini",          # cheap & fast for learning
        stream=True,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        messages=[
            {"role": "system", "content": request.system_prompt},
            {"role": "user",   "content": request.message},
        ],
    )

    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:                      # skip None chunks (role/finish markers)
            yield f"data: {delta}\n\n"

    yield "data: [DONE]\n\n"           # signal to the client that stream ended


# ---------------------------------------------------------------------------
# Route 1 – non-streaming (baseline / easiest to test)
# ---------------------------------------------------------------------------
@app.post("/chat", summary="Full response (no streaming)")
async def chat(request: ChatRequest) -> dict:
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user",   "content": request.message},
            ],
        )
        return {
            "reply": response.choices[0].message.content,
            "usage": {
                "prompt_tokens":     response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens":      response.usage.total_tokens,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Route 2 – streaming (the interesting one)
# ---------------------------------------------------------------------------
@app.post("/chat/stream", summary="Token-by-token SSE stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        token_stream(request),
        media_type="text/event-stream",   # tells the client to expect SSE
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",    # disables nginx buffering (production tip)
        },
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
