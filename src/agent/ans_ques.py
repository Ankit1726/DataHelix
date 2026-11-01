from src.agent.utils.state import InterviewState
from src.agent.utils.node import (
    generate_question,
    search_web,
    generate_answer,
    save_interview,
    write_section,
)
from src.agent.utils.state import InterviewState
from src.agent.utils.edge import route_messages
from langgraph.graph import StateGraph, START, END

# Add nodes and edges
interview_builder = StateGraph(InterviewState)
interview_builder.add_node("ask_question", generate_question)
interview_builder.add_node("search_web", search_web)
interview_builder.add_node("answer_question", generate_answer)
interview_builder.add_node("save_interview", save_interview)
interview_builder.add_node("write_section", write_section)

# Flow
interview_builder.add_edge(START, "ask_question")
interview_builder.add_edge("ask_question", "search_web")
interview_builder.add_edge("search_web", "answer_question")
interview_builder.add_conditional_edges(
    "answer_question", route_messages, ["ask_question", "save_interview"]
)
interview_builder.add_edge("save_interview", "write_section")
interview_builder.add_edge("write_section", END)

question_answer_graph = interview_builder.compile()