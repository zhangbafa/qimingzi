import asyncio
import time

from fastapi import APIRouter, Depends

from ai.deepseek import DeepSeekClient
from database.lexicon import Lexicon
from engine.generator import NameGenerator
from engine.models import GenerationConfig, GenerateResponse, NameCandidate

router = APIRouter()

_lexicon: Lexicon | None = None
_generator: NameGenerator | None = None
_ai_client: DeepSeekClient | None = None
_ai_semaphore = asyncio.Semaphore(3)


def set_lexicon(lexicon: Lexicon):
    global _lexicon, _generator, _ai_client
    _lexicon = lexicon
    _generator = NameGenerator(lexicon)
    _ai_client = DeepSeekClient()


def get_lexicon() -> Lexicon:
    assert _lexicon is not None, "Lexicon not initialized"
    return _lexicon


@router.post("/generate", response_model=GenerateResponse)
async def generate_names(
    config: GenerationConfig,
):
    assert _generator is not None
    assert _ai_client is not None

    names, meta = await asyncio.to_thread(_generator.generate, config)

    if config.with_ai and names:
        async def enrich(n: NameCandidate):
            async with _ai_semaphore:
                meaning = await _ai_client.name_meaning(
                    n.name, config.name_type, config.style
                )
                n.meaning = meaning or ""

        tasks = [enrich(n) for n in names[:10]]
        if tasks:
            start = time.time()
            await asyncio.gather(*tasks)
            meta["ai_ms"] = int((time.time() - start) * 1000)

    return GenerateResponse(names=names, meta=meta)
