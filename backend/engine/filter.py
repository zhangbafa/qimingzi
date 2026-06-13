from database.lexicon import Lexicon
from engine.models import GenerationConfig
from utils import unpack_json


def filter_chars(lexicon: Lexicon, config: GenerationConfig) -> list[str]:
    chars = lexicon.all_chars

    # Exclude negative words
    chars = [c for c in chars if not lexicon.is_negative(c.char)]

    # Exclude user-specified chars
    if config.exclude_chars:
        exclude_set = set(config.exclude_chars)
        chars = [c for c in chars if c.char not in exclude_set]

    # Filter by category for person names: prefer core chars
    if config.name_type == "person":
        core_chars = [c for c in chars if c.category == "core"]
        if len(core_chars) >= 100:
            chars = core_chars

    # Filter by gender (relaxed - include neutral chars too)
    if config.gender != "N":
        chars = [c for c in chars if c.gender in (config.gender, "N")]

    # Filter by style preference (relaxed - keep 30% minimum)
    if config.style:
        style_set = set(config.style)
        styled = [
            c for c in chars
            if any(s in style_set for s in unpack_json(c.vibe))
        ]
        if len(styled) >= 50:
            chars = styled

    return [c.char for c in chars]


def filter_compounds(lexicon: Lexicon, config: GenerationConfig) -> list[str]:
    compounds = lexicon.all_compounds

    if config.industry:
        ind_set = set(config.industry)
        compounds = [
            c for c in compounds
            if any(s in ind_set for s in unpack_json(c.industry))
        ]

    if config.style:
        style_set = set(config.style)
        compounds = [
            c for c in compounds
            if any(s in style_set for s in unpack_json(c.vibe))
        ]

    compounds.sort(key=lambda x: x.weight, reverse=True)
    return [c.text for c in compounds]
