from langchain.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from src.agent.utils.llm import invoke_model
from src.agent.utils.prompt import search_instructions
from src.agent.utils.search import search_documents
from src.agent.utils.state import InterviewState, SearchQuery

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

    search_docs = search_documents(search_query.search_query, config, max_results=4)

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

    search_docs = search_documents(search_query.search_query, config, max_results=4)

    # Format
    formatted_search_docs = "\n\n---\n\n".join(
        [
            f'<Document href="{doc["url"]}"/>\n{doc["content"]}\n</Document>'
            for doc in search_docs
        ]
    )

    return {"context": [formatted_search_docs]}