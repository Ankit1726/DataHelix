import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from src.agent.utils.llm import GroqModelRuntime, invoke_model
from src.agent.utils.object import Analyst, Perspectives


class RateLimitError(Exception):
    status_code = 429


class UnauthorizedError(Exception):
    status_code = 401


class FakeModel:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def with_structured_output(self, *_args, **_kwargs):
        return self

    def invoke(self, _messages):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


class GroqFallbackTests(unittest.TestCase):
    def test_rate_limit_switches_to_personal_key_for_remaining_calls(self):
        server_model = FakeModel(error=RateLimitError())
        personal_model = FakeModel(result="personal result")
        with (
            patch.dict(os.environ, {"GROQ_API_KEY": "server-key"}),
            patch(
                "src.agent.utils.llm._create_model",
                side_effect=[server_model, personal_model],
            ),
        ):
            runtime = GroqModelRuntime("personal-key")

            self.assertEqual(runtime.invoke(["prompt"]), "personal result")
            self.assertEqual(runtime.invoke(["next prompt"]), "personal result")
            runtime.clear()
            self.assertEqual(runtime._personal_api_key, "")
            self.assertIsNone(runtime._personal_model)
            self.assertIs(runtime._active_model, server_model)

        self.assertEqual(server_model.calls, 1)
        self.assertEqual(personal_model.calls, 2)

    def test_non_rate_limit_errors_do_not_use_personal_key(self):
        server_model = FakeModel(error=UnauthorizedError())
        personal_model = FakeModel(result="must not be used")
        with (
            patch.dict(os.environ, {"GROQ_API_KEY": "server-key"}),
            patch(
                "src.agent.utils.llm._create_model",
                side_effect=[server_model, personal_model],
            ),
        ):
            runtime = GroqModelRuntime("personal-key")

            with self.assertRaises(UnauthorizedError):
                runtime.invoke(["prompt"])

        self.assertEqual(server_model.calls, 1)
        self.assertEqual(personal_model.calls, 0)

    def test_personal_key_is_primary_when_server_key_is_missing(self):
        personal_model = FakeModel(result="personal result")
        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "src.agent.utils.llm._create_model",
                return_value=personal_model,
            ) as create_model,
        ):
            runtime = GroqModelRuntime("personal-key")

            self.assertEqual(runtime.invoke(["prompt"]), "personal result")

        create_model.assert_called_once_with("personal-key", max_retries=5)
        self.assertEqual(personal_model.calls, 1)

    def test_a_key_is_required(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ValueError, "API key is required"):
                GroqModelRuntime()

    def test_model_invocation_requires_a_run_runtime(self):
        with self.assertRaisesRegex(RuntimeError, "missing its Groq model runtime"):
            invoke_model(["prompt"], {"configurable": {}})

    def test_graph_node_receives_job_runtime(self):
        with patch.dict(
            os.environ,
            {
                "TAVILY_API_KEY": "test-tavily-key",
                "LANGCHAIN_TRACING_V2": "false",
                "LANGSMITH_TRACING": "false",
                "LANGSMITH_TRACING_V2": "false",
            },
        ):
            from src.agent.deep_agent import graph

            runtime = object()

            def fake_invoke(_messages, config, response_schema=None):
                self.assertIs(config["configurable"]["groq_runtime"], runtime)
                self.assertIs(response_schema, Perspectives)
                return Perspectives(
                    analysts=[
                        Analyst(
                            affiliation="Independent",
                            name="Test analyst",
                            role="Researcher",
                            description="Studies the test topic.",
                        )
                    ]
                )

            thread_id = "groq-runtime-test"
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "groq_runtime": runtime,
                }
            }
            with patch(
                "src.agent.utils.node.invoke_model", side_effect=fake_invoke
            ):
                graph.invoke(
                    {"topic": "A test topic", "max_analysts": 1, "sections": []},
                    config,
                )
                snapshot = graph.get_state(config)

        self.assertEqual(snapshot.values["analysts"][0]["name"], "Test analyst")
        self.assertTrue(snapshot.tasks[0].interrupts)


class ResearchApiTests(unittest.TestCase):
    def test_health_reports_shared_groq_key_and_personal_key_support(self):
        with (
            patch.dict(
                os.environ,
                {
                    "GROQ_API_KEY": "server-test-key",
                    "TAVILY_API_KEY": "tavily-test-key",
                },
            ),
            TestClient(main.app) as client,
        ):
            response = client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ready"])
        self.assertTrue(response.json()["personal_groq_key_supported"])
        self.assertTrue(response.json()["services"]["GROQ_API_KEY"])
        self.assertTrue(response.json()["services"]["TAVILY_API_KEY"])

    def test_personal_key_is_accepted_but_never_returned(self):
        job_id = None
        with (
            patch.dict(
                os.environ,
                {
                    "GROQ_API_KEY": "server-test-key",
                    "TAVILY_API_KEY": "tavily-test-key",
                    "LANGCHAIN_TRACING_V2": "false",
                    "LANGSMITH_TRACING": "false",
                    "LANGSMITH_TRACING_V2": "false",
                },
            ),
            patch("src.agent.utils.llm._create_model", return_value=FakeModel()),
            patch("main._run_research") as run_research,
            TestClient(main.app) as client,
        ):
            response = client.post(
                "/api/research",
                json={
                    "topic": "A test research question",
                    "max_analysts": 1,
                    "groq_api_key": "  personal-test-key  ",
                },
            )
            self.assertEqual(response.status_code, 202)
            job_id = response.json()["id"]
            run_research.assert_called_once_with(job_id)

            job_response = client.get(f"/api/research/{job_id}")
            self.assertEqual(job_response.status_code, 200)
            self.assertNotIn("groq_api_key", job_response.text)
            self.assertNotIn("personal-test-key", job_response.text)
            self.assertEqual(
                main._jobs[job_id].groq_runtime._personal_api_key,
                "personal-test-key",
            )

        if job_id is not None:
            main._clear_job_runtime(job_id)
            with main._jobs_lock:
                main._jobs.pop(job_id, None)

    def test_missing_groq_key_has_actionable_error(self):
        with (
            patch.dict(os.environ, {"TAVILY_API_KEY": "tavily-test-key"}, clear=True),
            TestClient(main.app) as client,
        ):
            response = client.post(
                "/api/research",
                json={"topic": "A test research question", "max_analysts": 1},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("Enter your Groq API key above", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
