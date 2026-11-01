from langchain_tavily import TavilySearch
from langchain.messages import SystemMessage

from src.agent.utils.llm import model
from src.agent.utils.prompt import search_instructions
from src.agent.utils.state import InterviewState, SearchQuery

tavily_search = TavilySearch(max_results=4)
search_instructions_system_message = SystemMessage(content=search_instructions)

# node
def search_web(state: InterviewState):
    """Retrieve docs from web search"""

    # Search query
    structured_llm = model.with_structured_output(
        SearchQuery, method="json_schema", strict=True
    )
    search_query = structured_llm.invoke(
        [search_instructions_system_message] + state["messages"]
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


def search_web2(state: InterviewState):
    """Retrieve docs from web search"""

    # Search query
    structured_llm = model.with_structured_output(
        SearchQuery, method="json_schema", strict=True
    )
    search_query = structured_llm.invoke(
        [search_instructions_system_message] + state["messages"]
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