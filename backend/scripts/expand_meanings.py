#!/usr/bin/env python3
"""Analyze missing meanings and output them for the developer to add."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import aiosqlite
from database.lexicon import BUILTIN_MEANINGS, _gb2312_level1, _gb2312_level2


async def find_gaps():
    db_path = Path(__file__).parent.parent / "data" / "lexicon.db"

    async with aiosqlite.connect(str(db_path)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT char, meaning FROM chars ORDER BY id")
        rows = await cursor.fetchall()

    chars_with_meaning = []
    chars_without_meaning = []

    for row in rows:
        ch = row["char"]
        meaning = row["meaning"] or ""
        if meaning:
            chars_with_meaning.append(ch)
        else:
            chars_without_meaning.append(ch)

    print(f"Total chars in DB: {len(rows)}")
    print(f"With meaning: {len(chars_with_meaning)} ({len(chars_with_meaning)/len(rows)*100:.1f}%)")
    print(f"Without meaning: {len(chars_without_meaning)} ({len(chars_without_meaning)/len(rows)*100:.1f}%)")
    print()

    # Show chars without meaning, grouped by GB2312 level
    all_l1 = _gb2312_level1()
    all_l2 = _gb2312_level2()
    l1_no = [c for c in chars_without_meaning if c in all_l1]
    l2_no = [c for c in chars_without_meaning if c not in all_l1]

    print(f"Missing L1 chars ({len(l1_no)}): {''.join(l1_no[:50])}{'...' if len(l1_no) > 50 else ''}")
    print(f"Missing L2 chars ({len(l2_no)}): {''.join(l2_no[:50])}{'...' if len(l2_no) > 50 else ''}")
    print()

    # Check name_worthy chars status
    name_worthy = set(
        "明华智慧轩瑞博雅诚信毅远志文德和谦恒达强伟杰凡卓越越新然思修齐安康"
        "宁静乐善美真行知学问言道理天地人心云风月山海林川泽润清晨曦朗昭昱晟"
        "熠瑶瑾瑜玥琳璇琪帆航征程驰骋飞翔腾跃进启源源泉溪波澜浩瀚宇星辰光"
        "辉煌耀泰安怡悦怀恩惠慈慕敬正平顺昌盛兴荣富贵吉祥如意嘉良友君宇锋"
        "刚毅俊彦鹏程龙腾凤鸣春晖永延宏图景浩德泽沛然若予希欣宜家承佑启功业"
        "守成业勋伟力涛洁冰霜寒温暖柔曼妮娜婷姿娇媚媛嫣婵娟蓓蕾茜莹颖馥馨"
        "蕊薇萱芙莲萍茵菲萌菁岚峥嵘峡峰岩岸柏松桦楠桐梓彬栋梁枢机杞枝杏杉"
        "枫林森柏桦榆梅兰荷菊葵蕾芦苇蒲蓬蕙芷茗荇薇萧蔚茂荣荫蔚旻昊晟曜"
        "瑾瑜瑶琳琪璇玥珺环珑玦珂玺琮璞玮琦琳琅琊台瑾瑶晗"
        "舒予畅颂彰尚凯晋朗晨浩宇泰然景行唯初川禾冉昀"
        "谦颐祯祺禄禧靖佑安恪恒恺悌慈恢悦恪惟敦"
        "全联总主生元世国东军高名品实通阳群"
    )
    nw_in_db = [c for c in name_worthy if c in [r["char"] for r in rows]]
    nw_no_meaning = [c for c in nw_in_db if c not in chars_with_meaning]
    print(f"Name-worthy chars in DB: {len(nw_in_db)}")
    print(f"Name-worthy without meaning: {len(nw_no_meaning)}")
    if nw_no_meaning:
        print(f"  {''.join(nw_no_meaning)}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(find_gaps())
