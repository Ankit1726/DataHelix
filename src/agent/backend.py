from src.agent.utils.state import GenerateAnalystsState
from src.agent.utils.node import create_analysts, human_feedback, dummy
from src.agent.utils.edge import should_continue
from langgraph.graph import START, END, StateGraph

# building our graph
builder = StateGraph(GenerateAnalystsState)

builder.add_node("create_analysts", create_analysts)
builder.add_node("human_feedback", human_feedback)
builder.add_node("dummy", dummy)

builder.add_edge(START, "create_analysts")
builder.add_edge("create_analysts", "human_feedback")
builder.add_conditional_edges(
    "human_feedback", should_continue, ["create_analysts", "dummy"]
)

builder.add_edge("dummy", END)
graph = builder.compile(interrupt_before=["human_feedback"])