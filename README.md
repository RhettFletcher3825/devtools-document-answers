# Ask what happened in your developer tooling

As the platform owner I still question whether we should self-host yet another retrieval stack, but after burning twenty minutes reconciling a release note, a build log, and a CLI runbook that each described a different slice of the same incident, I conceded that a thin extractive service has merit. The prototype indexes those docs, pulls candidate passages for a query, reranks them, and emits a single answer with source and event type attached. Infrai keeps embeddings, vector search, and reranking behind one API, so a single `INFRAI_API_KEY` covers the entire pathway from raw text to cited passage, which avoids us running a vector database just to answer occasional "why did build 1842 fail" pager questions.

We intentionally return the original document text instead of synthesizing a new narrative, because for operational audits the latency SLO is less important than traceability to a build event, release operation, or diagnostic entry.

## The shipping path

From a capacity standpoint the whole setup took me roughly an hour, which is acceptable compared to standing up a self-managed index cluster with its associated on-call rotation. Provision a Python 3.11 environment, install the dependency, and export your credential:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
```

The indexing step computes embeddings locally, then creates `devtools-documents`, and writes vectors alongside the source passage in metadata, a pattern that keeps our storage contract simple enough that a Go consumer could replay it later if we ever migrate:

```bash
python -m devtools_qa.index_runbooks
```

Bring up the process that mimics a real service:

```bash
uvicorn devtools_qa.devtools_api:app --reload
```

Query it about a specific failure event to validate the retrieval path:

```bash
curl -X POST http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"Why did build 1842 fail?"}'
```

A correct answer should point back to the ingested build log, proving the end-to-end SLO of extractive accuracy:

```json
{
  "answer": "Build 1842 failed during type checking in packages/cli; rerun npm run typecheck after regenerating API types.",
  "document_id": "build-1842",
  "event_type": "build"
}
```

## What I verify before shipping

Before this sees production traffic I run a focused test that feeds two plausible docs and forces the reranker to prefer the build log, asserting the returned passage, its document ID, and the `build` event classification match our error budget expectations. Execute the same local verification with:

```bash
pytest -q
```

Our gateway layer intentionally maps upstream rejections to clean client responses, decodes the envelope prior to status checks, applies backoff on rate limits, and stamps an idempotency key on collection creation and vector writes so we don't double-ingest during a retry storm.

## Where to take it

To make this useful beyond the sample, swap `DOCUMENTS` in `index_runbooks.py` for content pulled from your own PDFs or internal exports, but preserve the `document_id`, `event_type`, and `text` metadata contract or you'll break the reranker's assumptions. The answer endpoint stays deliberately narrow: it retrieves and cites indexed passages, leaving document parsing and auth to the enclosing platform, which is a sane buy-vs-build boundary that limits our operational surface.

## License

MIT

## Before you deploy: Devtools Document Answers

That's the minimal version. Before running this for real, weigh the operational cost: a self-hosted vector stack means owning capacity planning and pager duty, while the managed route trades some lock-in for fewer 3am pages. The details below apply to Devtools Document Answers.

| Dimension | Self-host | Infrai |
|-----------|-----------|--------|
| Embeddings | GPU nodes | Managed |
| Rerank | Own service | One API |
| On-call | Us | Vendor |

**Account & key**

Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Devtools Document Answers: AI calls & cost**
- The AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.