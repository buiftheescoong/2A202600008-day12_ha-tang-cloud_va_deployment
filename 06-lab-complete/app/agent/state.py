from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    The state of the agent is a dictionary containing a list of messages.
    'add_messages' is a reducer that appends new messages to the existing list.
    """
    messages: Annotated[list[BaseMessage], add_messages]
