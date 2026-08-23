"""FastAPI application factory: middleware, rate limiting, router mounting."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.routers import (
    auth,
    bitget,
    bitvavo,
    bitcoin_history,
    chat,
    coinbase,
    dashboard,
    financials,
    market_data,
    portfolio,
    score,
    transactions,
)

configure_logging()
settings = get_settings()

app = FastAPI(title="Finanz-Agent API", version="0.1.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(market_data.router)
app.include_router(financials.router)
app.include_router(portfolio.router)
app.include_router(score.router)
app.include_router(dashboard.router)
app.include_router(chat.router)
app.include_router(bitvavo.router)
app.include_router(bitget.router)
app.include_router(coinbase.router)
app.include_router(transactions.router)
app.include_router(bitcoin_history.router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
