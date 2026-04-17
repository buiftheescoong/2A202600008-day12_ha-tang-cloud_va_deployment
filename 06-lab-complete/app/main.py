import time
import json
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import check_rate_limit
from app.cost_guard import check_budget
from app.agent.graph import agent_app

# ─────────────────────────────────────────────────────────
# Logging & Globals
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({"event": "startup", "app": settings.app_name}))
    _is_ready = True
    yield
    _is_ready = False
    # Lifespan handles SIGTERM for graceful shutdown
    logger.info(json.dumps({"event": "shutdown", "signal": "SIGTERM"}))

# ─────────────────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(default="default_session", description="Unique session ID")

class ChatResponse(BaseModel):
    session_id: str
    answer: str
    timestamp: str

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "uptime": round(time.time() - START_TIME, 1),
        "version": settings.app_version
    }

@app.get("/ready")
def ready():
    if not _is_ready:
        raise HTTPException(503, "Service not ready")
    return {"status": "ready"}

@app.post("/ask", response_model=ChatResponse)
async def ask(
    body: ChatRequest,
    user_id: str = Depends(verify_api_key)
):
    """
    Production AI Agent Endpoint.
    Handles auth, rate limiting, budget, and maintains stateless conversation via Redis.
    """
    # 1. Protection Layers
    check_rate_limit(user_id)
    check_budget(user_id)
    
    # 2. Configure LangGraph Thread (user_id + session_id)
    # This ensures horizontal scaling works: any instance can pick up any session.
    thread_id = f"{user_id}:{body.session_id}"
    config = {"configurable": {"thread_id": thread_id}}
    
    # 3. Invoke Agent
    logger.info(json.dumps({"event": "agent_start", "thread_id": thread_id}))
    try:
        inputs = {"messages": [("user", body.question)]}
        result = agent_app.invoke(inputs, config=config)
        
        # The last message in the state is the agent's response
        raw_answer = result["messages"][-1].content
        
        # Handle cases where content is a list (common with Gemini/Claude)
        if isinstance(raw_answer, list):
            final_answer = "".join([
                c.get("text", "") if isinstance(c, dict) else str(c) 
                for c in raw_answer
            ])
        else:
            final_answer = str(raw_answer)
        
        return ChatResponse(
            session_id=body.session_id,
            answer=final_answer,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        logger.error(json.dumps({"event": "agent_error", "error": str(e)}))
        raise HTTPException(status_code=500, detail="Internal Agent Error")

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        timeout_graceful_shutdown=30
    )
