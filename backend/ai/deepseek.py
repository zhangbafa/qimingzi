import asyncio
import random

import httpx

from config import settings

AI_SYSTEM_PROMPT = (
    "你是一位专业的中文起名专家，擅长根据汉字寓意、音韵和文化内涵"
    "为个人、公司或品牌提供名字解读。回答简洁优美，不超过100字。"
)

_MEANING_TEMPLATES = [
    "「{name}」中，{char_explains}组合起来寓意{meaning}，给人一种{feeling}的感觉。",
    "名字「{name}」取意{meaning}，{char_explains}，整体意境{feeling}。",
    "「{name}」——{char_explains}。寓意{meaning}，气质{feeling}。",
]

_CHAR_VIBES = {
    "modern": "简约时尚、现代感",
    "chinese": "古典雅致、文化底蕴",
    "tech": "科技前沿、创新活力",
    "luxury": "高贵典雅、奢华气质",
    "minimal": "清新简约、纯粹自然",
    "literary": "诗意盎然、文采飞扬",
    "natural": "自然清新、山水意境",
    "vibrant": "朝气蓬勃、活力四射",
}


def _fallback_meaning(name: str, name_type: str, style: list[str]) -> str:
    """Generate a rule-based name explanation as AI fallback."""
    style_key = style[0] if style else "modern"
    vibe_desc = _CHAR_VIBES.get(style_key, "独特气质")

    # Build simple char explanations
    char_explains = []
    for ch in name:
        meaning = _get_char_meaning(ch)
        char_explains.append(f"「{ch}」寓意{meaning}")
    char_explain_str = "，".join(char_explains)

    meaning_descs = {
        "person": "才华与品德兼具，前途光明",
        "company": "事业兴旺、宏图大展",
        "brand": "品质卓越、深入人心",
        "product": "匠心独具、实用美观",
    }
    meaning = meaning_descs.get(name_type, "美好吉祥")

    template = random.choice(_MEANING_TEMPLATES)
    return template.format(
        name=name,
        char_explains=char_explain_str,
        meaning=meaning,
        feeling=vibe_desc,
    )


def _get_char_meaning(ch: str) -> str:
    """Look up or infer a short meaning for a single character."""
    basic_meanings = {
        "明": "光明智慧", "华": "美好繁荣", "智": "聪明才智",
        "慧": "聪慧通达", "轩": "气宇轩昂", "瑞": "吉祥如意",
        "博": "广博深厚", "雅": "高雅脱俗", "诚": "真诚守信",
        "信": "可靠可信", "毅": "坚毅果敢", "远": "志向高远",
        "志": "理想抱负", "文": "学识修养", "德": "品德高尚",
        "和": "和谐融洽", "谦": "谦虚低调", "恒": "持之以恒",
        "达": "事业有成", "强": "坚强有力", "伟": "卓越伟大",
        "杰": "才华出众", "新": "创新进取", "思": "善于思考",
        "安": "平安顺遂", "康": "健康安康", "宁": "宁静平和",
        "乐": "快乐积极", "善": "善良美好", "美": "美丽优秀",
        "天": "广阔高远", "云": "飘逸高远", "风": "潇洒自如",
        "海": "胸怀广阔", "山": "稳重可靠", "星": "闪耀夺目",
        "光": "光明希望", "宇": "胸怀宽广", "辰": "美好时光",
        "春": "生机勃勃", "晨": "新的开始", "晴": "晴朗明媚",
        "洁": "纯洁高雅", "冰": "冰雪聪明", "雪": "纯洁无瑕",
        "婷": "亭亭玉立", "娜": "婀娜多姿", "娟": "秀美动人",
        "娇": "美丽动人", "嫣": "笑靥如花", "蕾": "含苞待放",
        "瑶": "珍贵美好", "琳": "珍贵琳琅", "琪": "珍奇不凡",
        "璇": "华美珍贵", "玥": "祥瑞之兆", "瑾": "品德高尚",
        "瑜": "美好品质", "帆": "一帆风顺", "航": "勇往直前",
        "鹏": "前程万里", "龙": "杰出不凡", "凤": "吉祥高贵",
        "飞": "自由高远", "翔": "展翅高飞", "腾": "蒸蒸日上",
    }
    return basic_meanings.get(ch, "美好吉祥")

NAME_MEANING_PROMPT = """
请为名字「{name}」提供一段中文解释：
1. 名字类型：{name_type}
2. 风格偏好：{style}
3. 每个字的寓意
4. 组合后的整体意境

要求：语言优美、积极正面、不超过100字。
"""

BRAND_STORY_PROMPT = """
请为品牌/公司名「{name}」写一段品牌故事（100~150字）：
行业：{industry}
品牌定位：{positioning}
包括品牌使命和愿景，语言有感染力。
"""

SLOGAN_PROMPT = """
请为品牌「{name}」（行业：{industry}）创作一句中文Slogan。
要求：简洁有力、朗朗上口、不超过15字。
"""


class DeepSeekClient:
    def __init__(self, api_key: str | None = None,
                 base_url: str | None = None,
                 model: str | None = None):
        self.api_key = api_key or settings.deepseek_api_key
        self.base_url = base_url or settings.deepseek_base_url
        self.model = model or settings.deepseek_model
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            )
        return self._client

    async def name_meaning(self, name: str, name_type: str,
                           style: list[str]) -> str:
        if not self.api_key:
            return _fallback_meaning(name, name_type, style)

        prompt = NAME_MEANING_PROMPT.format(
            name=name, name_type=name_type,
            style="、".join(style) if style else "通用"
        )
        result = await self._call(prompt)
        return result or _fallback_meaning(name, name_type, style)

    async def brand_story(self, name: str, industry: str,
                          positioning: str) -> str:
        prompt = BRAND_STORY_PROMPT.format(
            name=name, industry=industry, positioning=positioning
        )
        result = await self._call(prompt, system_prompt=AI_SYSTEM_PROMPT)
        return result or f"「{name}」品牌致力于{industry}领域的{positioning}，以卓越品质和创新精神服务客户。"

    async def slogan(self, name: str, industry: str) -> str:
        prompt = SLOGAN_PROMPT.format(name=name, industry=industry)
        result = await self._call(prompt, system_prompt=AI_SYSTEM_PROMPT)
        return result or f"{name}，{industry}之选"

    async def _call(self, prompt: str,
                    system_prompt: str | None = None,
                    max_retries: int = 2) -> str:
        client = await self._ensure_client()
        sys_prompt = system_prompt or AI_SYSTEM_PROMPT

        for attempt in range(max_retries + 1):
            try:
                response = await client.post("/chat/completions", json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                    "max_tokens": 300,
                }, headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                })

                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    return content.strip()
                elif response.status_code == 429:
                    if attempt < max_retries:
                        await self._rate_limit_wait(attempt)
                        continue
                    return ""
                else:
                    return ""

            except (httpx.TimeoutException, httpx.ConnectError):
                if attempt < max_retries:
                    await self._rate_limit_wait(attempt)
                    continue
                return ""

        return ""

    async def _rate_limit_wait(self, attempt: int):
        await asyncio.sleep(0.5 * (attempt + 1))

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
