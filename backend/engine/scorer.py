import re
from functools import lru_cache

from pypinyin import pinyin, Style as PyStyle

from database.lexicon import Lexicon
from engine.models import GenerationConfig, DimensionScores
from utils import unpack_json, PINYIN_PREFERRED

_POSITIVE_WORDS = frozenset([
    "美好", "光明", "智慧", "吉祥", "高尚", "优雅",
    "希望", "兴盛", "广阔", "卓越", "成功", "勇敢",
])

# Cache positive word hits per character meaning to avoid repeated string scan
@lru_cache(maxsize=10000)
def _char_meaning_score(meaning: str) -> float:
    score = 0.5
    for pw in _POSITIVE_WORDS:
        if pw in meaning:
            score += 0.1
    if "不吉" in meaning or "消极" in meaning or "负面" in meaning:
        score -= 0.3
    return min(1.0, max(0.0, score))


@lru_cache(maxsize=None)
def _get_pinyin_info(chars_tuple: tuple[str, ...]) -> tuple[tuple[int, ...], tuple[str, ...], tuple[str, ...]]:
    chars = list(chars_tuple)
    try:
        # Override multi-tone chars with preferred name-context pinyin
        preferred = {ch: PINYIN_PREFERRED.get(ch) for ch in chars}
        has_preferred = any(v is not None for v in preferred.values())

        if has_preferred:
            # Build a custom pinyin string for preferred chars
            tone3_list = []
            for ch in chars:
                if ch in PINYIN_PREFERRED:
                    tone3_list.append(PINYIN_PREFERRED[ch])
                else:
                    r = pinyin(ch, style=PyStyle.TONE3, heteronym=False)
                    tone3_list.append(r[0][0] if r and r[0] else "")
            joined_tone3 = " ".join(tone3_list)
        else:
            joined = "".join(chars)
            r1 = pinyin(joined, style=PyStyle.TONE3, heteronym=False)
            tone3_list = [r[0] if r else "" for r in r1]
            joined_tone3 = " ".join(tone3_list)

        # Parse tones from tone3 list
        tones: list[int] = []
        for t in tone3_list:
            m = re.search(r'[1-5]$', t)
            tones.append(int(m.group()) if m else 0)

        # Get initials/finals via pypinyin
        if has_preferred:
            initials = []
            finals = []
            for ch in chars:
                r_i = pinyin(ch, style=PyStyle.INITIALS, heteronym=False)
                initials.append(r_i[0][0] if r_i and r_i[0] else "")
                r_f = pinyin(ch, style=PyStyle.FINALS, heteronym=False)
                finals.append(r_f[0][0] if r_f and r_f[0] else "")
        else:
            r2 = pinyin(joined, style=PyStyle.INITIALS, heteronym=False)
            initials = [r[0] if r else "" for r in r2]
            r3 = pinyin(joined, style=PyStyle.FINALS, heteronym=False)
            finals = [r[0] if r else "" for r in r3]

        return tuple(tones), tuple(initials), tuple(finals)
    except Exception:
        n = len(chars)
        return (0,) * n, ("",) * n, ("",) * n


class Scorer:
    def __init__(self, lexicon: Lexicon):
        self.lexicon = lexicon

    def score(self, name: str, config: GenerationConfig) -> DimensionScores:
        chars = list(name)
        d = DimensionScores()
        d.meaning = self._score_meaning(chars)
        d.tone = self._score_tone(chars)
        d.style = self._score_style(chars, config)
        d.readability = self._score_readability(chars)
        d.length = self._score_length(chars, config)
        d.repeat = self._score_repeat(chars)

        negative_count = sum(1 for ch in chars if self.lexicon.is_negative(ch))
        if negative_count > 0:
            penalty = 0.5 * negative_count
            d.meaning = max(0.0, d.meaning - penalty)
            d.readability = max(0.0, d.readability - penalty * 0.5)

        return d

    def total(self, dims: DimensionScores) -> float:
        weights = {
            "meaning": 0.20,
            "tone": 0.20,
            "style": 0.15,
            "readability": 0.15,
            "length": 0.10,
            "repeat": 0.10,
            "ai": 0.10,
        }
        total = sum(getattr(dims, k) * v for k, v in weights.items())

        basic = [dims.meaning, dims.tone, dims.readability]
        if any(b < 0.2 for b in basic):
            total = min(total, 0.30)

        return round(total * 100, 1)

    def _score_meaning(self, chars: list[str]) -> float:
        if not chars:
            return 0.0

        scores = []
        for ch in chars:
            entry = self.lexicon.get_char(ch)
            if entry is None or not entry.meaning:
                scores.append(0.5)
                continue
            scores.append(_char_meaning_score(entry.meaning))

        char_mean = sum(scores) / len(scores)

        name_str = "".join(chars)
        compound = self.lexicon.get_compound(name_str)
        compound_score = char_mean
        if compound and compound.weight > 0.5:
            compound_score = min(1.0, compound.weight + 0.2)

        return round(char_mean * 0.8 + compound_score * 0.2, 4)

    def _score_tone(self, chars: list[str]) -> float:
        if len(chars) < 2:
            return 0.7

        tones, initials, finals = _get_pinyin_info(tuple(chars))

        score = 0.7

        tone_changes = sum(1 for i in range(len(tones) - 1)
                           if tones[i] != tones[i + 1])
        max_changes = len(tones) - 1
        variation_ratio = tone_changes / max_changes if max_changes > 0 else 1.0
        score += 0.15 * variation_ratio

        rep_penalty = 0
        seen_initials = set()
        for i in initials:
            if i in seen_initials:
                rep_penalty += 0.05
            seen_initials.add(i)

        seen_finals = set()
        for f in finals:
            if f in seen_finals:
                rep_penalty += 0.05
            seen_finals.add(f)

        score -= rep_penalty

        if tones and tones[-1] in (1, 2):
            score += 0.05

        return round(max(0.0, min(1.0, score)), 4)

    def _score_style(self, chars: list[str],
                     config: GenerationConfig) -> float:
        if not config.style:
            return 1.0

        target = set(config.style)
        if not target:
            return 1.0

        matched = 0
        total = 0
        for ch in chars:
            entry = self.lexicon.get_char(ch)
            if entry is None:
                continue
            vibes = unpack_json(entry.vibe)
            matched += sum(1 for v in vibes if v in target)
            total += 1

        if total == 0:
            return 0.5

        ratio = matched / total

        name_str = "".join(chars)
        compound = self.lexicon.get_compound(name_str)
        if compound:
            cw_vibes = unpack_json(compound.vibe)
            if any(v in target for v in cw_vibes):
                ratio = min(1.0, ratio + 0.2)

        return round(min(1.0, max(0.0, ratio)), 4)

    def _score_readability(self, chars: list[str]) -> float:
        if not chars:
            return 0.0

        freq_scores = []
        stroke_penalty = 0.0
        for ch in chars:
            entry = self.lexicon.get_char(ch)
            if entry is None:
                freq_scores.append(0.3)
                continue
            freq_scores.append(entry.frequency)

            if entry.stroke_count > 25:
                stroke_penalty = max(stroke_penalty, 0.2)
            if entry.stroke_count > 30:
                stroke_penalty = max(stroke_penalty, 0.5)

        avg_freq = sum(freq_scores) / len(freq_scores)
        complexity_score = self._estimate_complexity(chars)

        score = avg_freq * 0.7 - stroke_penalty + 0.3 * complexity_score
        return round(max(0.0, min(1.0, score)), 4)

    def _score_length(self, chars: list[str],
                      config: GenerationConfig) -> float:
        n = len(chars)
        if config.name_type == "person":
            if n == 2:
                return 0.9
            if n == 3:
                return 1.0
            if n == 4:
                return 0.7
            return 0.3
        if config.name_type in ("company", "brand"):
            if n == 2:
                return 0.8
            if 3 <= n <= 4:
                return 1.0
            if 5 <= n <= 6:
                return 0.7
            return 0.4
        if config.name_type == "product":
            if 2 <= n <= 3:
                return 1.0
            if 4 <= n <= 5:
                return 0.7
            return 0.4
        return 0.7

    def _score_repeat(self, chars: list[str]) -> float:
        counts = {}
        for ch in chars:
            counts[ch] = counts.get(ch, 0) + 1

        max_repeat = max(counts.values()) if counts else 0
        if max_repeat >= 4:
            return 0.0
        if max_repeat == 3:
            return 0.2
        if max_repeat == 2:
            return 0.5
        return 1.0

    def _estimate_complexity(self, chars: list[str]) -> float:
        total_complexity = 0.0
        for ch in chars:
            entry = self.lexicon.get_char(ch)
            if entry is None:
                total_complexity += 0.5
            else:
                total_complexity += max(0.0, 1.0 - entry.stroke_count / 30)
        return total_complexity / len(chars) if chars else 0.5
