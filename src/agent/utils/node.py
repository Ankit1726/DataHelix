from langchain.messages import SystemMessage, HumanMessage
from langchain_tavily import TavilySearch
from langgraph.types import interrupt
from langchain_core.messages import get_buffer_string
from langchain_core.runnables import RunnableConfig

from src.agent.utils.llm import invoke_model
from src.agent.utils.prompt import search_instructions
from src.agent.utils.state import InterviewState, SearchQuery
from src.agent.utils.state import (
    GenerateAnalystsState,
    InterviewState,
    ResearchGraphState,
)
from src.agent.utils.object import Perspectives, Analyst
from src.agent.utils.prompt import (
    analyst_instructions,
    question_instructions,
    answer_instructions,
    section_writer_instructions,
    report_writer_instructions,
    intro_conclusion_instructions,
)

from dotenv import load_dotenv

load_dotenv()


# nodes
def create_analysts(state: GenerateAnalystsState, config: RunnableConfig):
    """Create analysts"""

    topic = state["topic"]
    max_analysts = state["max_analysts"]
    human_analyst_feedback = state.get("human_analyst_feedback", "")

    # Enforce structured output
    # System message
    system_message = analyst_instructions.format(
        topic=topic,
        human_analyst_feedback=human_analyst_feedback,
        max_analysts=max_analysts,
    )

    # Generate question
    analysts = invoke_model(
        [SystemMessage(content=system_message)]
        + [HumanMessage(content="Generate the set of analysts.")],
        config,
        response_schema=Perspectives,
    )

    return {"analysts": [analyst.model_dump() for analyst in analysts.analysts]}


def human_feedback(state: GenerateAnalystsState):
    feedback = interrupt(
        {
            "question": "Are these analysts okay?",
            "analysts": [
                analyst.model_dump() if hasattr(analyst, "model_dump") else analyst
                for analyst in state.get("analysts", [])
            ],
            "instructions": "Return feedback to regenerate analysts, or return empty/perfect/continue to approve.",
        }
    )

    if feedback is None:
        return {"human_analyst_feedback": None}

    if isinstance(feedback, str):
        feedback = feedback.strip()

        if feedback == "":
            return {"human_analyst_feedback": None}

        if feedback.lower() in {"perfect", "continue", "approved", "yes"}:
            return {"human_analyst_feedback": None}

        return {"human_analyst_feedback": feedback}

    return {"human_analyst_feedback": None}


def human_feedback_update(state: GenerateAnalystsState):
    """this will update the human feedback state"""
    human_feedback = GenerateAnalystsState["human_analyst_feedback"]
    return {"human_analyst_feedback": human_feedback}


def dummy(state: GenerateAnalystsState):
    """No-op node that should be interrupted on"""
    pass


def generate_question(state: InterviewState, config: RunnableConfig):
    """Node to generate a question"""

    # Get state
    analyst = state["analyst"]
    if isinstance(analyst, dict):
        analyst = Analyst.model_validate(analyst)
    messages = state["messages"]

    # Generate question
    system_message = question_instructions.format(goals=analyst.persona)
    question = invoke_model(
        [SystemMessage(content=system_message)] + messages, config
    )

    # Write messages to state
    return {"messages": [question]}


def save_interview(state: InterviewState):
    """Save interviews"""

    # Get messages
    messages = state["messages"]

    # Convert interview to a string
    interview = get_buffer_string(messages)

    # Save to interviews key
    return {"interview": interview}


def write_section(state: InterviewState, config: RunnableConfig):
    """Node to answer a question"""
    # Get state
    interview = state["interview"]
    context = state["context"]
    analyst = state["analyst"]

    if isinstance(analyst, dict):
        analyst = Analyst.model_validate(analyst)

    # Write section using either the gathered source docs from interview (context) or the interview itself (interview)
    system_message = section_writer_instructions.format(focus=analyst.description)
    section = invoke_model(
        [SystemMessage(content=system_message)]
        + [HumanMessage(content=f"Use this source to write your section: {context}")],
        config,
    )

    # Append it to state
    return {"sections": [section.content]}


def generate_answer(state: InterviewState, config: RunnableConfig):
    """Node to answer a question"""

    # Get state
    analyst = state["analyst"]
    messages = state["messages"]
    context = state["context"]

    if isinstance(analyst, dict):
        analyst = Analyst.model_validate(analyst)

    # Answer question
    system_message = answer_instructions.format(goals=analyst.persona, context=context)
    answer = invoke_model(
        [SystemMessage(content=system_message)] + messages, config
    )

    # Name the message as coming from the expert
    answer.name = "expert"

    # Append it to state
    return {"messages": [answer]}


def save_interview(state: InterviewState):
    """Save interviews"""

    # Get messages
    messages = state["messages"]

    # Convert interview to a string
    interview = get_buffer_string(messages)

    # Save to interviews key
    return {"interview": interview}


tavily_search = TavilySearch(max_results=3)

search_instructions_system_message = SystemMessage(content=search_instructions)


# node
def search_web(state: InterviewState, config: RunnableConfig):
    """Retrieve docs from web search"""

    # Search query
    search_query = invoke_model(
        [search_instructions_system_message] + state["messages"],
        config,
        response_schema=SearchQuery,
    )

    # Search
    # search_docs = tavily_search.invoke(search_query.search_query) # updated 1.0
    data = tavily_search.invoke({"query": search_query.search_query})
    search_docs = data.get("results", data)

    # Format
    formatted_search_docs = "\n\n---\n\n".join(
        [
            f'<Document href="{doc["url"]}"/>\n{doc["content"]}\n</Document>'
            for doc in search_docs
        ]
    )

    return {"context": [formatted_search_docs]}


def search_web2(state: InterviewState, config: RunnableConfig):
    """Retrieve docs from web search"""

    # Search query
    search_query = invoke_model(
        [search_instructions_system_message] + state["messages"],
        config,
        response_schema=SearchQuery,
    )

    # Search
    # search_docs = tavily_search.invoke(search_query.search_query) # updated 1.0
    data = tavily_search.invoke({"query": search_query.search_query})
    search_docs = data.get("results", data)

    # Format
    formatted_search_docs = "\n\n---\n\n".join(
        [
            f'<Document href="{doc["url"]}"/>\n{doc["content"]}\n</Document>'
            for doc in search_docs
        ]
    )

    return {"context": [formatted_search_docs]}


def write_report(state: ResearchGraphState, config: RunnableConfig):
    # Full set of sections
    sections = state["sections"]
    topic = state["topic"]

    # Concat all sections together
    formatted_str_sections = "\n\n".join([f"{section}" for section in sections])

    # Summarize the sections into a final report
    system_message = report_writer_instructions.format(
        topic=topic, context=formatted_str_sections
    )
    report = invoke_model(
        [SystemMessage(content=system_message)]
        + [HumanMessage(content=f"Write a report based upon these memos.")],
        config,
    )
    return {"content": report.content}


def write_introduction(state: ResearchGraphState, config: RunnableConfig):
    # Full set of sections
    sections = state["sections"]
    topic = state["topic"]

    # Concat all sections together
    formatted_str_sections = "\n\n".join([f"{section}" for section in sections])

    # Summarize the sections into a final report

    instructions = intro_conclusion_instructions.format(
        topic=topic, formatted_str_sections=formatted_str_sections
    )
    intro = invoke_model(
        [instructions] + [HumanMessage(content=f"Write the report introduction")],
        config,
    )
    return {"introduction": intro.content}


def write_conclusion(state: ResearchGraphState, config: RunnableConfig):

    # Full set of sections
    sections = state["sections"]
    topic = state["topic"]

    # Concat all sections together
    formatted_str_sections = "\n\n".join([f"{section}" for section in sections])

    # Summarize the sections into a final report

    instructions = intro_conclusion_instructions.format(
        topic=topic, formatted_str_sections=formatted_str_sections
    )
    conclusion = invoke_model(
        [instructions] + [HumanMessage(content=f"Write the report conclusion")],
        config,
    )
    return {"conclusion": conclusion.content}


def finalize_report(state: ResearchGraphState):
    """The is the "reduce" step where we gather all the sections, combine them, and reflect on them to write the intro/conclusion"""
    # Save full final report
    content = state["content"].removeprefix("## Insights").lstrip()
    content, source_separator, sources = content.partition("\n## Sources\n")

    final_report = (
        state["introduction"]
        + "\n\n---\n\n"
        + content
        + "\n\n---\n\n"
        + state["conclusion"]
    )
    if source_separator:
        final_report += "\n\n## Sources\n" + sources
    return {"final_report": final_report}
