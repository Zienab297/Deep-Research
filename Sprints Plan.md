# Sprints

Four sprints of about two weeks each. Adjust to your available time. Each sprint ends with a measured result against the golden set, and no component stays unless it beats the previous baseline.

This is a general product: users bring their own PDFs, so arXiv is test data only, and isolation, cost control, and non-academic documents are planned from the start.

---

## Sprint 1: Baseline and Golden Set (MVP)

**Goal:** A working end-to-end pipeline that handles text, tables, and images, with a baseline score.

### Tasks

- Choose one arXiv category and download 10 PDFs. Add one invoice, one report, one scanned document.
- Write the golden set: 15 to 20 questions covering single-document facts, table values, image-only values, cross-document comparisons, and no-answer questions.
- Build ingestion: page analysis, PyMuPDF4LLM and OCR side by side (OCR only on image or low-text pages), merge by page, then Cognee add and cognify.
- Build retrieval and single-call streamed answer, with a "not found in your documents" response.
- Expose `POST /ingest` and `POST /ask`.
- Run the eval and label each failure by cause.

### Tools

|Purpose|Tool|
|---|---|
|Text and tables|PyMuPDF4LLM|
|OCR|Tesseract|
|Knowledge graph and retrieval|Cognee|
|Synthesis|GPT-4o|
|API|FastAPI, Uvicorn|
|Evaluation|Python script, `golden.jsonl`|

### Expected outcome

- Pipeline runs end to end on the test documents.
- Baseline scores recorded: overall, table, image, and no-answer.
- Ingestion time and cost per document known.
- Failures labeled: retrieval miss, table garbled, OCR error, synthesis error, answer given for unanswerable question.

---

## Sprint 2: Table Store, Router, Summarize

**Goal:** Improve table handling, test whether routing helps, and add the first new feature.

### Tasks

- Add a structured table store alongside the graph.
- Add the Jev router: tags, relevance scores, confidence fallbacks (never drop documents). Keep thresholds and fallbacks in code, separate from the model client.
- Add summarize as a fixed-template prompt on top of Q&A (problem, method, results, or a generic document template).
- Add more messy and non-academic PDFs to the golden set.
- Compare against the Sprint 1 baseline.

### Tools

|Purpose|Tool|
|---|---|
|Table storage|SQL store (SQLite or Postgres)|
|Routing|Jev (pin a specific model version, not the latest alias)|
|Summarize|Prompt template over existing pipeline|
|Evaluation|Existing eval harness, extended|

### Expected outcome

- Table question accuracy improves over baseline.
- Router beats the no-router baseline on cost, time, or accuracy. If it does not, remove it.
- Summaries work on papers and non-paper documents.

---

## Sprint 3: Research Loop, Extract, Isolation

**Goal:** Replace the single call with a multi-agent loop, add extraction, and make the system safe for multiple users.

### Tasks

- Build the LangGraph state graph: clarify, brief, supervisor, parallel researchers, writer.
- Give researchers Cognee retrieval and table store query as tools.
- Add compression of findings inside each researcher, a hard cap on supervisor iterations, and the context budget step.
- Add extract: user-defined fields pulled into a structured table across documents, with structured output and its own eval questions.
- Add per-user or per-workspace isolation (one Cognee dataset each) and isolation tests.
- Add upload size limits and per-user quotas, based on the cost per document from Sprint 1.
- Add cross-document questions to the golden set.

### Tools

|Purpose|Tool|
|---|---|
|Orchestration|LangGraph|
|Model calls, tools, structured output|LangChain|
|Token counting|tiktoken|
|Retrieval|Cognee (wrapped as a thin tool)|
|Isolation|Cognee datasets, backend checks|

### Expected outcome

- Measurable gain over the single-call baseline, especially on cross-document questions.
- The loop always terminates.
- Extract returns correct structured fields on a test set.
- Tests confirm one user cannot retrieve another user's content.

---

## Sprint 4: Web App, Deployment, Observability

**Goal:** A deployed app with quality gates.

### Tasks

- Build the frontend with upload, chat, summarize, and extract views, plus token streaming.
- Complete auth (login UI, sessions) on top of the Sprint 3 isolation, and add the job queue.
- Containerize with Docker and set up CI/CD.
- Add Langfuse tracing for latency, tokens, and time to first token.
- Run the golden-set eval in CI as a regression gate.
- Deploy to a cloud host.

### Tools

|Purpose|Tool|
|---|---|
|Frontend|Next.js|
|Backend|FastAPI|
|Containers|Docker|
|CI/CD|GitHub Actions|
|Tracing|Langfuse|
|Hosting|Cloud host (TBD)|

### Expected outcome

- Live app where a user signs in, uploads PDFs, and gets streamed, cited answers, summaries, and extractions.
- CI fails a merge if golden-set scores drop.
- Traces available for every run.

---

## Later, Optional

- **Related documents** inside the user's library (nearest-neighbor query over graph and vectors).
- **External search fallback:** opt-in, used only when retrieval confidence is low, always labeled "external source". Candidate sources: arXiv API, Semantic Scholar API.
- **Vision model** for charts and diagrams that OCR cannot interpret.

---

## Summary

|Sprint|Focus|Exit criterion|
|---|---|---|
|1|Baseline with text, tables, images, and golden set|Baseline scores recorded|
|2|Table store, router, summarize|Router beats the baseline, or it is cut|
|3|Research loop, extract, isolation and quotas|Gain over single-call, isolation tests pass|
|4|Web app, deploy, observability|Deployed app with a regression gate|