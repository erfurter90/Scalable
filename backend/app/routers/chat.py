from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse, ChatStatusOut
from app.services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"], dependencies=[Depends(get_current_user)])


@router.get("/status", response_model=ChatStatusOut)
def status() -> ChatStatusOut:
    return ChatStatusOut(configured=chat_service.is_ai_configured())


@router.post("/message", response_model=ChatResponse)
@limiter.limit("10/minute")  # LLM calls cost money; keep abuse/runaway-loop risk low
def message(
    request: Request,
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    result = chat_service.answer_question(db, current_user.id, body.message)
    return ChatResponse(**result)
