import asyncio

from devtools_qa.question_service import QuestionService


class FakeGateway:
    async def embed(self, text: str) -> list[float]:
        return [0.2, 0.8]

    async def query(self, collection: str, embedding: list[float], top_k: int) -> list[dict]:
        return [
            {"id": "release-note", "metadata": {"document_id": "release-note", "event_type": "release", "text": "The release shipped Friday."}},
            {"id": "build-log", "metadata": {"document_id": "build-log", "event_type": "build", "text": "Build 1842 failed in type checking."}},
        ]

    async def rerank(self, query: str, candidates: list[str], top_k: int) -> list[dict]:
        assert query == "Why did build 1842 fail?"
        return [{"index": 1, "score": 0.97}]


def test_rerank_choice_becomes_the_cited_build_answer() -> None:
    result = asyncio.run(QuestionService(FakeGateway()).answer("Why did build 1842 fail?"))

    assert result is not None
    assert result.answer == "Build 1842 failed in type checking."
    assert result.document_id == "build-log"
    assert result.event_type == "build"
