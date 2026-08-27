from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class SearchGateway(Protocol):
    async def embed(self, text: str) -> list[float]:
        """Create an embedding for one question."""

    async def query(self, collection: str, embedding: list[float], top_k: int) -> list[dict]:
        """Retrieve document passages by vector similarity."""

    async def rerank(self, query: str, candidates: list[str], top_k: int) -> list[dict]:
        """Order candidate passages for the original question."""


@dataclass(frozen=True)
class DocumentAnswer:
    answer: str
    document_id: str
    event_type: str


class QuestionService:
    def __init__(self, gateway: SearchGateway, collection: str = "devtools-documents") -> None:
        self._gateway = gateway
        self._collection = collection

    async def answer(self, question: str) -> DocumentAnswer | None:
        embedding = await self._gateway.embed(question)
        matches = await self._gateway.query(self._collection, embedding, top_k=8)
        passages = [match.get("metadata", {}).get("text", "") for match in matches]
        passages = [passage for passage in passages if passage]
        if not passages:
            return None

        ranked = await self._gateway.rerank(question, passages, top_k=1)
        if not ranked:
            return None
        winner = ranked[0]
        index = int(winner.get("index", 0))
        if index < 0 or index >= len(passages):
            return None
        answer = passages[index]
        source = next(match for match in matches if match.get("metadata", {}).get("text") == answer)
        metadata = source.get("metadata", {})
        return DocumentAnswer(
            answer=answer,
            document_id=str(metadata.get("document_id", source.get("id", "unknown"))),
            event_type=str(metadata.get("event_type", "diagnostic")),
        )
