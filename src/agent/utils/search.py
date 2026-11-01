import logging
import os
from typing import Any

from langchain_tavily import TavilySearch
from langchain_tavily._utilities import TavilySearchAPIWrapper
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


def _search_tavily(query: str, api_key: str, max_results: int) -> list[dict[str, Any]]:
    search = TavilySearch(
        max_results=max_results,
        api_wrapper=TavilySearchAPIWrapper(tavily_api_key=api_key),
    )
    result = search.invoke({"query": query})
    documents = result.get("results", result) if isinstance(result, dict) else result
    return list(documents)


class SearchRuntime:
    def __init__(self, personal_tavily_api_key: str | None = None):
        self._server_tavily_api_key = os.getenv("TAVILY_API_KEY", "").strip()
        self._personal_tavily_api_key = (personal_tavily_api_key or "").strip()

    def search(self, query: str, max_results: int) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        tavily_keys = (
            self._server_tavily_api_key,
            self._personal_tavily_api_key,
        )
        for api_key in dict.fromkeys(key for key in tavily_keys if key):
            try:
                return _search_tavily(query, api_key, max_results)
            except Exception as error:
                last_error = error
                logger.warning(
                    "Tavily search failed (%s); trying the next configured provider.",
                    type(error).__name__,
                )

        if last_error is None:
            raise RuntimeError("No Tavily API key is configured.")
        raise RuntimeError("Tavily search failed with all configured keys.") from None

    def clear(self) -> None:
        self._personal_tavily_api_key = ""


def search_documents(
    query: str, config: RunnableConfig, max_results: int
) -> list[dict[str, Any]]:
    runtime = config.get("configurable", {}).get("search_runtime")
    if not isinstance(runtime, SearchRuntime):
        raise RuntimeError("The research run is missing its web search runtime.")
    return runtime.search(query, max_results)
