from sqlalchemy import Column, String, Float, Integer, Text, JSON
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from config import settings


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Char(Base):
    __tablename__ = "chars"

    id: Mapped[int] = mapped_column(primary_key=True)
    char: Mapped[str] = mapped_column(String(4), unique=True, index=True)
    pinyin: Mapped[str] = mapped_column(Text, default="[]")
    meaning: Mapped[str] = mapped_column(Text, default="")
    frequency: Mapped[float] = mapped_column(Float, default=0.0)
    gender: Mapped[str] = mapped_column(String(4), default="N")
    vibe: Mapped[str] = mapped_column(Text, default="[]")
    category: Mapped[str] = mapped_column(String(16), default="core")
    name_score: Mapped[float] = mapped_column(Float, default=0.0)
    stroke_count: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(Text, default="[]")


class CompoundWord(Base):
    __tablename__ = "compound_words"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    word_type: Mapped[str] = mapped_column(String(16), default="core")
    industry: Mapped[str] = mapped_column(Text, default="[]")
    vibe: Mapped[str] = mapped_column(Text, default="[]")
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class NegativeWord(Base):
    __tablename__ = "negative_words"

    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    level: Mapped[str] = mapped_column(String(8), default="forbidden")


class Style(Base):
    __tablename__ = "styles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")


async def init_db(database_url: str | None = None):
    url = database_url or settings.database_url
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session
