import math
import random
import re
import time
from functools import lru_cache

from pypinyin import pinyin, Style as PyStyle

from database.lexicon import Lexicon
from engine.filter import filter_chars, filter_compounds
from engine.models import GenerationConfig, NameCandidate, DimensionScores
from engine.scorer import Scorer
from utils import unpack_json, NAME_WORTHY


def _name_chars_similarity(a: list[str], b: list[str]) -> float:
    """Jaccard similarity on character sets."""
    set_a, set_b = set(a), set(b)
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def _mmr_select(
    scored: list[tuple[str, list[str], list[str], DimensionScores, float]],
    count: int,
    lambda_param: float = 0.7,
) -> list[tuple[str, list[str], list[str], DimensionScores, float]]:
    """Maximal Marginal Relevance selection for diversity."""
    if not scored or count >= len(scored):
        return scored

    selected: list = [scored[0]]
    candidates = list(scored[1:])

    while len(selected) < count and candidates:
        best_idx = -1
        best_score = -math.inf
        for i, (name, chars, py, dims, total) in enumerate(candidates):
            relevance = total
            max_sim = max(
                _name_chars_similarity(chars, s_chars)
                for _, s_chars, _, _, _ in selected
            )
            mmr = lambda_param * (relevance / 100.0) - (1 - lambda_param) * max_sim
            if mmr > best_score:
                best_score = mmr
                best_idx = i
        if best_idx >= 0:
            selected.append(candidates.pop(best_idx))
        else:
            break
    return selected


class NameGenerator:
    def __init__(self, lexicon: Lexicon):
        self.lexicon = lexicon
        self.scorer = Scorer(lexicon)

    def generate(self, config: GenerationConfig) -> tuple[list[NameCandidate], dict]:
        start = time.time()

        valid_chars = filter_chars(self.lexicon, config)
        if not valid_chars:
            return [], {"total_candidates": 0, "generation_ms": 0}

        candidates: list[tuple[str, list[str], list[str]]] = []

        if config.name_type == "person":
            candidates = self._generate_person_names(valid_chars, config)
        elif config.name_type == "company":
            candidates = self._generate_company_names(valid_chars, config)
        else:
            candidates = self._generate_generic_names(valid_chars, config)

        scored = []
        for name, chars_list, pinyins in candidates:
            dims = self.scorer.score(name, config)
            total = self.scorer.total(dims)
            scored.append((name, chars_list, pinyins, dims, total))

        scored.sort(key=lambda x: x[4], reverse=True)

        # Apply MMR for diverse Top N
        selected = _mmr_select(scored, config.count)

        result = []
        for name, chars_list, pinyins, dims, total in selected:
            result.append(NameCandidate(
                name=name,
                chars=chars_list,
                pinyin=pinyins,
                score=total,
                dimensions=dims,
            ))

        elapsed = int((time.time() - start) * 1000)
        meta = {
            "total_candidates": len(scored),
            "generation_ms": elapsed,
            "ai_ms": 0,
        }

        return result, meta

    def _generate_person_names(
        self, valid_chars: list[str], config: GenerationConfig,
    ) -> list[tuple[str, list[str], list[str]]]:
        candidates = []
        seen_names = set()
        surname = config.surname if config.surname else ""

        target_count = config.count * 20
        weighted = self._weight_chars(tuple(valid_chars), config)
        total_weight = sum(weighted.values())

        attempts = 0
        max_attempts = max(target_count * 10, 500)
        while len(candidates) < target_count and attempts < max_attempts:
            attempts += 1
            given_len = config.length or random.choices(
                [1, 2, 3], weights=[0.3, 0.6, 0.1]
            )[0]

            selected = self._random_select(weighted, total_weight, given_len)
            if len(selected) < given_len:
                continue

            name = surname + "".join(selected)
            if name in seen_names:
                continue
            seen_names.add(name)

            pinyins = self._get_pinyins(list(name))
            candidates.append((name, list(name), pinyins))

        return candidates

    def _generate_company_names(
        self, valid_chars: list[str], config: GenerationConfig,
    ) -> list[tuple[str, list[str], list[str]]]:
        candidates = []
        seen_names = set()
        compounds = filter_compounds(self.lexicon, config)

        if not compounds:
            return self._generate_generic_names(valid_chars, config)

        target_count = config.count * 20
        attempts = 0
        max_attempts = target_count * 5

        while len(candidates) < target_count and attempts < max_attempts:
            attempts += 1
            prefix = random.choice(compounds) if random.random() < 0.7 else ""
            core = "".join(random.choices(valid_chars, k=2))
            suffix = random.choice(compounds) if random.random() < 0.5 else ""

            if prefix and suffix:
                name = prefix + suffix
            elif prefix:
                name = prefix + core[:2]
            elif suffix:
                name = core[:2] + suffix
            else:
                name = core[:2]

            if len(name) < 2:
                name = name + random.choice(valid_chars)

            if not _is_company_name_valid(name):
                continue

            if name in seen_names:
                continue
            seen_names.add(name)

            pinyins = self._get_pinyins(list(name))
            candidates.append((name, list(name), pinyins))

        return candidates

    def _generate_generic_names(
        self, valid_chars: list[str], config: GenerationConfig,
    ) -> list[tuple[str, list[str], list[str]]]:
        candidates = []
        target_count = config.count * 20
        weighted = self._weight_chars(tuple(valid_chars), config)
        total_weight = sum(weighted.values())

        for _ in range(target_count):
            length = config.length or random.choices(
                [2, 3, 4], weights=[0.4, 0.4, 0.2]
            )[0]

            selected = self._random_select(weighted, total_weight, length)
            if len(selected) < length:
                continue

            name = "".join(selected)
            pinyins = self._get_pinyins(selected)
            candidates.append((name, selected, pinyins))

        return candidates

    def _weight_chars(
        self, chars_tuple: tuple[str, ...], config: GenerationConfig,
    ) -> dict[str, float]:
        # Build a hashable cache key (Pydantic v2 models with list fields are not hashable)
        style_key = tuple(sorted(config.style)) if config.style else ()
        gender = config.gender
        cache_key = (chars_tuple, style_key, gender)
        return self._weight_chars_impl(cache_key)

    @lru_cache(maxsize=128)
    def _weight_chars_impl(
        self, cache_key: tuple,
    ) -> dict[str, float]:
        chars_tuple, style, gender = cache_key
        chars = list(chars_tuple)
        weights: dict[str, float] = {}
        for ch in chars:
            entry = self.lexicon.get_char(ch)
            if entry is None:
                weights[ch] = 0.3 if ch in NAME_WORTHY else 0.01
                continue

            w = entry.name_score

            if ch in NAME_WORTHY:
                w = max(w, 0.5) * 2.0
            else:
                w *= 0.3

            if style:
                vibes = unpack_json(entry.vibe)
                if any(s in vibes for s in style):
                    w *= 1.3

            if gender != "N" and entry.gender == gender:
                w *= 1.2

            if entry.stroke_count > 20:
                w *= 0.8

            weights[ch] = max(0.01, w)

        return weights

    @staticmethod
    def _random_select(weights: dict[str, float], total: float,
                       k: int) -> list[str]:
        if not weights or total <= 0:
            return []
        chars = list(weights.keys())
        probs = [weights[c] / total for c in chars]
        try:
            selected = random.choices(chars, weights=probs, k=k)
        except (ValueError, ZeroDivisionError):
            selected = random.choices(chars, k=k)
        return selected

    @staticmethod
    def _get_pinyins(chars: list[str]) -> list[str]:
        try:
            result = pinyin("".join(chars), style=PyStyle.TONE3, heteronym=False)
            return [r[0] if r else "" for r in result]
        except Exception:
            return [""] * len(chars)


def _is_company_name_valid(name: str) -> bool:
    """Check basic semantic validity of a generated company name."""
    if len(name) < 2:
        return False

    counts: dict[str, int] = {}
    for ch in name:
        counts[ch] = counts.get(ch, 0) + 1
    if max(counts.values()) >= 3:
        return False

    if len(name) >= 3:
        try:
            r = pinyin(name, style=PyStyle.TONE3, heteronym=False)
            tones = []
            for r0 in r:
                if r0:
                    m = re.search(r'[1-5]$', r0[0])
                    tones.append(int(m.group()) if m else 0)
            if len(tones) >= 3 and len(set(tones[:3])) == 1:
                return False
        except Exception:
            pass

    return True
