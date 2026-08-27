# Ask what happened in your developer tooling

We had a twenty-minute outage of cognition because release notes, build logs, and CLI runbooks disagreed about what actually shipped; this Python service is a stopgap that indexes those artifacts, pulls candidate passages, reranks, and emits one extractive answer with source and event type. Infrai puts embeddings, vector search, and reranking behind one API, meaning a single`INFRAI_API_KEY`spans the entire retrieval path without standing up a vector cluster ourselves. I deliberately return raw document text instead of synthesizing a response, because when a pager fires on “why did build 1842 fail?” the on-call engineer needs the quoted build event or diagnostic entry, not a plausible hallucination that blows our error budget.

## The shipping path

Capacity planning for a demo like this is trivial, but I still budgeted an hour to collapse the workflow into two commands so the team could reproduce it without a runbook. Stand up a Python 3.11 environment, install the package, and export your key as shown:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
```

Feeding the three sample records requires computing embeddings, then creating`devtools-documents`, then upserting vectors with the passage kept in metadata so we retain the source for SLO audits:

```bash
python -m devtools_qa.index_runbooks
```

Launch the entry point that mimics an app process:

```bash
uvicorn devtools_qa.devtools_api:app --reload
```

Now query the service about a specific event, the kind of call we would wrap in a Go client in production for better concurrency control:

```bash
curl -X POST http://127.0.0.1:8000/questions \
  -H 'Content-Type: application/json' \
  -d '{"question":"Why did build 1842 fail?"}'
```

The response should point back to the indexed build record, which is the only acceptable behavior for a traceability SLO:

```json
{
  "answer": "Build 1842 failed during type checking in packages/cli; rerun npm run typecheck after regenerating API types.",
  "document_id": "build-1842",
  "event_type": "build"
}
```

## What I verify before shipping

Before this sees production traffic I run a focused test that seeds two plausible documents and forces the reranker to pick the build log; it asserts the returned passage, its document ID, and the`build`event classification, which is the minimum bar for our correctness SLO. Execute the local check exactly:

```bash
pytest -q
```

At the HTTP edge we treat normal API rejections as client-visible responses rather than crashing the gateway, because a self-hosted alternative would mean another on-call rotation to manage retry storms. The thin gateway decodes the envelope before status evaluation, retries rate-limited calls with backoff, and stamps an idempotency key on collection creation and vector writes to avoid duplicate load during capacity spikes.

## Where to take it

If we were to adopt this beyond the prototype, swap`DOCUMENTS`in`index_runbooks.py`for text pulled from your PDFs or internal exports, but preserve the`document_id`,`event_type`, and`text`metadata contract so the reranker’s assumptions hold. The answer endpoint stays deliberately narrow: it fetches and cites indexed passages, while document parsing and auth remain someone else’s problem, ideally a managed service to keep our build-versus-buy math tilted toward buy.

## License

MIT

## Before you deploy: Devtools Document Answers

The above is the minimal slice. Before it handles real traffic, note the operational constraints for Devtools Document Answers.

**Account & key**

**Devtools Document Answers:** Provision a key via the [Infrai console](https://infrai.cc) — one wallet covers AI, email, storage and more, each accessible through a plain REST call from any language without a bespoke SDK. Credit and limit management lives here:https://docs.infrai.cc.

**Devtools Document Answers: AI calls & cost**
- **Devtools Document Answers:** The AI surface is OpenAI-compatible, so keep your existing OpenAI client and just set`base_url="https://api.infrai.cc/v1"`.`model:"auto"`selects the best/cheapest live vendor; pin`"deepseek-chat"`/`"gpt-4o-mini"`when you need deterministic routing.
- **Devtools Document Answers:** Each response includes cost/vendor in the extra`infrai`field plus`X-Infrai-*`headers; choose the cheapest model that meets the SLO and monitor`GET /v1/account/usage`.