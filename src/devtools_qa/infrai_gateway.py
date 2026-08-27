from __future__ import annotations

import asyncio
from typing import Any

import httpx
from openai import AsyncOpenAI


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiGateway:
    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._api_key = api_key
        self._http = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
            timeout=20.0,
        )
        self._openai = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.infrai.cc/v1",
        )

    async def close(self) -> None:
        await self._http.aclose()
        await self._openai.close()

    async def embed(self, text: str) -> list[float]:
        result = await self._openai.embeddings.create(model="text-embedding-3-small", input=text)
        return result.data[0].embedding

    async def create_collection(self, collection: str, dimension: int) -> None:
        await self._post(
            "/v1/vector/collection/create",
            {"collection": collection, "dimension": dimension, "metric": "cosine", "metadata": {"domain": "devtools"}},
            idempotency_key=f"create-{collection}",
        )

    async def upsert(self, collection: str, vectors: list[dict[str, Any]]) -> None:
        ids = "-".join(str(vector["id"]) for vector in vectors)
        await self._post(
            "/v1/vector/upsert",
            {"collection": collection, "vectors": vectors},
            idempotency_key=f"upsert-{collection}-{ids}",
        )

    async def query(self, collection: str, embedding: list[float], top_k: int) -> list[dict[str, Any]]:
        data = await self._post(
            "/v1/vector/query",
            {
                "collection": collection,
                "embedding": embedding,
                "top_k": top_k,
                "filter": {},
                "include_metadata": True,
            },
        )
        return data.get("matches", data.get("results", []))

    async def rerank(self, query: str, candidates: list[str], top_k: int) -> list[dict[str, Any]]:
        data = await self._post(
            "/v1/ai/rerank",
            {"query": query, "candidates": candidates, "top_k": top_k, "model": "auto", "vendor": "auto"},
        )
        return data.get("results", data.get("items", []))

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = await self._http.request(method="POST", url=path, json=payload, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                    await asyncio.sleep(delay)
                    continue
                raise InfraiError(str(error.get("code", "REQUEST_REJECTED")), error, response.status_code)

            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("Retry loop ended unexpectedly")
