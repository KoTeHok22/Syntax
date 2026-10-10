from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backend.models
from backend.api import router
from backend.core.config import get_settings
from backend.db import Base, engine, ensure_vector_extension


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_vector_extension(engine)
    Base.metadata.create_all(bind=engine)
    from backend.core.domain_seed import seed_domains
    from backend.db import SessionLocal

    db = SessionLocal()
    try:
        seed_domains(db)
        db.commit()
        from backend.models import Domain
        from backend.services.domain_index import index_domains

        await index_domains(db, db.query(Domain).all())
        db.commit()
    finally:
        db.close()
    if get_settings().seed_demo:
        from scripts.seed_demo import main as seed_demo_data

        seed_demo_data()
    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
