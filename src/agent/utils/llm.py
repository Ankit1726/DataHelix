import os
import threading
from typing import Any

from langchain_groq import ChatGroq
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "openai/gpt-oss-20b"


def _create_model(
    api_key: str, model_name: str = MODEL_NAME, max_retries: int = 1
) -> ChatGroq:
    return ChatGroq(
        model=model_name,
        api_key=api_key,
        max_retries=max_retries,
        rate_limiter=InMemoryRateLimiter(
            requests_per_second=0.4,
            check_every_n_seconds=0.1,
            max_bucket_size=1,
        ),
        streaming=True,
    )


def _is_rate_limit_error(error: Exception) -> bool:
    response = getattr(error, "response", None)
    status_code = getattr(error, "status_code", None) or getattr(
        response, "status_code", None
    )
    return status_code == 429


class GroqModelRuntime:
    def __init__(
        self,
        personal_api_key: str | None = None,
        model_name: str = MODEL_NAME,
    ):
        server_api_key = os.getenv("GROQ_API_KEY", "").strip()
        self._model_name = model_name
        self._server_model = (
            _create_model(server_api_key, model_name=model_name, max_retries=1)
            if server_api_key
            else None
        )
        self._personal_api_key = (personal_api_key or "").strip()
        self._personal_model: ChatGroq | None = None
        self._lock = threading.Lock()

        if self._server_model is not None:
            self._active_model: ChatGroq | None = self._server_model
        elif self._personal_api_key:
            self._active_model = self._get_personal_model()
        else:
            raise ValueError("A server or personal Groq API key is required.")

    def _get_personal_model(self) -> ChatGroq:
        if self._personal_model is None:
            self._personal_model = _create_model(
                self._personal_api_key,
                model_name=self._model_name,
                max_retries=5,
            )
        return self._personal_model

    @staticmethod
    def _invoke(model: ChatGroq, messages: list[Any], response_schema: Any) -> Any:
        if response_schema is not None:
            model = model.with_structured_output(
                response_schema, method="json_schema", strict=True
            )
        return model.invoke(messages)

    def invoke(
        self,
        messages: list[Any],
        response_schema: Any = None,
    ) -> Any:
        with self._lock:
            active_model = self._active_model
        if active_model is None:
            raise RuntimeError("This research run's Groq runtime has been cleared.")

        try:
            return self._invoke(active_model, messages, response_schema)
        except Exception as error:
            if (
                not _is_rate_limit_error(error)
                or active_model is not self._server_model
                or not self._personal_api_key
            ):
                raise

            with self._lock:
                if self._active_model is self._server_model:
                    self._active_model = self._get_personal_model()
                fallback_model = self._active_model
            if fallback_model is None:
                raise RuntimeError("This research run's Groq runtime has been cleared.")

            return self._invoke(fallback_model, messages, response_schema)

    def clear(self) -> None:
        with self._lock:
            self._personal_api_key = ""
            self._personal_model = None
            self._active_model = self._server_model


def invoke_model(
    messages: list[Any],
    config: RunnableConfig,
    response_schema: Any = None,
) -> Any:
    runtime = config.get("configurable", {}).get("groq_runtime")
    if not isinstance(runtime, GroqModelRuntime):
        raise RuntimeError("The research run is missing its Groq model runtime.")
    return runtime.invoke(messages, response_schema)