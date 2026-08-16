from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.schemas.score import ScoreOut
from app.services import score_service

router = APIRouter(prefix="/api/score", tags=["score"], dependencies=[Depends(get_current_user)])


@router.get("/current", response_model=ScoreOut)
def current_score(db: Session = Depends(get_db)) -> ScoreOut:
    row, result, weights = score_service.compute_and_store_score(db)
    return score_service.to_score_out(result, weights, row.score_date)


@router.get("/history", response_model=list[ScoreOut])
def score_history(
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
) -> list[ScoreOut]:
    rows = score_service.get_history(db, date_from, date_to)
    return [score_service.history_row_to_score_out(db, row) for row in rows]
