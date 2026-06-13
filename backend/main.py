import asyncio
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.generate import set_lexicon, router as generate_router
from config import settings
from database.lexicon import Lexicon, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine, session_factory = await init_db()
    async with session_factory() as session:
        lexicon = Lexicon(session)
        await lexicon.load()
        set_lexicon(lexicon)
        app.state.lexicon = lexicon
        app.state.db_engine = engine
    yield
    await engine.dispose()


logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    colorize=True,
)
logger.add(
    "logs/qiming_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {name}:{function}:{line} - {message}",
    level="INFO",
)

app = FastAPI(
    title="起名系统 API",
    description="商业级智能起名系统后端",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate_router, prefix="/api/v1")


@app.get("/")
async def root():
    logger.info("Root endpoint accessed")
    return {"name": "起名系统", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting server on 0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
