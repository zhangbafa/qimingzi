import json

# Characters frequently used in Chinese names, curated for positive meaning and aesthetic
NAME_WORTHY = frozenset(
    "明华智慧轩瑞博雅诚信毅远志文德和谦恒达强伟杰凡卓越越新然思修齐安康"
    "宁静乐善美真行知学问言道理天地人心云风月山海林川泽润清晨曦朗昭昱晟"
    "熠瑶瑾瑜玥琳璇琪帆航征程驰骋飞翔腾跃进启源源泉溪波澜浩瀚宇星辰光"
    "辉煌泰安怡悦怀恩惠慈慕敬正平顺昌盛兴荣富贵吉祥如意嘉良友君宇锋"
    "刚毅俊彦鹏程龙腾凤鸣春晖永延宏图景浩德泽沛若予希欣宜家承佑启功业"
    "守成勋伟力涛洁冰霜寒温暖柔曼妮娜婷姿娇媚媛嫣婵娟蓓蕾茜莹颖馥馨"
    "蕊薇萱芙莲萍茵菲萌菁岚峥嵘峰岩岸柏松桦楠桐梓彬栋梁枢机杈枝杏杉"
    "枫梅兰荷菊葵蕙芷茗萧蔚茂荫旻昊晟曜"
    "瑾瑜瑶琳琪璇玥珺环珑珂玺璞玮琦琅"
    "舒畅颂彰尚凯晋朗浩泰景唯初川禾冉昀"
    "谦颐祯祺禄禧靖佑恪恺悌敦"
    "全联总主生元世国东高军名品实通阳群"
    "凌梦涵凌淳湘淇涵淑澜沛泓沪江池汤汪沛河泉泊波"
    "泳洋洋洛津洪洲流济浑淳清凌凝冰雪冲冷静净凛"
    "柯枝林果根植材柏柳柴梦梨梅梓梧梢椿楠楷槐"
)


# Preferred pinyin for multi-tone chars in name context (tone3 format)
PINYIN_PREFERRED: dict[str, str] = {
    "行": "xing2", "乐": "le4", "长": "chang2", "朝": "zhao1",
    "重": "zhong4", "为": "wei2", "便": "bian4", "还": "hai2",
    "都": "du1", "只": "zhi3", "好": "hao3", "少": "shao3",
    "教": "jiao4", "相": "xiang1", "的": "di2", "了": "liao3",
    "着": "zhe1", "什": "shen2", "得": "de2", "和": "he2",
    "与": "yu3", "中": "zhong1", "传": "chuan2", "调": "tiao2",
    "率": "shuai4", "量": "liang2", "宁": "ning2", "奇": "qi2",
    "区": "qu1", "曲": "qu3", "任": "ren4", "散": "san4",
    "弹": "tan2", "卡": "ka3", "空": "kong1", "陆": "lu4",
    "埋": "mai2", "脉": "mai4", "模": "mo2", "难": "nan2",
    "漂": "piao1", "铺": "pu1", "强": "qiang2", "切": "qie4",
    "亲": "qin1", "兴": "xing1", "应": "ying1", "藏": "cang2",
    "曾": "zeng1", "石": "shi2", "华": "hua2", "几": "ji3",
    "尽": "jin4", "卷": "juan3", "看": "kan4", "落": "luo4",
    "没": "mei2", "蒙": "meng2", "秘": "mi4", "摩": "mo2",
    "泊": "bo2", "叶": "ye4", "正": "zheng4", "识": "shi2",
    "术": "shu4", "数": "shu4", "系": "xi4", "校": "xiao4",
    "血": "xue4", "饮": "yin3", "约": "yue1", "涨": "zhang3",
}


def unpack_json(val: str | list) -> list:
    if isinstance(val, list):
        return val
    try:
        return json.loads(val) if val else []
    except (json.JSONDecodeError, TypeError):
        return []
