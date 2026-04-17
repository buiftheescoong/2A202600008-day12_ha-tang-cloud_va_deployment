import time
from app.agent.state import AgentState
from app.agent.tools import tools
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, ToolMessage
from app.config import settings
from app.logger import log_llm_call, log_tool_call


# Initialize the base model
llm = ChatGoogleGenerativeAI(
    model=settings.MODEL_NAME, 
    google_api_key=settings.GEMINI_API_KEY,
    temperature=settings.TEMPERATURE
)


# System prompt when USE_TOOLS = True (full tool-augmented agent)
SYSTEM_PROMPT_WITH_TOOLS = """You are a professional Smart Travel Assistant. 
Your mission is to support users with all information related to travel:
1. Suggest attractive destinations. 
2. Provide weather info.
3. Provide flight info.
4. Provide hotel info.
5. Provide currency/costs info.
6. Always use the 'search_web_info' tool for real-time data such as current time, weather,....
7. Communicate with user friendly even though out of topics

Rules:
- Maintain a friendly, professional tone. If the user provides info, acknowledge it and continue.
"""

# System prompt when USE_TOOLS = False (LLM-only mode)
SYSTEM_PROMPT_NO_TOOLS = """You are a professional Smart Travel Assistant. 
Your mission is to support users with all information related to travel.
- If the user asks about topics that are out of the travel domain, respond with: "I am not within my scope, please ask again".
"""
print("USE_TOOLS: " + str(settings.USE_TOOLS))
# Active system prompt – selected at import time based on config
SYSTEM_PROMPT = SYSTEM_PROMPT_WITH_TOOLS if settings.USE_TOOLS else SYSTEM_PROMPT_NO_TOOLS



def _extract_usage(response) -> dict:
    """Extract token usage from a LangChain/Gemini response object.
    Supports both dict‑like and attribute‑style metadata.
    """
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    try:
        meta = getattr(response, "usage_metadata", None) or getattr(response, "usage", None)
        if meta is None:
            return usage
        # If meta behaves like a dict, use get(); otherwise fall back to getattr
        if isinstance(meta, dict):
            usage["prompt_tokens"] = meta.get("input_tokens") or meta.get("prompt_token_count", 0)
            usage["completion_tokens"] = meta.get("output_tokens") or meta.get("candidates_token_count", 0)
            usage["total_tokens"] = meta.get("total_tokens") or meta.get("total_token_count", 0)
        else:
            usage["prompt_tokens"] = getattr(meta, "input_tokens", 0) or getattr(meta, "prompt_token_count", 0)
            usage["completion_tokens"] = getattr(meta, "output_tokens", 0) or getattr(meta, "candidates_token_count", 0)
            usage["total_tokens"] = getattr(meta, "total_tokens", 0) or getattr(meta, "total_token_count", 0)
    except Exception as e:
        # Keep defaults on error and optionally log
        print(f"[WARN] Failed to extract usage metadata: {e}")
    return usage


def call_model(state: AgentState):
    """
    Node that calls the LLM with the current message history.
    It conditionally binds tools if settings.USE_TOOLS is True.
    Logs the invocation details (content, tool_calls, usage, latency).
    """
    messages = state["messages"]

    # Prepend the system prompt if it's the beginning of the conversation
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    # Conditionally bind tools based on global settings
    model = llm.bind_tools(tools) if settings.USE_TOOLS else llm

    # --- invoke with timing ---
    t0 = time.time()
    response = model.invoke(messages)
    latency_ms = int((time.time() - t0) * 1000)

    # --- parse response fields ---
    content = response.content if isinstance(response.content, str) else ""
    tool_calls = [
        {"name": tc["name"], "args": tc.get("args", {})}
        for tc in (response.tool_calls or [])
    ]
    usage = _extract_usage(response)

    log_llm_call(
        step="call_model",
        content=content,
        tool_calls=tool_calls,
        usage=usage,
        latency_ms=latency_ms,
        provider="google",
        model=settings.MODEL_NAME,
    )

    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Logged ToolNode – wraps each individual tool execution with timing + logs
# ---------------------------------------------------------------------------

class LoggedToolNode:
    """
    Wraps LangGraph's ToolNode and adds per-tool logging.
    """
    def __init__(self, tool_list):
        self._tool_node = ToolNode(tool_list)
        # Build a lookup by name for direct invocation timing
        self._tools_by_name = {t.name: t for t in tool_list}

    def __call__(self, state: AgentState):
        messages = state["messages"]
        last_msg = messages[-1]

        # Execute all tool calls in the last AI message one-by-one for individual timing
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            tool_messages = []
            for tc in last_msg.tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("args", {})
                tool_id   = tc["id"]

                tool_fn = self._tools_by_name.get(tool_name)
                if tool_fn:
                    t0 = time.time()
                    try:
                        result = tool_fn.invoke(tool_args)
                        output = str(result)
                    except Exception as e:
                        output = f"ERROR: {e}"
                    latency_ms = int((time.time() - t0) * 1000)

                    log_tool_call(
                        tool_name=tool_name,
                        tool_input=tool_args,
                        tool_output=output,
                        latency_ms=latency_ms,
                    )

                    tool_messages.append(
                        ToolMessage(content=output, tool_call_id=tool_id)
                    )
                else:
                    # Fallback: unknown tool, let the standard ToolNode handle it
                    tool_messages.append(
                        ToolMessage(
                            content=f"Tool '{tool_name}' not found.",
                            tool_call_id=tool_id,
                        )
                    )

            return {"messages": tool_messages}

        # Fallback if somehow no tool calls
        return self._tool_node(state)


# Export the logged tool node
tool_node = LoggedToolNode(tools)
