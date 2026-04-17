from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.redis import RedisSaver
from app.agent.state import AgentState
from app.agent.nodes import call_model, tool_node
from app.config import settings

def should_continue(state: AgentState):
    """
    Conditional edge to decide whether to call tools or end the conversation.
    """
    messages = state["messages"]
    last_message = messages[-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

def human_review(state: AgentState):
    pass

def route_after_tools(state: AgentState):
    messages = state["messages"]
    last_msg = messages[-1]
    if "REQUESTED_USER_INPUT" in getattr(last_msg, "content", ""):
        return "human_review"
    return "agent"

workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", tool_node)
workflow.add_node("human_review", human_review)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
workflow.add_conditional_edges("tools", route_after_tools, {"human_review": "human_review", "agent": "agent"})
workflow.add_edge("human_review", "agent")

# Redis checkpointer for stateless scaling
try:
    # Use from_conn_string which is the standard entry point for 0.4.1
    # Note: It returns a context manager in this library version
    _memory_cm = RedisSaver.from_conn_string(settings.redis_url)
    
    # Manually enter the context to keep the connection open for the module's lifetime
    if hasattr(_memory_cm, "__enter__"):
        memory = _memory_cm.__enter__()
    else:
        memory = _memory_cm
        
    # Required: setup indices in Redis Stack
    memory.setup()
    print("[INFO] RedisSaver initialized successfully.")
except Exception as e:
    import traceback
    print(f"[ERROR] RedisSaver setup failed: {str(e)}")
    print(traceback.format_exc())
    memory = None

# Compile the graph
agent_app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["human_review"]
)
