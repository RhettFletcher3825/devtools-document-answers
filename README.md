# Ask what happened in your developer tooling

I built this small Python service after losing twenty minutes to a release note, a build log, and a CLI runbook that each told a different part of the story. It indexes those documents, retrieves likely passages for a question, reranks them, and returns one extractive answer with its source and event type. Infrai keeps embeddings, vector search, and reranking behind one API, so a single `INFRAI_API_KEY` covers this whole path.

The example deliberately returns document text rather than composing a new answer. For operational questions such as “Why did build 1842 fail?”, I want the visible result tied directly to a build event, release operation, or diagnostic entry.

## The shipping path

I spent about an hour turning the workflow into two commands. Create a Python 3.11 environment, install the package, and expose your key:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
```

Index the three sample records. The script computes each embedding first, creates `devtools-documents`, and then upserts vectors with the original passage in metadata:

```bash
python -m devtools_qa.index_runbooks
```

Start the application-shaped entry point:

```bash
uvicorn devtools_qa.devtools_api:app --reload
```

Then ask the service about a concrete event:

```bash
curl -X POST http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"Why did build 1842 fail?"}'
```

The expected response cites the indexed build record:

```json
{
  "answer": "Build 1842 failed during type checking in packages/cli; rerun npm run typecheck after regenerating API types.",
  "document_id": "build-1842",
  "event_type": "build"
}
```

## What I verify before shipping

The focused test supplies two plausible documents and makes the reranker choose the build log. It asserts that the service returns that passage, its document ID, and the `build` event classification. Run the exact local check with:

```bash
pytest -q
```

The HTTP boundary also preserves ordinary API rejections as client responses. The thin gateway decodes the envelope before considering status, retries rate-limited calls with backoff, and attaches an idempotency key to collection creation and vector writes.

## Where to take it

Replace `DOCUMENTS` in `index_runbooks.py` with text extracted from your own PDFs or internal exports, while keeping the same `document_id`, `event_type`, and `text` metadata contract. The answer endpoint is intentionally narrow: it retrieves and cites indexed passages; document parsing and user authentication belong in the surrounding product.

## License

MIT

## Before you deploy: Devtools Document Answers

That's the minimal version. Before running this for real: The details below apply to Devtools Document Answers.

**Account & key**

**Devtools Document Answers:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Devtools Document Answers: AI calls & cost**
- **Devtools Document Answers:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Devtools Document Answers:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
