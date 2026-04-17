import logging
import json

logger = logging.getLogger("agent")

def log_llm_call(step, content, tool_calls, usage, latency_ms, provider, model):
    logger.info(json.dumps({
        "event": "llm_call",
        "step": step,
        "usage": usage,
        "latency_ms": latency_ms,
        "model": model,
        "tool_calls_count": len(tool_calls)
    }))

def log_tool_call(tool_name, tool_input, tool_output, latency_ms):
    logger.info(json.dumps({
        "event": "tool_call",
        "tool": tool_name,
        "latency_ms": latency_ms,
        "status": "success" if "ERROR" not in str(tool_output) else "error"
    }))
