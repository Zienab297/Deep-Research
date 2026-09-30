Document Deep Research Platform

Upload your own PDFs (papers, reports, invoices, scans), build a knowledge graph over them, and get cited, streamed answers. Every component is added only if it beats the baseline on a golden dataset.

**Status:** Sprint 1 (MVP baseline) in progress. See [[Sprints Plan]] for the plan.

---

## Problem

People spend hours reading long PDFs and pulling facts, especially from tables and image-based pages. Keyword search and single-shot RAG miss cross-document links and often garble table data. This project answers questions across a personal document set with trustworthy, cited output, and says "not found" instead of guessing.

## Objectives

1. Upload PDFs and ask questions across them.
2. Return accurate, cited answers, including values from tables and images.
3. Reply "not found in your documents" when the answer is not there.
4. Measure quality on a golden dataset before adding any component.
5. Keep each user's documents isolated and per-document cost under control.

## Features

|Feature|Stage|
|---|---|
|Search and answer with citations|MVP|
|Summarize (fixed template)|Sprint 2|
|Extract user-defined fields into a table|Sprint 3|
|Per-user isolation and quotas|Sprint 3|
|Related documents in your library|Later, optional|
|External search fallback (opt-in, labeled)|Later, optional|

---

## MVP Pipeline

```
PDF -> Page Analyzer -> [PyMuPDF4LLM (text + tables) | OCR (images + scanned pages)] -> Merge by Page -> Markdown
    -> Cognee (add, cognify) -> retrieval -> GPT-4o (streamed answer or "not found") -> golden set score
```

PyMuPDF4LLM and OCR run side by side because most PDFs mix text pages with embedded images. OCR runs only on pages with images or little extractable text.

### In scope (MVP)

- PDF upload and ingestion (text, tables, images)
- Knowledge graph and retrieval through Cognee
- Single-call synthesis with streaming and a "not found" response
- API with upload and ask endpoints
- Golden dataset and scripted evaluation

### Out of scope (later sprints)

- Jev routing model, structured table store
- Summarize and extract
- Multi-agent research loop
- Auth, per-user isolation, quotas
- Web frontend and job queue
- Langfuse tracing and metrics
- Cloud deployment and CI/CD

---

## Planned Architecture

|Zone|Components|
|---|---|
|Ingestion|Page analyzer, PyMuPDF4LLM and OCR (Tesseract) in parallel, merge by page|
|Routing|Jev router (tags and scores, never drops documents)|
|Knowledge layer|Cognee (relational, vector, graph stores), table store|
|Deep research agent|Clarify, brief, supervisor, parallel researchers, context budget, streaming writer|
|Web app|Next.js frontend, FastAPI backend, auth, job queue|
|Evaluation and observability|Golden dataset, Langfuse tracing|

---

## Repo Layout

```
Deep-Research/
├── app/
│   ├── api/            # FastAPI backend
│   └── web/            # Next.js frontend
├── src/research/
│   ├── ingestion/
│   ├── routing/
│   ├── knowledge/
│   ├── agent/
│   ├── config.py
│   └── schemas.py
├── eval/
│   ├── golden/
│   ├── metrics/
│   └── run_eval.py
├── tests/
├── infra/
├── notebooks/
├── .env.example
└── pyproject.toml
```

Only the folders needed for the current sprint are built. The MVP currently uses a flat layout: `core.py`, `api.py`, `run_eval.py`.

---

## Setup

> To be filled in as the project develops.

### Prerequisites

- Python version: _TBD_
- API keys: _TBD_
- Tesseract installed: _TBD_

### Install

```bash
# TBD
```

### Environment variables

```bash
# TBD
```

---

## Running

> Add commands here as each piece works.

### Ingest documents

```bash
# TBD
```

### Start the API

```bash
# TBD
```

### Ask a question

```bash
# TBD
```

### Run the evaluation

```bash
# TBD
```

---

## Data

- **Test data:** arXiv subset, one narrow category, start with 10 PDFs. arXiv is test data, not the product scope.
- **Non-paper files:** at least one invoice, one report, one scanned document.
- **Sources:** arXiv API or OAI-PMH for PDFs (rate limited, check current terms, do not scrape). Kaggle arXiv metadata only to choose the subset.
- **Chosen category:** _TBD_
- **Golden set:** `eval/golden/questions.jsonl`, 15 to 20 questions covering single-document facts, table values, image-only values, cross-document comparisons, and no-answer questions.

---

## Evaluation

|Run|Date|Pipeline version|Score|Table score|Image score|No-answer score|Notes|
|---|---|---|---|---|---|---|---|
|Baseline|_TBD_|Sprint 1|_TBD_|_TBD_|_TBD_|_TBD_||

Failure causes are labeled per run: retrieval miss, table garbled, OCR error, synthesis error, or answer given for an unanswerable question.

---

## Process Log

> One line per meaningful step or decision, newest first.

- _TBD_

---

## Known Risks

|Risk|Mitigation|
|---|---|
|Cognify is slow and costly at scale|Start with 10 documents, extrapolate, cap count, add quotas|
|Tables garbled in markdown|Track table accuracy separately, add a table store in Sprint 2|
|OCR reads text in images but not charts|Note the limit, consider a vision model later|
|Cognee API changes between versions|Pin the version and inspect result shapes|
|Tuning only to academic papers|Include invoices, reports, and scans in the golden set|
|Answers guessed when nothing is found|Explicit "not found" rule and no-answer eval questions|
|Cross-user data leakage|Per-user datasets and isolation tests before any public launch|

---

## Roadmap

See [[Sprints Plan]].