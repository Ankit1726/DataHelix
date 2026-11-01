<div align="center">

# ***Datahelix 🌐***
---

### ***🤖 Multi-Agent Research Studio • Human-in-the-Loop • Live Web Research • Structured Reports***
***LangGraph Agent Orchestration • Groq LLM Inference • Tavily Web Search • Parallel Analyst Research • Human Review Before Research Starts***

<p align="center">
<img src="https://readme-typing-svg.herokuapp.com?font=Poppins&weight=600&size=24&duration=3500&pause=1000&color=14B8A6&center=true&vCenter=true&width=900&lines=Datahelix+Research+Studio;Multi-Agent+Research+%7C+LangGraph+%7C+Groq+%7C+Tavily;From+Question+to+Clarity;Built+by+Ankit"/>
</p>

<p align="center">
<img src="https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python"/>
<img src="https://img.shields.io/badge/LangGraph-Agent_Orchestration-purple?style=for-the-badge"/>
<img src="https://img.shields.io/badge/Groq-LLM_Inference-F55036?style=for-the-badge"/>
<img src="https://img.shields.io/badge/Tavily-Web_Research-14B8A6?style=for-the-badge"/>
<img src="https://img.shields.io/badge/Docker-Deployment-blue?style=for-the-badge&logo=docker"/>
<img src="https://img.shields.io/badge/Render-Hosted-46E3B7?style=for-the-badge&logo=render"/>
</p>

---

### ***🌟 About Datahelix***

***Datahelix is a multi-agent research studio. You type a research question, and the system builds a team of AI analysts, each with a different perspective. You review the team, then the analysts research in parallel using live web search and their findings are combined into a single structured report.***

***It is a live workflow, not a demo. Results come from the configured research pipeline, and no sample report is presented as a real run.***

<p align="center">
<a href="https://datahelix.onrender.com/" target="_blank">
<img src="https://img.shields.io/badge/🚀%20Live%20Demo-Visit%20Datahelix-14B8A6?style=for-the-badge">
</a>
</p>
</div>

---

### ***🌐 Live Demo***

***Web Application 👉 [Datahelix Research Studio](https://datahelix.onrender.com/)***

> ⏳ Hosted on a free tier: the first load may take up to a minute (cold start).

---

### ***📸 Project Preview***

<p align="center">
<img src="./preview/live.png" width="100%" alt="Datahelix UI Preview">
</p>

---

### ***✅ What Datahelix Can Do***

- 🔎 Turn one research question into a focused investigation (up to 500 characters)
- 👥 Generate a team of analysts, each with a distinct perspective (choose team size)
- ✋ Human-in-the-loop: review the analyst team before research starts
- ⚡ Parallel research: analysts gather evidence at the same time
- 🌐 Live web research through Tavily
- 🧾 Final structured report that combines all findings
- 📊 Research activity tracker showing the current stage
- ⚙️ Service configuration panel showing Groq, Tavily and LangGraph status
- 💡 One-click starter prompts (AI in software teams, Urban food waste, Creator economy)
- 🌑 Modern dark-theme interface

---

### ***🧠 How It Works***

```text
                 💬 Research Question
                          │
                          ▼
              1. Find the Angles
        (generate a team of analyst personas)
                          │
                          ▼
              2. Review the Analysts
          (human approves / adjusts the team)
                          │
                          ▼
              3. Gather the Evidence
      ┌───────────┬───────────┬───────────┐
      ▼           ▼           ▼           ▼
  Analyst 1   Analyst 2   Analyst N    (parallel)
      │           │           │
      └─── Tavily web search + Groq LLM ──┘
                          │
                          ▼
              4. Shape the Report
        (combine insights into one report)
                          │
                          ▼
                  📄 Final Report
```

| Step | Stage | Purpose |
|---|---|---|
| 1 | **Find the angles** | Build a team of research perspectives from the question |
| 2 | **Review the analysts** | You decide when the research starts (human-in-the-loop) |
| 3 | **Gather the evidence** | Analysts search sources and build insights in parallel |
| 4 | **Shape the report** | Bring all findings together into a single report |

> 📐 Architecture diagram: see [`preview/agent_architecture.png`](./preview/agent_architecture.png)

---

### ***💡 Example Questions***

- *How is the creator economy evolving with short-form video?*
- *How is AI changing the way software teams work?*
- *What are the main causes of urban food waste and how can cities reduce it?*

---

### ***🧩 Tech Stack***

### ***AI & Agents***

- **LangGraph** for agent orchestration (stateful graph, parallel branches, human-in-the-loop interrupt)
- **Groq** for fast LLM inference
- **Tavily** for live web research

### ***Application***

- **Python 3.11**
- **Backend API** (see `src/`)
- **Custom dark-theme frontend** (HTML, CSS, JavaScript)

### ***Deployment***

- **Docker**
- **Render**

---

### ***📁 Project Structure***

> ✏️ Update this tree to match your actual repository.

```text
Datahelix/
│
├── preview/
│   ├── agent_architecture.png     # Architecture diagram
│   └── live.png                   # Project UI screenshot
│
├── src/
│   ├── graph.py                   # LangGraph workflow (nodes, edges, parallel branches)
│   ├── analysts.py                # Analyst persona generation
│   ├── research.py                # Evidence gathering with Tavily + Groq
│   ├── report.py                  # Final report generation
│   ├── config.py                  # Environment settings and API key checks
│   └── main.py                    # Application entrypoint / API routes
│
├── ui/
│   ├── static/                    # CSS, JS, assets
│   └── templates/                 # HTML templates
│
├── .dockerignore
├── .env                           # Environment variables (not committed)
├── .gitignore
├── Dockerfile                     # Docker configuration
├── requirements.txt               # Python dependencies
└── run.py                         # Run the application
```

---

### ***⚙️ Run Locally***

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/Datahelix.git
cd Datahelix

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your API keys
cp .env.example .env
```

```env
GROQ_API_KEY=your_groq_key
TAVILY_API_KEY=your_tavily_key
```

```bash
# 5. Start the app
python run.py
```

Run with Docker:

```bash
docker build -t datahelix .
docker run -p 8000:8000 --env-file .env datahelix
```

---

### ***🧪 Why Human-in-the-Loop Matters***

Fully automatic research can drift in the wrong direction. Datahelix pauses after generating the analyst team so you can check the angles before any search budget is spent.

```text
Question → Analyst team generated
                ↓
        Human reviews the team
                ↓
   Approve → Parallel research → Report
   Adjust  → Regenerate analysts
```

---

### ***⚠️ Limitations***

- Report quality depends on the quality of web sources returned by search.
- LLM output can contain mistakes; always verify important claims against the sources.
- Free-tier hosting may have cold starts and non-persistent storage.
- Groq and Tavily require network access, valid API keys and are subject to rate limits.

---

### ***🔮 Future Enhancements***

- Export reports to PDF / Markdown
- Saved research history and user accounts
- Inline source citations with links in every report section
- Streaming progress for each analyst
- Support for uploading private documents as an extra source
- Evaluation suite for report quality

---

### ***🎯 Real-World Use Cases***

✔ Market and Trend Research

✔ Topic Exploration for Writers and Students

✔ Competitive Analysis

✔ Literature and Background Scans

✔ Multi-Agent Workflow Demonstration

✔ AI/ML Portfolio Project

---

## ***🧠 Key Learning Outcomes***

1. Design a stateful multi-agent workflow with LangGraph.
2. Run analyst agents in parallel and merge their results.
3. Add a human-in-the-loop approval step to an agent graph.
4. Integrate Tavily live web search with an LLM.
5. Use Groq for low-latency LLM inference.
6. Generate a structured report from multiple agent outputs.
7. Build a custom research-studio frontend.
8. Package the app with Docker and deploy it on Render.

---

## ***👨‍💻 Developer***

<div align="center">

# ***ANKIT GUPTA 👦***

### ***AI Engineer • AI Backend Developer • GenAI Developer***

**Building practical AI systems with Python, RAG and multi-agent workflows**

</div>

---

### ***⭐ Support the Project***

If you find Datahelix useful:

- ⭐ Star the repository
- 🍴 Fork the project
- 🐛 Report issues
- 💡 Suggest new features
- 📢 Share the project

---

<div align="center">

### ***Datahelix: From Question to Clarity 🌐***

***Ask Big Questions. Review the Team. Read the Report.***

### ***Built with ❤️ by Ankit***

</div>
