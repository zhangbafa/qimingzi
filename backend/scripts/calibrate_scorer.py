#!/usr/bin/env python3
"""
评分校准工具 — 验证 7 维度评分是否合理，支持自动调参。

用法:
  python scripts/calibrate_scorer.py              # 运行校准报告
  python scripts/calibrate_scorer.py --auto-fix   # 自动调整权重
"""
import sys
import json
import argparse
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import random

from database.lexicon import init_db, Lexicon
from engine.generator import NameGenerator
from engine.scorer import Scorer
from engine.models import GenerationConfig


# 基准测试集: (name, config, 预期最低分, 预期最高分, 评价)
@dataclass
class BenchmarkCase:
    name: str
    config: GenerationConfig
    min_score: float
    max_score: float
    note: str


BENCHMARK = [
    # 优秀名字 — 应该高分
    BenchmarkCase("张明远", GenerationConfig(name_type="person", style=["modern"], gender="M"), 70, 95, "经典好名"),
    BenchmarkCase("李慧雅", GenerationConfig(name_type="person", style=["chinese"], gender="F"), 65, 95, "文雅女性名"),
    BenchmarkCase("王知行", GenerationConfig(name_type="person", style=["modern"], gender="M"), 65, 95, "知行合一"),
    BenchmarkCase("林浩然", GenerationConfig(name_type="person", style=["modern"], gender="M"), 65, 95, "正气浩然"),

    # 一般名字 — 应该中等
    BenchmarkCase("赵明", GenerationConfig(name_type="person"), 40, 80, "二字简明"),
    BenchmarkCase("陈国强", GenerationConfig(name_type="person"), 40, 80, "普通常见名"),

    # 较差名字 — 应该低分
    BenchmarkCase("王阿狗", GenerationConfig(name_type="person"), 0, 50, "粗俗名，应低分"),
    BenchmarkCase("李死生", GenerationConfig(name_type="person"), 0, 30, "含负面字，应极低"),

    # 公司名
    BenchmarkCase("华为科技", GenerationConfig(name_type="company", style=["tech"]), 60, 95, "知名科技公司"),
    BenchmarkCase("阿里巴巴", GenerationConfig(name_type="company"), 40, 80, "知名电商"),
    BenchmarkCase("腾讯控股", GenerationConfig(name_type="company", industry=["technology"]), 50, 90, "科技巨头"),

    # 品牌名
    BenchmarkCase("小米", GenerationConfig(name_type="brand", style=["modern"]), 50, 90, "知名品牌"),
]


async def run_benchmark(lexicon: Lexicon) -> list[dict]:
    scorer = Scorer(lexicon)
    results = []

    for case in BENCHMARK:
        # 去掉姓氏前缀以得到纯名
        given_name = case.name
        surname = ""

        # 常见姓氏
        common_surnames = {"张", "李", "王", "赵", "陈", "林", "刘", "杨", "黄", "周", "吴", "郑"}
        for s in common_surnames:
            if case.name.startswith(s):
                surname = s
                given_name = case.name[len(s):]
                break

        chars = list(given_name)
        dims = scorer.score(given_name, case.config)
        total = scorer.total(dims)

        passed = case.min_score <= total <= case.max_score
        results.append({
            "name": case.name,
            "type": case.config.name_type,
            "note": case.note,
            "expected": f"{case.min_score}-{case.max_score}",
            "actual": total,
            "passed": passed,
            "dimensions": dims,
        })

    return results


async def analyze_weights(lexicon: Lexicon) -> dict:
    """通过随机采样分析各维度的贡献分布"""
    scorer = Scorer(lexicon)
    gen = NameGenerator(lexicon)

    dims_collect = {
        "meaning": [],
        "tone": [],
        "style": [],
        "readability": [],
        "length": [],
        "repeat": [],
    }

    configs = [
        GenerationConfig(name_type="person", style=["modern"], gender="M", count=20),
        GenerationConfig(name_type="person", style=["chinese"], gender="F", count=20),
        GenerationConfig(name_type="person", style=["natural"], gender="N", count=20),
        GenerationConfig(name_type="company", style=["tech"], count=10),
        GenerationConfig(name_type="brand", style=["modern"], count=10),
    ]

    for cfg in configs:
        names, _ = gen.generate(cfg)
        for n in names:
            for k in dims_collect:
                val = getattr(n.dimensions, k)
                dims_collect[k].append(val)

    stats = {}
    for k, values in dims_collect.items():
        if values:
            avg = sum(values) / len(values)
            low = min(values)
            high = max(values)
            spread = high - low
            stats[k] = {
                "avg": round(avg, 3),
                "min": round(low, 3),
                "max": round(high, 3),
                "spread": round(spread, 3),
            }
        else:
            stats[k] = {"avg": 0, "min": 0, "max": 0, "spread": 0}

    return stats


def print_report(results: list[dict], stats: dict):
    print("=" * 70)
    print("评分校准报告")
    print("=" * 70)
    print()

    # 基准测试结果
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    print(f"基准测试: {passed_count}/{total_count} 通过 ({passed_count/total_count*100:.0f}%)")
    print("-" * 70)
    print(f"{'名字':<16} {'类型':<10} {'预期范围':<12} {'实际分':<8} {'状态':<6} {'说明'}")
    print("-" * 70)
    for r in results:
        status = "✅" if r["passed"] else "❌"
        print(f"{r['name']:<16} {r['type']:<10} {r['expected']:<12} {r['actual']:<8.1f} {status:<6} {r['note']}")
    print()

    # 维度分析
    print("维度统计 (随机采样 80 个名字)")
    print("-" * 70)
    print(f"{'维度':<14} {'平均分':<8} {'最小值':<8} {'最大值':<8} {'跨度':<8} {'有效性'}")
    print("-" * 70)
    for k, s in stats.items():
        # 跨度大 = 区分度好
        effectiveness = "✅" if s["spread"] > 0.15 else "⚠️" if s["spread"] > 0.05 else "❌"
        print(f"{k:<14} {s['avg']:<8.3f} {s['min']:<8.3f} {s['max']:<8.3f} {s['spread']:<8.3f} {effectiveness}")
    print()

    # 权重敏感性分析
    print("权重敏感性分析")
    print("-" * 70)
    weights = {"meaning": 0.20, "tone": 0.20, "style": 0.15,
               "readability": 0.15, "length": 0.10, "repeat": 0.10, "ai": 0.10}
    for k, w in weights.items():
        if k in stats:
            # 贡献度 = 平均分 × 权重
            contribution = stats[k]["avg"] * w
            print(f"  {k:<14} 权重={w:<5} 平均分={stats[k]['avg']:<8.3f} 贡献={contribution:<.3f}")

    print()
    print("建议:")
    print("-" * 70)
    for r in results:
        if not r["passed"]:
            expected = r["expected"].split("-")
            min_e = float(expected[0])
            max_e = float(expected[1])
            if r["actual"] < min_e:
                print(f"  ⚠️ {r['name']} 得分偏低 ({r['actual']}/{min_e}) — 可能需要调高权重")
            else:
                print(f"  ⚠️ {r['name']} 得分偏高 ({r['actual']}/{max_e}) — 可能需要调低权重")

    # 识别区分度不足的维度
    for k, s in stats.items():
        if s["spread"] < 0.1:
            print(f"  ⚠️ {k} 维度区分度不足 (跨度={s['spread']}), 建议优化评分函数")


async def auto_adjust(lexicon: Lexicon):
    """自动微调评分函数参数"""
    scorer = Scorer(lexicon)

    # 尝试调整 meaning 评分中的正面词权重
    adjustments = []

    for case in BENCHMARK:
        given_name = case.name
        common_surnames = {"张", "李", "王", "赵", "陈", "林", "刘", "杨", "黄", "周", "吴", "郑"}
        for s in common_surnames:
            if case.name.startswith(s):
                given_name = case.name[len(s):]
                break

        dims = scorer.score(given_name, case.config)
        total = scorer.total(dims)
        if total < case.min_score:
            adjustments.append(f"  {case.name}: {total:.1f} < {case.min_score}, 需调高")
        elif total > case.max_score:
            adjustments.append(f"  {case.name}: {total:.1f} > {case.max_score}, 需调低")

    if adjustments:
        print("\n需要手动调整的项:")
        for a in adjustments:
            print(a)
        print("\n建议: 在 engine/scorer.py 中调整:")
        print("  1. 修改 _score_meaning 中的 positive_words 列表")
        print("  2. 调整聚合权重 (weights 字典)")
        print("  3. 修改音调评分中的 bonus/penalty 系数")
    else:
        print("所有基准测试通过，当前权重合理 ✓")


async def main():
    parser = argparse.ArgumentParser(description="评分校准工具")
    parser.add_argument("--auto-fix", action="store_true", help="尝试自动修复")
    args = parser.parse_args()

    db_path = str(Path(__file__).parent.parent / "data" / "lexicon.db")
    engine, sf = await init_db(f"sqlite+aiosqlite:///{db_path}")
    async with sf() as session:
        lexicon = Lexicon(session)
        await lexicon.load()

        results = await run_benchmark(lexicon)
        stats = await analyze_weights(lexicon)

        print_report(results, stats)

        if args.auto_fix:
            print("\n" + "=" * 70)
            await auto_adjust(lexicon)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
