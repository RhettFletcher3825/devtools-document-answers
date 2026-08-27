from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .infrai_gateway import InfraiError, InfraiGateway
from .question_service import QuestionService


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class AnswerResponse(BaseModel):
    answer: str
    document_id: str
    event_type: str


def build_service() -> tuple[InfraiGateway, QuestionService]:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise RuntimeError("Set INFRAI_API_KEY before starting the service")
    gateway = InfraiGateway(api_key)
    return gateway, QuestionService(gateway)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    gateway, service = build_service()
    app.state.gateway = gateway
    app.state.question_service = service
    yield
    await gateway.close()


app = FastAPI(title="Devtools document answers", lifespan=lifespan)


@app.post("/questions", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest) -> AnswerResponse:
    try:
        result = await app.state.question_service.answer(request.question)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail={"code": exc.code, "message": str(exc)}) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="No supporting document was found")
    return AnswerResponse(**result.__dict__)
