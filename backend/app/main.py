"""EMEA Guard API entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from .config import get_settings
from .database import Base, SessionLocal, engine
from .routers import accounts, core, governance, reports

log = logging.getLogger("emea_guard")


def init_db() -> None:
    """Create the schema and seed synthetic data on first start."""
    from .models import Jurisdiction
    from .seed.generate import seed

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.execute(select(func.count()).select_from(Jurisdiction)).scalar_one() == 0 and get_settings().seed_on_startup:
            log.info("Empty database: seeding synthetic EMEA dataset")
            seed(db, get_settings().random_seed)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    s = get_settings()
    if not s.is_development and not s.email_configured:
        log.error("No email delivery configured (EMEA_GUARD_RESEND_API_KEY or EMEA_GUARD_SMTP_HOST): password resets cannot be delivered.")
    yield


settings = get_settings()
app = FastAPI(
    title="EMEA Guard API",
    version="1.0.0",
    description=(
        "Enterprise Data Governance & Regulatory Control Management Platform.\n\n"
        "Create an account with **POST /api/auth/register** (the first account becomes admin), then sign in "
        "with **POST /api/auth/login** or the Authorize button. Passwords are stored as bcrypt hashes; "
        "password resets use single-use emailed tokens.\n\n"
        "**All data is synthetic.** Regulatory content is a simplified model for demonstration, not legal advice."
    ),
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
for r in (accounts.router, core.router, governance.router, reports.router):
    app.include_router(r, prefix="/api")


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "emea-guard"}
