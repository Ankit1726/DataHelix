import os
import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from fastapi.testclient import TestClient
from langchain.messages import AIMessage
from langgraph.types import Command

import main
from src.agent.utils import node as agent_nodes
from src.agent.utils.node import finalize_report
from src.agent.utils.object import Analyst, Perspectives
from src.agent.utils.state import SearchQuery


class FakeResearchGraph:
    def __init__(self):
        self.snapshot = self._waiting_snapshot()

    @staticmethod
    def _waiting_snapshot():
        return SimpleNamespace(
            values={
                "analysts": [
                    {
                        "name": "Research analyst",
                        "role": "Independent researcher",
                        "affiliation": "Demo",
                    }
                ]
            },
            tasks=[SimpleNamespace(interrupts=[object()])],
        )

    def invoke(self, value, config):
        if isinstance(value, Command) and value.resume == "perfect":
            self.snapshot = SimpleNamespace(
                values={
                    "analysts": self.snapshot.values["analysts"],
                    "final_report": "## Findings\nEvidence-based results.",
                },
                tasks=[],
            )
        else:
            self.snapshot = self._waiting_snapshot()

    def get_state(self, config):
        return self.snapshot


class FakeStructuredModel:
    def __init__(self, schema):
        self.schema = schema

    def invoke(self, messages):
        if self.schema is Perspectives:
            prompt = str(getattr(messages[0], "content", messages[0]))
            match = re.search(r"Pick the top (\d+) themes", prompt)
            analyst_count = int(match.group(1)) if match else 1
            return Perspectives(
                analysts=[
                    Analyst(
                        name=f"Test analyst {index + 1}",
                        role="Evidence reviewer",
                        affiliation="Test lab",
                        description=f"Checks research claims against source {index + 1}.",
                    )
                    for index in range(analyst_count)
                ]
            )
        if self.schema is SearchQuery:
            return SearchQuery(search_query="test research evidence")
        raise AssertionError(f"Unexpected structured output schema: {self.schema}")


class FakeLanguageModel:
    def with_structured_output(self, schema, **kwargs):
        return FakeStructuredModel(schema)

    def invoke(self, messages):
        first_message = messages[0]
        prompt = str(getattr(first_message, "content", first_message))
        if prompt.startswith("You are an analyst tasked with interviewing"):
            return AIMessage(content="What evidence supports this conclusion?")
        if prompt.startswith("You are an expert being interviewed"):
            return AIMessage(content="A test finding supported by source [1].")
        if prompt.startswith("You are an expert technical writer."):
            return AIMessage(
                content=(
                    "## Evidence review\nA grounded test finding.\n"
                    "### Sources\n[1] https://example.com"
                )
            )
        if prompt.startswith("You are a technical writer creating a report"):
            return AIMessage(
                content="## Insights\nThe result ends with insights.\n\n"
                "## Sources\n[1] https://example.com"
            )
        if prompt.startswith("You are a technical writer finishing a report"):
            last_message = messages[-1]
            last_content = str(getattr(last_message, "content", last_message))
            if "Write the report introduction" in last_content:
                return AIMessage(content="## Introduction\nA test overview.")
            if "Write the report conclusion" in last_content:
                return AIMessage(content="## Conclusion\nA test summary.")
        raise AssertionError(f"Unexpected model prompt: {prompt[:100]}")


class ResearchApiTests(unittest.TestCase):
    def setUp(self):
        with main._jobs_lock:
            main._jobs.clear()
        main._research_graph = FakeResearchGraph()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        main._research_graph = None
        with main._jobs_lock:
            main._jobs.clear()

    def test_health_and_static_ui(self):
        health = self.client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(set(health.json()["services"]), set(main.REQUIRED_KEYS))

        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Crafted with", page.text)
        self.assertIn("by Ankit", page.text)
        self.assertEqual(self.client.get("/static/app.js").status_code, 200)

    def test_missing_credentials_disable_research(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "", "TAVILY_API_KEY": ""}):
            health = self.client.get("/api/health")
            self.assertFalse(health.json()["ready"])
            response = self.client.post(
                "/api/research", json={"topic": "Valid research question"}
            )
        self.assertEqual(response.status_code, 503)

    def test_rejects_invalid_topics_and_analyst_counts(self):
        for topic in ("  ", "ab", "x" * 501):
            with self.subTest(topic_length=len(topic)):
                response = self.client.post("/api/research", json={"topic": topic})
                self.assertEqual(response.status_code, 422)

        for analyst_count in (0, 4, 1.5, True):
            with self.subTest(analyst_count=analyst_count):
                response = self.client.post(
                    "/api/research",
                    json={"topic": "Valid research question", "max_analysts": analyst_count},
                )
                self.assertEqual(response.status_code, 422)

    def test_revise_then_approve_completes_job(self):
        with patch.dict(
            os.environ,
            {"GROQ_API_KEY": "test-key", "TAVILY_API_KEY": "test-key"},
        ):
            start = self.client.post(
                "/api/research",
                json={"topic": "  A valid research question  ", "max_analysts": 1},
            )
            self.assertEqual(start.status_code, 202)
            job_id = start.json()["id"]

            job = self.client.get(f"/api/research/{job_id}")
            self.assertEqual(job.status_code, 200)
            self.assertEqual(job.json()["topic"], "A valid research question")
            self.assertEqual(job.json()["status"], "awaiting_approval")
            self.assertEqual(len(job.json()["analysts"]), 1)

            at_capacity = self.client.post(
                "/api/research", json={"topic": "Another valid question"}
            )
            self.assertEqual(at_capacity.status_code, 429)

            revision = self.client.post(
                f"/api/research/{job_id}/approval",
                json={"approved": False, "feedback": "Add a skeptical perspective"},
            )
            self.assertEqual(revision.status_code, 202)
            self.assertEqual(
                self.client.get(f"/api/research/{job_id}").json()["status"],
                "awaiting_approval",
            )

            approval = self.client.post(
                f"/api/research/{job_id}/approval",
                json={"approved": True},
            )
            self.assertEqual(approval.status_code, 202)
            completed = self.client.get(f"/api/research/{job_id}").json()
            self.assertEqual(completed["status"], "completed")
            self.assertEqual(completed["report"], "## Findings\nEvidence-based results.")

            duplicate_approval = self.client.post(
                f"/api/research/{job_id}/approval",
                json={"approved": True},
            )
            self.assertEqual(duplicate_approval.status_code, 409)

    def test_rejects_empty_revision_and_unknown_jobs(self):
        with patch.dict(
            os.environ,
            {"GROQ_API_KEY": "test-key", "TAVILY_API_KEY": "test-key"},
        ):
            start = self.client.post(
                "/api/research", json={"topic": "A valid research question"}
            )
            job_id = start.json()["id"]
            revision = self.client.post(
                f"/api/research/{job_id}/approval",
                json={"approved": False, "feedback": "   "},
            )

        self.assertEqual(revision.status_code, 422)
        self.assertEqual(
            self.client.get("/api/research/unknown-job").status_code, 404
        )
        self.assertEqual(
            self.client.post(
                "/api/research/unknown-job/approval",
                json={"approved": True},
            ).status_code,
            404,
        )


class ReportFormattingTests(unittest.TestCase):
    def test_preserves_report_text_and_extracts_sources(self):
        report = finalize_report(
            {
                "content": (
                    "## Insights\nThe final word is insights\n\n"
                    "## Sources\n[1] https://example.com"
                ),
                "introduction": "## Introduction\nOverview.",
                "conclusion": "## Conclusion\nSummary.",
            }
        )["final_report"]

        self.assertIn("The final word is insights", report)
        self.assertIn("## Sources\n[1] https://example.com", report)


class LangGraphWorkflowTests(unittest.TestCase):
    def test_real_graph_resumes_approval_and_generates_report(self):
        from src.agent.deep_agent import graph

        with main._jobs_lock:
            main._jobs.clear()
        main._research_graph = graph
        client = TestClient(main.app)
        try:
            with (
                patch.dict(
                    os.environ,
                    {"GROQ_API_KEY": "test-key", "TAVILY_API_KEY": "test-key"},
                ),
                patch.object(agent_nodes, "model", FakeLanguageModel()),
                patch.object(
                    agent_nodes,
                    "tavily_search",
                    SimpleNamespace(
                        invoke=lambda query: {
                            "results": [
                                {
                                    "url": "https://example.com",
                                    "content": "A test source.",
                                }
                            ]
                        }
                    ),
                ),
            ):
                for analyst_count in (1, 2, 3):
                    with self.subTest(analyst_count=analyst_count):
                        start = client.post(
                            "/api/research",
                            json={
                                "topic": "Test the actual research graph",
                                "max_analysts": analyst_count,
                            },
                        )
                        self.assertEqual(start.status_code, 202)
                        job_id = start.json()["id"]

                        awaiting_approval = client.get(
                            f"/api/research/{job_id}"
                        ).json()
                        self.assertEqual(
                            awaiting_approval["status"], "awaiting_approval"
                        )
                        self.assertEqual(
                            len(awaiting_approval["analysts"]), analyst_count
                        )

                        approval = client.post(
                            f"/api/research/{job_id}/approval",
                            json={"approved": True},
                        )
                        self.assertEqual(approval.status_code, 202)

                        completed = client.get(f"/api/research/{job_id}").json()
                        self.assertEqual(
                            completed["status"], "completed", completed["error"]
                        )
                        self.assertIn(
                            "The result ends with insights.", completed["report"]
                        )
                        self.assertIn(
                            "## Sources\n[1] https://example.com",
                            completed["report"],
                        )
        finally:
            client.close()
            main._research_graph = None
            with main._jobs_lock:
                main._jobs.clear()


if __name__ == "__main__":
    unittest.main()
