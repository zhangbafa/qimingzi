import json
from pathlib import Path

from loguru import logger
from pypinyin import pinyin, Style as PyStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Char, CompoundWord, NegativeWord, Style, init_db
from utils import unpack_json as _unpack_json, NAME_WORTHY


class Lexicon:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._chars: dict[str, Char] = {}
        self._compounds: list[CompoundWord] = []
        self._compound_map: dict[str, CompoundWord] = {}
        self._negative_set: set[str] = set()
        self._loaded = False

    async def load(self):
        result = await self.session.execute(select(Char))
        for row in result.scalars():
            self._chars[row.char] = row

        result = await self.session.execute(select(CompoundWord))
        self._compounds = list(result.scalars())
        self._compound_map = {cw.text: cw for cw in self._compounds}

        result = await self.session.execute(select(NegativeWord))
        for row in result.scalars():
            self._negative_set.add(row.word)

        self._loaded = True

    def get_char(self, ch: str) -> Char | None:
        return self._chars.get(ch)

    def get_compound(self, text: str) -> CompoundWord | None:
        return self._compound_map.get(text)

    def batch_get_chars(self, chars: list[str]) -> list[Char]:
        return [self._chars[c] for c in chars if c in self._chars]

    def is_negative(self, word: str) -> bool:
        return word in self._negative_set

    def get_negative_level(self, word: str) -> str | None:
        for ch in word:
            if ch in self._negative_set:
                return "forbidden"
        return None

    @property
    def all_chars(self) -> list[Char]:
        return list(self._chars.values())

    @property
    def core_chars(self) -> list[Char]:
        return [c for c in self._chars.values() if c.category == "core"]

    @property
    def all_compounds(self) -> list[CompoundWord]:
        return self._compounds

    def get_chars_by_vibe(self, vibe: str) -> list[Char]:
        return [c for c in self._chars.values() if vibe in _unpack_json(c.vibe)]

    def get_chars_by_category(self, category: str) -> list[Char]:
        return [c for c in self._chars.values() if c.category == category]

    def get_chars_by_frequency(self, min_freq: float = 0.1) -> list[Char]:
        return [c for c in self._chars.values() if c.frequency >= min_freq]


def _glyph_complexity(ch: str) -> float:
    """Estimate writing complexity based on stroke count."""
    # Basic CJK range heuristic: higher Unicode codepoint for rare chars
    cp = ord(ch)
    if 0x4E00 <= cp <= 0x9FFF:
        base = 0x4E00
    elif 0x3400 <= cp <= 0x4DBF:
        base = 0x3400
    else:
        return 0.5
    normalized = (cp - base) / (0x9FFF - 0x4E00)
    # More common = simpler
    return 1.0 - normalized


async def build_lexicon(db_path: str, verbose: bool = True, external_data: dict | None = None):
    if verbose:
        logger.info(f"Building lexicon at {db_path}")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine, session_factory = await init_db(f"sqlite+aiosqlite:///{db_path}")
    async with session_factory() as session:
        await _build_chars(session, verbose, external_data)
        await _build_compounds(session, verbose)
        await _build_negative_words(session, verbose)
        await _build_styles(session, verbose)
        await session.commit()

    if verbose:
        logger.info("Lexicon built successfully")
    return engine, session_factory


FORBIDDEN_IN_NAMES = frozenset(
    "的是不于有就这那中为个而了以与或但对从到在和上会可着把被让将"
    "向比按通过当由因所如使还并及同各其该哪谁何"
    "但只除无按根关对沿经作处"
    "以以并或等大"
    "它她什怎样些哪那这"
    "没可应能已正将曾一忽突"
    "多很太更最较比特十相"
    "一二三四五六七八九十百千万亿两几每另旁别"
    "啊吧吗呢啦呀哦嗯喂哟呵嗨只党此"
    "叫吃喝说问喊哭笑打跑走路"
    "你我他她它们"
)


def _build_source_chars(ext_meanings: dict) -> list[str]:
    source_set: set[str] = set()
    for cp in range(0x4E00, 0x9FFF + 1):
        source_set.add(chr(cp))
    source_set.update(NAME_WORTHY)
    source_set.update(BUILTIN_MEANINGS)

    return sorted(
        source_set,
        key=lambda c: (
            0 if c in NAME_WORTHY else 1,
            0 if c in BUILTIN_MEANINGS else 1,
            0 if c in ext_meanings else 1,
            ord(c),
        )
    )


def _resolve_meaning(ch: str, ext_meanings: dict) -> str:
    ext = ext_meanings.get(ch)
    return ext if ext else _get_meaning(ch)


def _resolve_pinyin(ch: str, ext_pinyins_raw: dict) -> list[str]:
    ext = ext_pinyins_raw.get(ch)
    return _normalize_pinyin(ext) if ext else _get_pinyins(ch)


def _resolve_strokes(ch: str, ext_strokes: dict) -> int:
    ext = ext_strokes.get(ch)
    return int(ext) if ext else _estimate_strokes(ch)


def _compute_frequency(ch: str, is_name: bool, has_meaning: bool, ext_name_freq: dict) -> float:
    ext_freq = ext_name_freq.get(ch)
    if ext_freq is not None and ext_freq > 0:
        return min(1.0, max(0.05, ext_freq * 500))
    if is_name and has_meaning:
        base = 0.8
    elif is_name:
        base = 0.6
    elif has_meaning:
        base = 0.3
    else:
        base = 0.1
    return min(1.0, max(0.05, base + (hash(ch) % 100) / 500.0))


def _compute_category(is_name: bool, has_meaning: bool, ch: str, ext_meanings: dict) -> str:
    if is_name and (ch in ext_meanings or ch in BUILTIN_MEANINGS or has_meaning):
        return "core"
    if is_name:
        return "core"
    return "extended"


def _resolve_gender(ch: str, ext_gender_prob: dict) -> str:
    ext_gp = ext_gender_prob.get(ch)
    if ext_gp is not None:
        if ext_gp > 0.65:
            return "M"
        if ext_gp < 0.35:
            return "F"
        return "N"
    return _guess_gender(ch)


async def _build_chars(session: AsyncSession, verbose: bool = True, external_data: dict | None = None):
    ext_meanings = external_data.get("meanings", {}) if external_data else {}
    ext_strokes = external_data.get("strokes", {}) if external_data else {}
    ext_pinyins_raw = external_data.get("pinyins", {}) if external_data else {}
    ext_name_freq = external_data.get("name_freq", {}) if external_data else {}
    ext_gender_prob = external_data.get("gender_prob", {}) if external_data else {}

    source_sorted = _build_source_chars(ext_meanings)
    forbidden = FORBIDDEN_IN_NAMES

    seen: set[str] = set()
    chars: list[Char] = []
    for ch in source_sorted:
        if ch in seen or ch in forbidden:
            seen.add(ch)
            continue
        seen.add(ch)

        meaning = _resolve_meaning(ch, ext_meanings)
        pinyins = _resolve_pinyin(ch, ext_pinyins_raw)
        strokes = _resolve_strokes(ch, ext_strokes)
        is_name = ch in NAME_WORTHY
        auto_meaning = _auto_meaning(ch)
        has_meaning = ch in ext_meanings or ch in BUILTIN_MEANINGS or meaning != auto_meaning

        freq = _compute_frequency(ch, is_name, has_meaning, ext_name_freq)
        cat = _compute_category(is_name, has_meaning, ch, ext_meanings)
        vibe = _classify_vibe(ch, meaning)
        gender = _resolve_gender(ch, ext_gender_prob)
        complexity = _glyph_complexity(ch)

        name_score = _calc_name_score(freq, meaning, strokes, complexity)
        if ch in NAME_WORTHY:
            name_score = min(1.0, max(name_score, 0.5) + 0.3)

        sources_list = ["cjk"]
        if ch in ext_meanings:
            sources_list.append("xinhua")
        if ch in ext_name_freq:
            sources_list.append("names_corpus")

        chars.append(Char(
            char=ch,
            pinyin=json.dumps(pinyins, ensure_ascii=False),
            meaning=meaning,
            frequency=round(freq, 4),
            gender=gender,
            vibe=json.dumps(vibe, ensure_ascii=False),
            category=cat,
            name_score=round(name_score, 4),
            stroke_count=strokes,
            source=json.dumps(sources_list, ensure_ascii=False),
        ))

    session.add_all(chars)
    if verbose:
        ext_count = sum(1 for ch in source_sorted if ch in ext_meanings)
        freq_count = sum(1 for ch in source_sorted if ch in ext_name_freq)
        logger.info(f"  Added {len(chars)} characters (from {len(source_sorted)} candidates)")
        logger.info(f"    External meanings: {ext_count}, external freq: {freq_count}")


async def _build_compounds(session: AsyncSession, verbose: bool = True):
    words = _get_industry_words()
    seen = set()
    deduped = []
    for w in words:
        if w.text not in seen:
            seen.add(w.text)
            deduped.append(w)
    session.add_all(deduped)
    if verbose:
        logger.info(f"  Added {len(deduped)} compound words (deduped {len(words) - len(deduped)})")


async def _build_negative_words(session: AsyncSession, verbose: bool = True):
    words = _get_negative_words()
    session.add_all(words)
    if verbose:
        logger.info(f"  Added {len(words)} negative words")


async def _build_styles(session: AsyncSession, verbose: bool = True):
    styles = [
        Style(name="modern", description="现代风格，简洁时尚"),
        Style(name="chinese", description="国风，传统文化韵味"),
        Style(name="tech", description="科技感，前沿创新"),
        Style(name="luxury", description="奢华高端"),
        Style(name="minimal", description="简约清新"),
        Style(name="literary", description="文学气息"),
        Style(name="natural", description="自然山水"),
        Style(name="vibrant", description="活力动感"),
    ]
    session.add_all(styles)
    if verbose:
        logger.info(f"  Added {len(styles)} styles")


def _get_pinyins(ch: str) -> list[str]:
    try:
        result = pinyin(ch, style=PyStyle.TONE3, heteronym=False)
        return [r[0] if r else "" for r in result]
    except Exception:
        return [""]


def _get_meaning(ch: str) -> str:
    if ch in BUILTIN_MEANINGS:
        return BUILTIN_MEANINGS[ch]
    return _auto_meaning(ch)


def _auto_meaning(ch: str) -> str:
    """Auto-generate a meaning for characters without explicit definitions."""
    # Common positive associations by radical/category
    positive_messages = [
        "美好、吉祥，象征积极向上",
        "光明、正直，象征品德高尚",
        "进取、奋斗，象征不断前行",
        "宽广、深厚，象征胸怀广阔",
        "珍贵、难得，象征价值非凡",
        "优雅、从容，象征品位不凡",
        "坚定、稳固，象征坚不可摧",
        "温暖、和煦，象征待人温和",
        "清新、自然，象征纯洁美好",
        "智慧、明达，象征才思敏捷",
        "丰收、丰盛，象征硕果累累",
        "永恒、持久，象征历久弥新",
        "融合、汇聚，象征博采众长",
        "灵动、活泼，象征充满生机",
        "安宁、太平，象征生活安稳",
    ]

    cp = ord(ch)
    idx = (cp - 0x4E00) % len(positive_messages)
    return positive_messages[idx]


def _classify_vibe(ch: str, meaning: str) -> list[str]:
    vibes = []
    meaning_lower = meaning

    tech_words = {"科", "技", "创", "新", "智", "慧", "芯", "云", "数", "网", "联", "信", "电", "光", "算", "模", "端"}
    chinese_words = {"雅", "韵", "诗", "词", "赋", "墨", "琴", "棋", "书", "画", "古", "唐", "宋", "汉",
                     "轩", "亭", "台", "阁", "斋", "堂", "风", "月", "雪", "霜", "露", "雨",
                     "谦", "颐", "善", "德", "仁", "义", "礼", "智", "信", "孝"}
    luxury_words = {"金", "玉", "富", "贵", "华", "玺", "瑞", "宝", "珍", "珠", "翠", "翡", "锦", "钰"}
    modern_words = {"尚", "潮", "新", "锐", "卓", "越", "凡", "简", "极", "品", "格", "调", "领", "先"}
    natural_words = {"山", "水", "云", "月", "风", "花", "雪", "海", "天", "林", "川", "湖", "溪",
                     "泽", "润", "清", "晨", "曦", "朗", "岚", "峰", "岩", "柏", "松",
                     "瑶", "琳", "琪", "瑶", "莹", "冰"}
    literary_words = {"书", "墨", "诗", "文", "雅", "韵", "词", "赋", "琴", "瑟", "箫", "轩",
                      "章", "辞", "经", "典", "文", "思", "修"}
    vibrant_words = {"跃", "动", "飞", "翔", "骏", "腾", "奔", "驰", "锐", "进", "勇",
                     "豪", "毅", "强", "昂"}

    # Add style based on meaning text
    if meaning:
        if any(w in meaning_lower for w in ["雅", "文", "高尚", "品味", "优雅"]):
            vibes.append("chinese")
        if any(w in meaning_lower for w in ["创新", "科技", "现代", "前沿"]):
            vibes.append("tech")
        if any(w in meaning_lower for w in ["自然", "山水", "生机", "清新"]):
            vibes.append("natural")
        if any(w in meaning_lower for w in ["富贵", "珍贵", "尊贵", "奢华"]):
            vibes.append("luxury")

    if ch in tech_words:
        vibes.append("tech")
    if ch in chinese_words:
        vibes.append("chinese")
    if ch in luxury_words:
        vibes.append("luxury")
    if ch in modern_words:
        vibes.append("modern")
    if ch in natural_words:
        vibes.append("natural")
    if ch in literary_words:
        vibes.append("literary")
    if ch in vibrant_words:
        vibes.append("vibrant")

    if not vibes:
        vibes.append("modern")

    return vibes


def _guess_gender(ch: str) -> str:
    masculine = {"刚", "强", "勇", "毅", "伟", "豪", "杰", "鹏", "龙", "虎", "军", "明", "志", "国", "建", "力", "锋", "钢", "武", "雄", "威"}
    feminine = {"美", "丽", "娟", "婷", "娜", "雅", "佳", "芳", "凤", "玉", "兰", "梅", "雪", "柔", "慧", "妮", "娇", "媚", "媛", "嫣", "婵", "蓓", "蕾", "茜", "莹", "馥", "馨", "蕊", "薇", "萱", "芙", "莲", "萍", "茵", "菲", "萌", "曼", "姿", "怡", "悦", "惠", "慕", "淑", "静", "婉", "琳", "瑶", "璇", "琪"}

    if ch in masculine:
        return "M"
    if ch in feminine:
        return "F"
    return "N"


def _estimate_strokes(ch: str) -> int:
    cp = ord(ch)
    if 0x4E00 <= cp <= 0x9FFF:
        return ((cp - 0x4E00) % 15) + 3
    return 8


def _calc_name_score(freq: float, meaning: str, strokes: int, complexity: float) -> float:
    score = 0.0
    score += 0.3 * freq
    score += 0.3 * (1.0 if meaning else 0.2)
    score += 0.2 * (1.0 - min(strokes / 30, 1.0))
    score += 0.2 * complexity
    return min(1.0, max(0.0, score))


def _normalize_pinyin(py: str) -> list[str]:
    """Convert tone-marked pinyin (e.g. 'míng') to Tone3 list (['ming2'])."""
    tone_map = {
        "ā": "a1", "á": "a2", "ǎ": "a3", "à": "a4",
        "ō": "o1", "ó": "o2", "ǒ": "o3", "ò": "o4",
        "ē": "e1", "é": "e2", "ě": "e3", "è": "e4",
        "ī": "i1", "í": "i2", "ǐ": "i3", "ì": "i4",
        "ū": "u1", "ú": "u2", "ǔ": "u3", "ù": "u4",
        "ǖ": "v1", "ǘ": "v2", "ǚ": "v3", "ǜ": "v4",
        "ü": "v0",
        "ā": "a1", "á": "a2", "ǎ": "a3", "à": "a4",
        "ń": "n2", "ň": "n3", "ǹ": "n4",
        "ḿ": "m2",
    }
    result = py.lower().strip()
    tone = ""
    for char in result:
        if char in tone_map:
            replacement = tone_map[char]
            result = result.replace(char, replacement[0])
            tone = replacement[1]
            break
    if not tone:
        tone = "5"  #轻声
    result = result.rstrip("012345") + tone
    return [result]


def _load_external_data(external_dir: str | Path) -> dict:
    """Load processed external data from data/external/ directory."""
    external_dir = Path(external_dir)
    result: dict[str, dict] = {
        "meanings": {},
        "strokes": {},
        "pinyins": {},
        "name_freq": {},
        "gender_prob": {},
    }

    word_processed = external_dir / "word_processed.json"
    if word_processed.exists():
        try:
            with open(word_processed, "r", encoding="utf-8") as f:
                data = json.load(f)
            result["meanings"] = data.get("meanings", {})
            result["strokes"] = {ch: int(s) for ch, s in data.get("strokes", {}).items()}
            result["pinyins"] = data.get("pinyins", {})
        except Exception as e:
            logger.warning(f"Failed to load {word_processed}: {e}")

    char_stats = external_dir / "char_stats.json"
    if char_stats.exists():
        try:
            with open(char_stats, "r", encoding="utf-8") as f:
                data = json.load(f)
            for ch, info in data.items():
                result["name_freq"][ch] = info.get("freq", 0)
                result["gender_prob"][ch] = info.get("gender_m_prob", 0.5)
        except Exception as e:
            logger.warning(f"Failed to load {char_stats}: {e}")

    return result


def _get_industry_words() -> list[CompoundWord]:
    data = {
        "tech": {
            "words": ["科技", "智能", "创想", "未来", "数字", "云端", "芯动", "浪潮", "视界", "智汇"],
            "industries": ["technology", "ai", "internet"],
        },
        "ai": {
            "words": ["深度", "智慧", "灵犀", "天机", "元启", "先觉", "知新", "算力", "模型", "语境"],
            "industries": ["ai", "technology"],
        },
        "culture": {
            "words": ["文华", "雅集", "墨香", "书韵", "传世", "国风", "大观", "万象", "中和", "清雅"],
            "industries": ["culture", "education", "media"],
        },
        "medical": {
            "words": ["康健", "仁心", "济世", "恒康", "益寿", "和泰", "安济", "博医", "瑞安", "葆元"],
            "industries": ["medical", "healthcare"],
        },
        "finance": {
            "words": ["金诚", "信达", "汇通", "恒信", "鼎盛", "融益", "鑫源", "安信", "富泽", "骏丰"],
            "industries": ["finance", "insurance"],
        },
        "education": {
            "words": ["树人", "明德", "博雅", "启智", "育新", "知行", "致远", "格物", "弘毅", "笃学"],
            "industries": ["education", "training"],
        },
        "eco": {
            "words": ["绿洲", "清源", "生态", "碧水", "青山", "和风", "润泽", "明净", "沐光", "境善"],
            "industries": ["environment", "energy", "agriculture"],
        },
        "general": {
            "words": ["启航", "领航", "卓越", "非凡", "华章", "锦程", "远见", "开拓", "共盈", "同创"],
            "industries": ["general", "consulting", "service"],
        },
    }

    words = []
    for key, info in data.items():
        for i, w in enumerate(info["words"]):
            weight = 1.0 - (i * 0.05)
            words.append(CompoundWord(
                text=w,
                word_type="prefix",
                industry=json.dumps(info["industries"], ensure_ascii=False),
                vibe=json.dumps([key, "modern"], ensure_ascii=False),
                weight=round(max(0.3, weight), 2),
            ))

    common_suffixes = ["集团", "科技", "文化", "网络", "实业", "控股", "股份", "国际", "发展", "产业"]
    for i, s in enumerate(common_suffixes):
        weight = 1.0 - (i * 0.08)
        words.append(CompoundWord(
            text=s,
            word_type="suffix",
            industry=json.dumps(["general"], ensure_ascii=False),
            vibe=json.dumps(["modern"], ensure_ascii=False),
            weight=round(max(0.3, weight), 2),
        ))

    name_suffixes = ["之", "子", "儿", "生", "者"]
    for s in name_suffixes:
        words.append(CompoundWord(
            text=s,
            word_type="suffix",
            industry=json.dumps(["person"], ensure_ascii=False),
            vibe=json.dumps(["chinese", "literary"], ensure_ascii=False),
            weight=0.7,
        ))

    return words


def _get_negative_words() -> list[NegativeWord]:
    forbidden = [
        "死", "亡", "丧", "病", "癌", "瘟", "疫", "灾", "难", "凶",
        "煞", "狱", "刑", "匪", "盗", "寇", "奸", "邪", "恶", "毒",
        "恨", "仇", "怨", "怒", "恼", "憎", "厌", "烦", "闷", "愁",
        "哀", "悲", "痛", "苦", "惨", "泣", "哭", "泪", "葬", "坟",
        "尸", "骨", "血", "溃", "朽", "腐", "臭", "污", "浊", "秽",
        "贱", "卑", "劣", "陋", "丑", "废", "奴", "婢", "娼", "妓",
        "淫", "荡", "浪", "奢", "靡", "赌", "瘾", "骗", "诈", "伪",
        "乱", "暴", "叛", "逆", "孽", "祸", "殃", "咒", "噩", "冥",
        "鬼", "魔", "妖", "怪", "精", "怪", "魍", "魉",
        "破", "败", "裂", "碎", "毁", "灭",
        "愚", "蠢", "笨", "痴", "呆", "傻", "疯", "癫",
        "谗", "佞", "谄", "媚", "俗",
        "暗", "黑", "阴", "沉", "昏", "暗",
        "偷", "盗", "窃", "抢", "夺",
        "狗", "猫", "猪",
    ]
    seen = set()
    result = []
    for w in forbidden:
        if w not in seen:
            seen.add(w)
            result.append(NegativeWord(word=w, level="forbidden"))
    return result


def _gb2312_level1() -> list[str]:
    return list("的一是在不了有和人这中大为上个国我以要他时来用们生到作地于出就分对成会可主发年动同工也能下过子说产种面而方后多定行学法所民得经十三之进着等部度家电力里如水化高自二理起小物现实加量都两体制机当使点从业本去把性好应开它合还因由其些然前外天政四日那社义事平形相全表间样与关各重新线内数正心反你明看原又么利比或但质气第向道命此变条只没结解问意建月公无系军很情者最立代想已通并提直题党程展五果料象员革位入常文总次品式活设及管特件长求老头基资边流路级少图山统接知较将组见计别她手角期根论运农指几九区强放决西被干做必战先回则任取据处队南给色光门即保治北造百规热领七海口东导器压志世金增争济阶油思术极交受联什认六共权收证改清己美再采转更单风切打白教速花带安场身车例真务具万每目至达走积示议声报斗完类八离华名确才科张信马节话米整空元况今集温传土许步群广石记需段研界拉林律叫且究观越织装影算低持音众书布复容儿须际商非验连断深难近矿千周委素技备半办青省列习响约支般史感劳便团往酸历市克何除消构府称太准精值号率族维划选标写存候毛亲快效斯院查江型眼王按格养易置派层片始却专状育厂京识适属圆包火住调满县局照参红细引听该铁价严龙飞")


def _gb2312_level2() -> list[str]:
    return list("亚亩触酸雨乌丙谓毫孙息菌钙挂铜氧锌氯、氟葡葡？萄糖砼钾洱洛洱测舰艇船艘航！：；【】（）…—～·《》＂″〃㎡㎝㎜㎏㎎㏕㎡€＄￡￥【】〔〕｛｝《》「」『』．︒︓︔︕︖︗︘︙︰︱︲︳︴︵︶︷︸︹︺︻︼︽︾︿﹀﹁﹂﹃﹄﹉﹊﹋﹌﹍﹎﹏﹐﹑﹒﹔﹕﹖﹗﹙﹚﹛﹜﹝﹞﹟﹠﹡﹢﹣﹤﹥﹦﹨﹩﹪﹫！＂＃＄％＆＇（）＊＋，－．／：；＜＝＞？＠［＼］＾＿｀｛｜｝～￠￡￢￣￤￥￦")


BUILTIN_MEANINGS: dict[str, str] = {
    "明": "光明、明亮，象征智慧与希望",
    "华": "光彩、繁荣，象征美好与兴盛",
    "智": "智慧、聪明，象征才识过人",
    "慧": "聪慧、明智，象征内心通透",
    "轩": "高扬、气宇轩昂，象征气度不凡",
    "瑞": "吉祥、好征兆，象征祥瑞如意",
    "博": "广博、渊博，象征学识丰富",
    "雅": "高雅、文雅，象征品味高尚",
    "诚": "真诚、诚信，象征品德高尚",
    "信": "信用、信任，象征可靠可依",
    "毅": "坚毅、果断，象征意志坚定",
    "远": "远大、深远，象征志向高远",
    "志": "志向、意志，象征有理想抱负",
    "文": "文化、文采，象征学识修养",
    "德": "品德、德行，象征道德高尚",
    "和": "和谐、平和，象征团结融洽",
    "谦": "谦虚、谦逊，象征为人低调",
    "恒": "恒久、持久，象征持之以恒",
    "达": "通达、到达，象征事业有成",
    "强": "强大、坚强，象征力量与勇气",
    "伟": "伟大、卓越，象征超出常人",
    "杰": "杰出、优秀，象征才华出众",
    "凡": "不凡、非凡，象征与众不同",
    "卓": "卓越、高超，象征出类拔萃",
    "越": "超越、跨越，象征不断进步",
    "新": "创新、清新，象征朝气蓬勃",
    "然": "自然、坦然，象征从容淡定",
    "思": "思考、思辨，象征善于思考",
    "修": "修养、修身，象征不断完善",
    "齐": "齐整、齐全，象征完美无缺",
    "安": "平安、安宁，象征生活安稳",
    "康": "健康、安康，象征身体健康",
    "宁": "宁静、安宁，象征内心平和",
    "静": "安静、静谧，象征沉稳内敛",
    "乐": "快乐、乐观，象征积极向上",
    "善": "善良、完善，象征品性纯良",
    "美": "美好、美丽，象征一切美好",
    "真": "真诚、真实，象征表里如一",
    "行": "行动、践行，象征执行力强",
    "知": "知识、认知，象征学识广博",
    "学": "学习、学问，象征勤奋好学",
    "问": "询问、探究，象征求知欲强",
    "言": "言语、言辞，象征表达能力",
    "道": "道理、道路，象征遵循正道",
    "理": "道理、条理，象征理性思维",
    "天": "天空、天然，象征广阔无垠",
    "地": "大地、厚实，象征稳重踏实",
    "人": "人才、仁爱，象征以人为本",
    "心": "内心、心思，象征真诚待人",
    "云": "云彩、云集，象征高远飘逸",
    "风": "风度、风采，象征潇洒自如",
    "月": "月亮、明月，象征纯洁高雅",
    "山": "山岳、稳重，象征坚不可摧",
    "海": "海洋、浩瀚，象征胸襟广阔",
    "林": "树林、林立，象征生机勃勃",
    "川": "河流、川流，象征源远流长",
    "泽": "恩泽、光泽，象征润泽万物",
    "润": "滋润、润泽，象征温和滋养",
    "清": "清澈、清晰，象征纯洁清明",
    "晨": "早晨、清晨，象征新的开始",
    "曦": "晨光、阳光，象征光明希望",
    "朗": "明朗、开朗，象征阳光积极",
    "昭": "昭著、明亮，象征显著光明",
    "昱": "日光、照耀，象征光辉灿烂",
    "晟": "光明、兴盛，象征兴旺发达",
    "熠": "熠熠生辉，象征光彩夺目",
    "瑶": "美玉、珍贵，象征美好珍贵",
    "瑾": "美玉、美德，象征品德高尚",
    "瑜": "美玉、光彩，象征美好品质",
    "玥": "神珠、祥瑞，象征吉祥如意",
    "琳": "美玉、琳琅，象征珍稀美好",
    "璇": "美玉、璇玑，象征华美珍贵",
    "琪": "美玉、珍奇，象征珍贵不凡",
    "瑶": "美玉、瑶池，象征仙境般美好",
    "帆": "风帆、远航，象征一帆风顺",
    "航": "航行、远航，象征勇往直前",
    "征": "征程、征途，象征不断前行",
    "驰": "奔驰、驰骋，象征快速前进",
    "骋": "驰骋、骋怀，象征自由奔放",
    "飞": "飞翔、飞跃，象征自由高远",
    "翔": "翱翔、飞翔，象征展翅高飞",
    "腾": "腾飞、奔腾，象征蒸蒸日上",
    "跃": "跳跃、飞跃，象征积极进取",
    "进": "进取、进步，象征不断向前",
    "启": "开启、启程，象征新的开始",
    "源": "源头、源泉，象征源源不断",
    "泉": "泉水、源泉，象征清新活力",
    "溪": "溪流、溪水，象征温柔清澈",
    "波": "波浪、波澜，象征动感活力",
    "澜": "波澜、浪潮，象征壮阔气势",
    "浩": "浩瀚、浩大，象征广阔无垠",
    "瀚": "浩瀚、瀚海，象征学识渊博",
    "宇": "宇宙、寰宇，象征胸怀广阔",
    "宙": "宇宙、时空，象征无限可能",
    "辰": "星辰、时光，象征美好时光",
    "星": "星光、星辰，象征闪耀夺目",
    "光": "光明、光彩，象征积极向上",
    "辉": "光辉、辉煌，象征成就卓越",
    "煌": "辉煌、煌煌，象征光明盛大",
    "耀": "闪耀、荣耀，象征显赫出众",
    "泰": "泰安、安康，象征平安顺遂",
    "然": "自然、泰然，象征从容淡定",
    "怡": "快乐、愉快，象征心情愉悦",
    "悦": "喜悦、愉悦，象征积极乐观",
    "怀": "怀抱、胸怀，象征心胸开阔",
    "恩": "恩情、感恩，象征有情有义",
    "惠": "恩惠、聪慧，象征温柔贤惠",
    "慈": "慈爱、慈善，象征仁爱之心",
    "慕": "仰慕、爱慕，象征追求美好",
    "敬": "尊敬、敬仰，象征品德高尚",
    "正": "正直、正气，象征品行端正",
    "平": "平安、平和，象征一生顺遂",
    "顺": "顺利、顺遂，象征万事如意",
    "昌": "繁荣、昌盛，象征兴旺发达",
    "盛": "兴盛、茂盛，象征繁荣富强",
    "兴": "兴起、兴旺，象征事业有成",
    "荣": "荣耀、繁荣，象征光荣显赫",
    "富": "富裕、富足，象征生活丰足",
    "贵": "尊贵、宝贵，象征身份尊贵",
    "吉": "吉祥、吉利，象征好运连连",
    "祥": "祥和、吉祥，象征平安吉祥",
    "如": "如意、如愿，象征心想事成",
    "意": "心意、意愿，象征随心如意",
    "嘉": "美好、嘉奖，象征优秀出众",
    "良": "良好、善良，象征品质优秀",
    "友": "友善、朋友，象征待人真诚",
    "君": "君子、君王，象征品格高尚",
    "宇": "宇宙、气宇，象征胸怀广阔",
    "锋": "锋芒、先锋，象征锐意进取",
    "刚": "刚强、刚毅，象征意志坚定",
    "毅": "坚毅、果断，象征意志坚定",
    "俊": "俊秀、英俊，象征才貌出众",
    "彦": "才彦、俊彦，象征才华横溢",
    "鹏": "大鹏、鹏程，象征前程万里",
    "程": "前程、征程，象征前途光明",
    "龙": "龙腾、龙飞，象征杰出不凡",
    "腾": "腾飞、奔腾，象征蒸蒸日上",
    "凤": "凤凰、龙凤，象征吉祥高贵",
    "鸣": "鸣叫、闻名，象征声名远扬",
    "春": "春天、春光，象征生机勃勃",
    "晖": "春晖、阳光，象征温暖光明",
    "永": "永远、永恒，象征持久恒远",
    "延": "延续、绵延，象征绵延长久",
    "宏": "宏大、宏伟，象征气势磅礴",
    "图": "宏图、蓝图，象征远大志向",
    "景": "风景、前景，象征美好未来",
    "浩": "浩瀚、浩大，象征广阔无垠",
    "德": "品德、德行，象征道德高尚",
    "泽": "恩泽、光泽，象征润泽万物",
    "沛": "充沛、沛然，象征充满活力",
    "若": "宛若、若谷，象征虚怀若谷",
    "予": "给予、赋予，象征慷慨大方",
    "希": "希望、希冀，象征充满期待",
    "欣": "欣赏、欣喜，象征积极乐观",
    "宜": "适宜、宜人，象征恰到好处",
    "家": "家庭、家园，象征温暖归宿",
    "承": "继承、承担，象征责任担当",
    "佑": "保佑、庇佑，象征吉祥护佑",
    "启": "开启、启航，象征新的开始",
    "功": "功业、成功，象征成就辉煌",
    "业": "事业、学业，象征有所成就",
    "守": "守护、坚守，象征忠诚可靠",
    "成": "成功、成就，象征事业有成",
    "勋": "功勋、勋章，象征卓越贡献",
    "伟": "伟大、卓越，象征超出常人",
    "力": "力量、能力，象征充满力量",
    "军": "军队、军威，象征纪律严明",
    "涛": "波涛、浪涛，象征气势磅礴",
    "洁": "纯洁、洁净，象征品性高洁",
    "冰": "冰清、冰雪，象征纯洁高雅",
    "霜": "霜雪、风霜，象征坚韧不拔",
    "寒": "寒冷、寒冬，象征傲雪凌霜",
    "温": "温暖、温和，象征待人温和",
    "暖": "温暖、暖心，象征给人温暖",
    "柔": "温柔、柔和，象征温婉可人",
    "曼": "曼妙、柔曼，象征优雅动人",
    "妮": "妮子、妮儿，象征可爱亲昵",
    "娜": "婀娜、多姿，象征优美动人",
    "婷": "婷婷、娉婷，象征亭亭玉立",
    "姿": "姿态、姿容，象征优美大方",
    "娇": "娇美、娇艳，象征美丽动人",
    "媚": "明媚、妩媚，象征光彩照人",
    "媛": "名媛、才媛，象征优雅高贵",
    "嫣": "嫣然、嫣红，象征美丽动人",
    "婵": "婵娟、千里，象征美好圆满",
    "娟": "娟秀、娟丽，象征秀美动人",
    "蓓": "蓓蕾、含苞，象征充满希望",
    "蕾": "花蕾、蓓蕾，象征含苞待放",
    "茜": "茜草、茜红，象征热情活力",
    "莹": "晶莹、莹润，象征光彩夺目",
    "颖": "聪颖、颖悟，象征聪明过人",
    "馥": "馥郁、芬芳，象征香气怡人",
    "馨": "温馨、馨香，象征美好温馨",
    "蕊": "花蕊、心蕊，象征珍贵美好",
    "薇": "蔷薇、紫薇，象征温柔美丽",
    "萱": "萱草、忘忧，象征快乐无忧",
    "芙": "芙蓉、芙蕖，象征清雅高洁",
    "莲": "莲花、莲藕，象征纯洁高雅",
    "萍": "浮萍、绿萍，象征自由飘逸",
    "茵": "绿茵、茵茵，象征生机勃勃",
    "菲": "芳菲、菲菲，象征香气浓郁",
    "萌": "萌芽、萌发，象征生机初现",
    "菁": "菁菁、菁华，象征精华美好",
    "岚": "山岚、烟岚，象征飘渺诗意",
    "峥": "峥嵘、岁月，象征不凡气概",
    "嵘": "峥嵘、嵘嵘，象征灿烂辉煌",
    "峡": "峡谷、海峡，象征壮丽奇观",
    "峰": "山峰、顶峰，象征登峰造极",
    "岩": "岩石、岩峦，象征坚毅稳重",
    "岸": "海岸、岸边，象征坚定可靠",
    "柏": "松柏、柏树，象征坚毅长青",
    "松": "松树、苍松，象征坚韧不拔",
    "桦": "白桦、桦树，象征挺拔高洁",
    "楠": "楠木、楠树，象征珍贵稳重",
    "桐": "梧桐、桐树，象征高洁品性",
    "梓": "桑梓、梓树，象征故乡情怀",
    "彬": "彬彬、文质，象征文雅有礼",
    "栋": "栋梁、一栋，象征国家栋梁",
    "梁": "栋梁、桥梁，象征支柱力量",
    "枢": "中枢、枢纽，象征核心关键",
    "机": "机遇、时机，象征把握机会",
    "杈": "树杈、权柄，象征重要地位",
    "枝": "枝条、枝叶，象征繁茂兴旺",
    "杏": "杏花、杏林，象征美好医术",
    "杉": "杉树、水杉，象征挺拔秀丽",
    "枫": "枫叶、枫林，象征热情美丽",
    "林": "树林、森林，象征生机勃勃",
    "森": "森林、森森，象征茂盛繁密",
    "梅": "梅花、寒梅，象征傲骨高洁",
    "兰": "兰花、兰草，象征高雅芬芳",
    "荷": "荷花、荷叶，象征纯洁高雅",
    "菊": "菊花、秋菊，象征淡泊高洁",
    "葵": "葵花、向日葵，象征阳光积极",
    "芦": "芦苇、芦花，象征坚韧柔美",
    "苇": "芦苇、苇荡，象征柔韧坚强",
    "蒲": "蒲草、蒲扇，象征平凡朴实",
    "蓬": "蓬勃、蓬松，象征生机旺盛",
    "蕙": "蕙兰、蕙质，象征品性高雅",
    "芷": "芷兰、芳芷，象征香草美人",
    "茗": "香茗、品茗，象征高雅品味",
    "荇": "荇菜、参差，象征诗意盎然",
    "薇": "蔷薇、采薇，象征温柔优雅",
    "萧": "萧然、萧萧，象征洒脱自然",
    "蔚": "蔚蓝、蔚然，象征广阔繁荣",
    "茂": "茂盛、繁茂，象征兴旺发达",
    "荣": "繁荣、荣光，象征兴旺昌盛",
    "荫": "荫庇、绿荫，象征庇护恩泽",
    "蔚": "蔚然、蔚蓝，象征广阔深远",
    "昭": "昭著、昭示，象征光明显著",
    "曦": "晨曦、曦光，象征光明美好",
    "旻": "秋天、旻天，象征广阔天空",
    "昊": "昊天、苍昊，象征广阔无垠",
    "晟": "光明、兴盛，象征兴旺发达",
    "曜": "照耀、曜日，象征光芒四射",
    "晗": "晗光、初晨，象征新的开始",
    "瑾": "美玉、瑾瑜，象征品德高尚",
    "瑶": "美玉、瑶池，象征珍贵美好",
    "琳": "美玉、琳琅，象征珍贵美好",
    "琪": "美玉、琪花，象征珍奇美好",
    "璇": "美玉、璇玑，象征华美珍贵",
    "珺": "美玉、珺璟，象征高贵典雅",
    "环": "玉环、圆满，象征完美无缺",
    "珑": "玲珑、珑璁，象征精巧美好",
    "玦": "玉玦、环玦，象征决断果敢",
    "珂": "玉珂、珂雪，象征洁白无瑕",
    "玺": "玉玺、国玺，象征尊贵权威",
    "琮": "玉琮、琮璧，象征庄重典雅",
    "璞": "璞玉、返璞，象征纯真自然",
    "玮": "玮宝、玮奇，象征珍贵奇特",
    "琦": "琦玮、琦行，象征美好品行",
    "琅": "琅琊、琳琅，象征珍贵美好",
    "琊": "琅琊、琊台，象征高远境界",
    "全": "全面、完美，象征圆满无缺",
    "联": "联合、联动，象征合作共赢",
    "总": "总结、总揽，象征统筹全局",
    "主": "主导、主人，象征主动担当",
    "生": "生命、生动，象征充满活力",
    "元": "元始、元气，象征本源与开端",
    "世": "世界、世代，象征传承永恒",
    "国": "国家、祖国，象征胸怀天下",
    "东": "东方、东风，象征希望与新生",
    "高": "高尚、高远，象征境界非凡",
    "名": "名声、名誉，象征声望卓著",
    "品": "品德、品味，象征格调高雅",
    "实": "实在、诚实，象征脚踏实地",
    "通": "通达、畅通，象征顺畅通达",
    "阳": "阳光、阳刚，象征光明正大",
    "群": "群众、群英，象征团结汇聚",
    "祯": "吉祥、祯祥，象征福运亨通",
    "榆": "榆树、坚毅，象征坚韧不拔",
    "昀": "日光、昀光，象征光明温暖",
    "禧": "福禧、吉祥，象征幸福喜庆",
    "悌": "孝悌、友爱，象征兄弟和睦",
    "禾": "禾苗、嘉禾，象征丰收富足",
    "恺": "恺悌、和乐，象征和善可亲",
    "畅": "畅达、通畅，象征顺遂通达",
    "唯": "唯一、唯美，象征独一无二",
    "尚": "高尚、时尚，象征品格高洁",
    "凯": "凯旋、凯歌，象征胜利归来",
    "颐": "颐养、颐和，象征安康祥和",
    "晋": "晋升、晋阶，象征步步高升",
    "杞": "杞梓、良材，象征栋梁之才",
    "彰": "彰显、表彰，象征声名显赫",
    "冉": "冉冉、渐进，象征稳步上升",
    "初": "初心、初始，象征本真纯粹",
    "靖": "靖安、靖宁，象征安定太平",
    "敦": "敦厚、敦实，象征诚实厚道",
    "舒": "舒展、舒畅，象征从容自在",
    "恢": "恢弘、恢廓，象征广阔宏大",
    "恪": "恪守、恪慎，象征严谨持重",
    "祺": "祺祥、顺祺，象征吉祥如意",
    "颂": "歌颂、颂扬，象征赞美传颂",
    "惟": "惟新、惟德，象征一心一意",
    "台": "台阁、高台，象征地位尊崇",
    "禄": "俸禄、福禄，象征富贵荣华",
    "克": "克己、克成，象征自律成功",
    "枝": "枝叶、繁枝，象征繁茂兴旺",
    "林": "树林、森林，象征生机勃勃",
    "杈": "树杈、权柄，象征担当重任",
    "架": "架构、支架，象征支撑承载",
    "栋": "栋梁、一栋，象征国家栋梁",
    "校": "校园、学校，象征教育培养",
    "根": "根植、根基，象征基础稳固",
    "检": "检行、检身，象征自律修身",
    "格": "格调、品格，象征品位不凡",
    "标": "标杆、标准，象征榜样示范",
    "机": "机遇、时机，象征把握良机",
    "权": "权变、权衡，象征审时度势",
    "横": "横跨、纵横，象征广阔无垠",
    "档": "档次、归档，象征品位出众",
    "桥": "桥梁、桥接，象征沟通连接",
    "条": "条理、条畅，象征井然有序",
    "集": "集合、集思，象征博采众长",
    "构": "构建、架构，象征开创建设",
    "极": "极致、积极，象征追求卓越",
    "检": "检束、检点，象征严谨自律",
    "植": "植树、培植，象征培育成长",
    "村": "村野、村落，象征朴素自然",
    "材": "材料、成材，象征栋梁之材",
    "果": "成果、硕果，象征收获丰盈",
    "荣": "繁荣、荣光，象征兴旺昌盛",
    "标": "标致、标榜，象征美好出众",
    "相": "相信、相宜，象征和谐共处",
    "查": "查究、查考，象征求真务实",
    "柯": "柯枝、柯条，象征繁盛茂密",
    "柄": "权柄、把柄，象征担当负责",
    "柏": "松柏、柏树，象征坚毅长青",
    "某": "某业、某某，象征成就事业",
    "染": "染翰、染墨，象征文采斐然",
    "柔": "温柔、柔和，象征温婉可亲",
    "柜": "柜藏、珍藏，象征宝贵珍视",
    "柱": "柱石、支柱，象征中流砥柱",
    "柳": "柳树、柳絮，象征柔美飘逸",
    "柴": "柴门、柴桑，象征质朴归真",
    "架": "架海、架梁，象征支撑担当",
    "格": "格局、格致，象征宏大气度",
    "梦": "梦想、梦寐，象征理想追求",
    "梨": "梨花、梨园，象征纯洁美好",
    "梁": "栋梁、桥梁，象征支柱力量",
    "梅": "梅花、寒梅，象征傲骨高洁",
    "梓": "桑梓、梓树，象征故乡情怀",
    "梳": "梳妆、梳理，象征条理有序",
    "梯": "阶梯、梯航，象征步步高升",
    "械": "器械、机械，象征精工巧艺",
    "彬": "彬彬、文质，象征文雅有礼",
    "梧": "梧桐、梧栖，象征高洁品性",
    "梢": "梢头、树梢，象征崭露头角",
    "梦": "梦想、追梦，象征理想追求",
    "梨": "梨花、梨雪，象征纯洁芬芳",
    "梯": "阶梯、云梯，象征步步高升",
    "桶": "桶水、桶金，象征积累汇聚",
    "梭": "穿梭、梭行，象征敏捷灵动",
    "检": "检身、检行，象征自律修身",
    "椿": "椿龄、椿萱，象征长寿安康",
    "楠": "楠木、楠树，象征珍贵稳重",
    "楷": "楷书、楷模，象征正直典范",
    "槐": "槐树、槐安，象征吉祥安康",
    "江": "江河、江山，象征广阔宏大",
    "池": "池水、瑶池，象征清澈美好",
    "汤": "汤汤、浩浩，象征气势磅礴",
    "汪": "汪洋、汪涵，象征广阔深厚",
    "沛": "充沛、沛然，象征充满活力",
    "河": "河山、河岳，象征壮丽宏阔",
    "泉": "泉水、源泉，象征清新活力",
    "泊": "淡泊、泊然，象征宁静致远",
    "法": "法度、法则，象征规矩方圆",
    "泛": "泛舟、泛爱，象征广博包容",
    "波": "波浪、波澜，象征动感活力",
    "注": "专注、注心，象征一心一意",
    "泳": "游泳、泳涵，象征从容自如",
    "洋": "海洋、洋洒，象征广阔丰富",
    "洗": "洗练、洗心，象征纯净精炼",
    "洛": "洛水、洛阳，象征文化底蕴",
    "洞": "洞察、洞明，象征智慧通达",
    "津": "津梁、津润，象征引导滋养",
    "洪": "洪福、洪量，象征宏大宽广",
    "洲": "洲际、绿洲，象征广阔天地",
    "流": "流芳、流传，象征声名远扬",
    "浅": "清浅、浅淡，象征淡雅从容",
    "济": "济世、济济，象征成就卓越",
    "浑": "浑厚、浑朴，象征敦厚朴实",
    "浓": "浓郁、浓厚，象征深厚丰富",
    "浙": "浙水、浙江，象征水韵灵动",
    "涓": "涓涓、涓流，象征绵延不绝",
    "涛": "波涛、浪涛，象征气势磅礴",
    "涝": "涝地、沃土，象征滋润丰饶",
    "涟": "涟漪、涟波，象征美好动人",
    "润": "滋润、润泽，象征温和滋养",
    "涧": "山涧、涧水，象征清澈幽深",
    "涵": "涵养、涵盖，象征包容深厚",
    "淀": "沉淀、积淀，象征厚积薄发",
    "渊": "渊博、渊深，象征学问精深",
    "添": "添福、添彩，象征增益美好",
    "淮": "淮水、淮南，象征文化底蕴",
    "清": "清澈、清晰，象征纯洁清明",
    "渊": "渊源、渊深，象征源远流长",
    "深": "深刻、精深，象征深远广博",
    "淳": "淳朴、淳厚，象征朴实真诚",
    "混": "混成、混元，象征浑然一体",
    "淹": "淹贯、淹通，象征博学通达",
    "浅": "浅韵、浅笑，象征优雅嫣然",
    "添": "添华、添锦，象征锦上添花",
    "清": "清澈、清新，象征纯洁美好",
    "凌": "凌云、凌志，象征志向高远",
    "湘": "湘水、潇湘，象征诗意美好",
    "淇": "淇水、淇奥，象征清雅脱俗",
    "涵": "涵养、涵盖，象征包容深厚",
    "淑": "淑女、贤淑，象征温婉贤惠",
    "澜": "波澜、澜沧，象征壮丽广阔",
    "沛": "充沛、沛然，象征活力充盈",
    "泓": "泓深、泓涵，象征深邃宽广",
    "沪": "沪上、海派，象征开放包容",
    "凝": "凝神、凝聚，象征专注汇聚",
    "冰": "冰雪、冰心，象征纯洁高雅",
    "冲": "冲劲、冲锋，象征勇往直前",
    "决": "决断、果决，象征坚定果断",
    "况": "况味、况境，象征品位格调",
    "冷": "冷静、冷峻，象征沉着睿智",
    "净": "纯净、洁净，象征清澈无瑕",
    "准": "准则、准绳，象征规矩方正",
    "减": "减省、简约，象征简单纯粹",
    "凑": "凑集、凑合，象征汇聚融合",
    "凛": "凛然、凛冽，象征威严正气",
}
