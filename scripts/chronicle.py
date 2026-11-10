# -*- coding: utf-8 -*-
"""
盘古 · 编年层（1.1.6）
======================
前面的版本把世界的**律**、**地**、**天**都算出来了，唯独「人」这一层只有散文：
`civilization` 是一段自我介绍，`history.eras` 是三个手写的纪元标题。
读者会问：那这三千年里到底发生了什么？

这个模块的回答方式是**不编故事**——跟 `entail` 一样，只做正向推导：

    承载力 → 人口曲线（logistic） → 人口刻度 → 事件时刻 → 事件文案

于是每一条事件都能回答「你凭什么是这一年」：
    年长来自 `cosmology.calendar.year_days`
    人口上限来自 `biology.carrying_capacity.humans_subsistence`
    历法事件来自 `year_days / month_days` 的余数
    禁忌来自 `civilization.taboo`
    能源、技术、社会形状直接引用 `civilization.*` 的原文
    国教锚定在 `cosmology.sky_phenomena` 里最显眼的那一条

三条设计约束（与 entailment / ca_engine 同源）：
  · **单一真相**：只用 world.json 已声明的字段，缺字段就少一条事件，不猜、不补
  · **可复算**：seed + world → 逐位一致的 events 与 hash，`--check` 当场对账
  · **可证伪**：每条事件带 `src`（引用哪几个字段）、`strength`（必然 / 很可能）
    与 `q`（在文明跨度上的相对时刻）；`--check` 会指出哪条引用已经失效

刻意没做的事：
  · 不写人名、不写国名。名字是作者的事，年份与因果是引擎的事。
  · 不做多文明交互（战争只有一条，且由人口压力推出，不是编排出来的剧情）。
  · 不覆盖 `history.eras`。作者手写的纪年是**上位叙事**，编年史是它下面的一条时间轴。
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from typing import Any

import world_schema as ws

GENERATOR = "chronicle/1.1.6"

# 起点的聚落人口：一个能自我维持、开始记年的规模
P0 = 5000.0

# 事件时刻表：q 是「文明跨度上的相对时刻」，0 = 第一笔，1 = 人口顶点
# 顺序即输出顺序（排序前），也是 --list 的顺序
RULES_META = [
    ("H01", "第一笔", "有历法", "必然"),
    ("H02", "定历", "year_days 与 month_days 可算", "必然"),
    ("H03", "立禁", "civilization.taboo 非空", "很可能"),
    ("H04", "能源", "civilization.energy_source 非空", "很可能"),
    ("H05", "种子入土", "有承载力且陆地占比 > 0", "很可能"),
    ("H06", "第一批城市", "人口规模足够", "很可能"),
    ("H07", "文字", "civilization.timekeeping 非空", "很可能"),
    ("H08", "出海", "海洋占比 > 0.4 或存在卫星", "很可能"),
    ("H09", "成国", "civilization.social_shape 非空", "很可能"),
    ("H10", "争地", "人口接近上限", "很可能"),
    ("H11", "大疫", "人口密度高", "很可能"),
    ("H12", "变法", "civilization.tech_path 非空", "很可能"),
    ("H13", "国教", "sky_phenomena 非空", "很可能"),
    ("H14", "顶点", "人口到峰值", "必然"),
    ("H15", "余波", "总有结局", "很可能"),
    ("H20", "双日之民", "恒星 ≥ 2", "必然"),
    ("H21", "没有黑夜", "恒星总光度 ≥ 1 L☉", "必然"),
    ("H22", "两段睡眠", "日长偏离 24 h 超过 25%", "必然"),
    ("H23", "晨昏线", "行星潮汐锁定", "必然"),
]

ERA_BANDS = [
    (0.10, "萌芽纪"),
    (0.28, "农耕纪"),
    (0.48, "城邦纪"),
    (0.70, "王国纪"),
    (1.0001, "鼎盛纪"),
    (9.99, "余波纪"),
]


# ════════════════════════════════════════════════════════════════════
# 取值助手
# ════════════════════════════════════════════════════════════════════

def _dict(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _list(v: Any) -> list:
    return v if isinstance(v, list) else []


def _num(v: Any, d: float = 0.0) -> float:
    return ws._num(v, d)


def _cal(world: dict) -> dict:
    return _dict(_dict(world.get("cosmology")).get("calendar"))


def _b0(world: dict) -> dict:
    for b in _list(_dict(world.get("cosmology")).get("bodies")):
        if isinstance(b, dict):
            return b
    return {}


def _pms(world: dict) -> dict:
    return _dict(_dict(_b0(world).get("planet_map")).get("summary"))


def _pm(world: dict) -> dict:
    return _dict(_b0(world).get("planet_map"))


def _civ(world: dict) -> dict:
    c = _dict(world.get("civilization"))
    return c if c.get("exists") is not False else {}


def _cc(world: dict) -> dict:
    return _dict(_dict(world.get("biology")).get("carrying_capacity"))


def _phen(world: dict) -> list:
    return [p for p in _list(_dict(world.get("cosmology")).get("sky_phenomena"))
            if isinstance(p, str) and p.strip()]


def _stars(world: dict) -> list:
    return [s for s in _list(_dict(world.get("cosmology")).get("stars"))
            if isinstance(s, dict)]


def _derived_stars(world: dict) -> list:
    try:
        d = ws.compute_derived(world)
    except Exception:  # noqa: BLE001 —— 编年史不该因为派生层挂了就整个不出
        return []
    return [s for s in _list(d.get("stars")) if isinstance(s, dict)]


def _src(world: dict, *paths) -> list:
    """只保留真实存在的引用路径：不存在的字段不许冒充依据。"""
    out = [p for p in paths if p and ws.resolve_path(world, p)[0]]
    return out or ["meta.name"]


def _people(n: float) -> str:
    """数字与量词之间不留空格：折行时「629.0 / 亿人」被拆开很难看。"""
    if n >= 1e8:
        return f"{n / 1e8:.1f}亿"
    if n >= 1e4:
        return f"{n / 1e4:.0f}万"
    return f"{n:.0f}"


def _pct(x: float) -> str:
    if x >= 0.1:
        return f"{x:.0%}"
    if x >= 0.001:
        return f"{x:.1%}"
    return f"{x:.2%}"


def _clip(text: Any, n: int = 44) -> str:
    """把作者写的长句剪成一句可引用的短语：不改变意思，只去掉枝蔓。"""
    t = str(text or "").strip()
    # 作者常在字段里自带上引号；不剥掉就会变成「「……」」
    opened = t.startswith(("「", "『", "“", '"', "'"))
    if opened:
        t = t[1:].strip()
    if t.endswith(("」", "』", "”", '"', "'")):
        t = t[:-1].strip()
    if opened:
        t = t.replace("」。", "。", 1).replace("」，", "，", 1)
    if len(t) <= n:
        return t
    cut = t[:n]
    for mark in ("，", "。", "；", "、", "——", "（"):
        p = cut.rfind(mark)
        if p >= n * 0.5:
            return cut[:p] + "……"
    return cut + "……"


def _q(text: Any, n: int = 44) -> str:
    """引用作者的原文：单层书名号，长句自动截断，避免出现「「」」的双引号套娃。"""
    return f"「{_clip(text, n)}」"


# ════════════════════════════════════════════════════════════════════
# 上下文：把 world.json 压成推演需要的几个数
# ════════════════════════════════════════════════════════════════════

def _seed_of(world: dict, override=None) -> int:
    if override is not None:
        return int(override)
    for path in ("history.chronicle.seed", "cosmology.bodies[0].planet_map.seed",
                 "meta.seed", "seed.number"):
        ok, v, _ = ws.resolve_path(world, path)
        if ok and _num(v) > 0:
            return int(_num(v))
    return 20261107


def _capacity(world: dict) -> tuple:
    """返回 (可养活人口, 依据路径)。优先级：声明的承载力 > 由 NPP 现算。"""
    k = _num(_cc(world).get("humans_subsistence"))
    if k > 0:
        return k, "biology.carrying_capacity.humans_subsistence"
    npp = _num(_pms(world).get("land_npp_gtc_yr"))
    if npp > 0:
        k = npp * 1e15 * 9.0 * 0.01 / (2500.0 * 365.0)
        return k, "cosmology.bodies[0].planet_map.summary.land_npp_gtc_yr"
    return 0.0, ""


def context(world: dict, seed=None) -> dict:
    """构造推演上下文。所有随机量只在这里取，顺序固定 → 可复算。"""
    cal = _cal(world)
    pms = _pms(world)
    civ = _civ(world)
    rng = random.Random(_seed_of(world, seed))

    k, k_src = _capacity(world)
    if k <= 0:
        k = P0 * 800.0          # 无承载力时退化为「八百万人的小世界」，并标在口径里
        k_src = "（缺失承载力，按 800 万人占位）"

    # 气候适配：宜居窗口 288 K，偏离越大农业效率越低（下限 45%）
    t_k = _num(pms.get("mean_temperature_k"), 288.0)
    fit = max(0.45, 1.0 - abs(t_k - 288.0) / 60.0)
    if _pm(world).get("tidal_locked"):
        fit *= 0.7              # 晨昏线世界只有一条可耕带

    # 增长速率与「实际峰值占理论上限的比例」：这两项是仅有的两个自由度
    r = (0.00055 + 0.00055 * rng.random()) * fit
    p_peak = 0.035 + 0.075 * rng.random()
    if fit < 0.6:
        p_peak *= 0.7
    p_peak = max(0.005, min(0.35, p_peak))

    a = k / P0 - 1.0
    t_max = math.log(a / (1.0 / p_peak - 1.0)) / r if 0 < p_peak < 1 and a > 0 else 0.0
    t_max = max(t_max, 400.0)

    def p_of(t: float) -> float:
        return k / (1.0 + a * math.exp(-r * t))

    year_days = _num(cal.get("year_days"), 365.256)
    day_hours = _num(cal.get("day_hours"), 24.0)
    months = int(_num(cal.get("months"), 0))
    month_days = _num(cal.get("month_days"), year_days / months if months else 0.0)

    return {
        "world": world, "seed": _seed_of(world, seed), "rng": rng,
        "k": k, "k_src": k_src, "p0": P0, "r": r, "p_peak": p_peak,
        "t_max": t_max, "p_of": p_of, "fit": fit,
        "cal": cal, "pms": pms, "pm": _pm(world), "civ": civ,
        "phen": _phen(world), "stars": _stars(world), "dstars": _derived_stars(world),
        "year_days": year_days, "day_hours": day_hours,
        "months": months, "month_days": month_days,
    }


def era_of(t: float, t_max: float) -> str:
    q = (t / t_max) if t_max > 0 else 0.0
    for edge, name in ERA_BANDS:
        if q < edge:
            return name
    return ERA_BANDS[-1][1]


def _ev(ctx, eid, kind, title, text, q, src, strength="很可能") -> dict:
    t_max = ctx["t_max"]
    t = q * t_max
    era = era_of(t, t_max) if q <= 1.0 else "余波纪"
    # 顶点之后进入平台：人口不再沿 logistic 继续爬向 K，
    # 否则「余波」会比「顶点」人更多——那是把理论上限当成了历史事实。
    p = min(ctx["p_of"](min(t, t_max)), ctx["p_peak"] * ctx["k"])
    return {
        "id": eid, "kind": kind, "title": title, "text": text,
        "t_year": int(round(t)), "era": era, "q": round(q, 4),
        "people": int(round(p)),
        "src": src, "strength": strength,
    }


# ════════════════════════════════════════════════════════════════════
# 事件
# ════════════════════════════════════════════════════════════════════

def _h01(world, ctx):
    cal = ctx["cal"]
    epoch = str(cal.get("epoch") or "").strip()
    seed_src = _src(world, "cosmology.calendar.epoch", "cosmology.calendar.year_days",
                    "cosmology.calendar.day_hours")
    carrier = "星图边缘" if _dict(_dict(world.get("cosmology")).get("starfield")) else "骨片与石柱"
    head = f"「{epoch}」" if epoch else "无名之年"
    return _ev(
        ctx, "H01", "origin", "第一笔",
        (f"{head}，这一年被记作第 0 年：一昼夜 {ctx['day_hours']:g} 小时、"
         f"一年 {ctx['year_days']:g} 天，第一次被刻在{carrier}上。"
         f"从此他们有了「以前」和「以后」——这是这个文明唯一一次不需要理由的跃迁。"),
        0.0, seed_src, "必然")


def _h02(world, ctx):
    yd, md, months = ctx["year_days"], ctx["month_days"], ctx["months"]
    if yd <= 0:
        return None
    src = _src(world, "cosmology.calendar.year_days", "cosmology.calendar.month_days",
               "cosmology.calendar.months")
    if md > 0 and months > 0:
        q = yd / md
        near = abs(q - round(q)) < 0.01 and round(q) >= 1
        rest = yd - months * md
        if near:
            text = (f"{yd:g} 天 ÷ {md:g} 天 = {round(q)}：一年正好 {round(q)} 个「月」，"
                    f"**历法不需要闰日**。这是算术给他们的礼物，不是祭司的功劳——"
                    f"任何人只要会除法就能预言下一次节庆在哪一天。")
        else:
            text = (f"{months} 个月 × {md:g} 天 = {months * md:g} 天，一年剩 "
                    f"{rest:+.2f} 天。这 {abs(rest):.2f} 天必须有人决定塞进哪一个月，"
                    f"于是**历法成了权力**：谁管余数，谁管时间。")
    else:
        text = (f"一年 {yd:g} 天被均分成若干段，段与段之间没有天体可参照——"
                f"他们的「月」是纯人为的行政区间。")
    return _ev(ctx, "H02", "calendar", "定历", text, 0.02, src, "必然")


def _h03(world, ctx):
    civ = ctx["civ"]
    taboo = str(civ.get("taboo") or "").strip()
    if not taboo:
        return None
    return _ev(
        ctx, "H03", "taboo", "立禁",
        (f"{_q(taboo, 34)}被写进最早的律法。它读起来像道德，其实是生理学："
         f"这条禁忌的每一条都对应着物理层的一个代价。"
         f"世界先收钱，然后才有人替它编理由。"),
        0.04, _src(world, "civilization.taboo"), "很可能")


def _h04(world, ctx):
    civ = ctx["civ"]
    e = str(civ.get("energy_source") or "").strip()
    if not e:
        return None
    P = ctx["p_of"](0.10 * ctx["t_max"])
    return _ev(
        ctx, "H04", "energy", "能源",
        (f"人口到 {_people(P)}，柴薪的边际收益开始下降。"
         f"{_q(e, 32)}第一次被当成基础设施，而不是运气——"
         f"能量密度决定了他们能造多大的城、能走多远的路。"),
        0.10, _src(world, "civilization.energy_source"), "很可能")


def _h05(world, ctx):
    pms = ctx["pms"]
    land = _num(pms.get("land_fraction"))
    k = ctx["k"]
    if land <= 0 and not ctx["k_src"].startswith("biology"):
        return None
    P = ctx["p_of"](0.16 * ctx["t_max"])
    return _ev(
        ctx, "H05", "agriculture", "种子入土",
        (f"陆地只占 {_pct(land) if land > 0 else '一小块'}，可耕的还要再打折。"
         f"把种子埋进土里之后，同一片地的产出第一次超过采集——"
         f"这颗星球的理论口粮上限是 {_people(k)}人（{ctx['k_src']}），"
         f"而此时他们还不到 {_people(P)}人。"
         f"**从这一刻起，每一次人口增长都在预支未来。**"),
        0.16, _src(world, "cosmology.bodies[0].planet_map.summary.land_fraction",
                   "biology.carrying_capacity.humans_subsistence"), "很可能")


def _h06(world, ctx):
    ocean = _num(ctx["pms"].get("ocean_fraction"))
    P = ctx["p_of"](0.30 * ctx["t_max"])
    where = "海岸线上——水运比陆运便宜一个数量级" if ocean > 0.4 else "河谷与山口"
    return _ev(
        ctx, "H06", "city", "第一批城市",
        (f"人口 {_people(P)}人。第一批万人城长在{where}。"
         f"城市不是变大的村庄：它把「陌生人之间的合作」变成了日常，"
         f"也第一次让瘟疫、火灾与暴动有了足够的密度。"),
        0.30, _src(world, "cosmology.bodies[0].planet_map.summary.ocean_fraction"), "很可能")


def _h07(world, ctx):
    tk = str(ctx["civ"].get("timekeeping") or "").strip()
    if not tk:
        return None
    P = ctx["p_of"](0.38 * ctx["t_max"])
    return _ev(
        ctx, "H07", "writing", "文字",
        (f"人口 {_people(P)}人，粮食要入仓、税要记账、节庆要排到下一年。"
         f"文字为记账而生，随后被用来写诗。他们的计时方式是：{_q(tk, 30)}"
         f"——历法不是天文学的副产品，是行政的第一块地基。"),
        0.38, _src(world, "civilization.timekeeping"), "很可能")


def _h08(world, ctx):
    ocean = _num(ctx["pms"].get("ocean_fraction"))
    has_moon = len(_list(_dict(world.get("cosmology")).get("bodies"))) > 1
    if ocean <= 0.4 and not has_moon:
        return None
    locked = bool(ctx["pm"].get("tidal_locked"))
    if locked:
        tail = "行星被潮汐锁定，没有潮汐表可背；他们把星位当经纬，把「远方」当成一个可以算出来的地方。"
    elif has_moon:
        tail = "有卫星就有潮汐表：退潮时露出的那条路，是普通人唯一免费的远行方式。"
    else:
        tail = "没有卫星，潮汐近乎为零；出海靠季风与星象，一次远航就是一次赌博。"
    return _ev(
        ctx, "H08", "sea", "出海",
        f"海洋占 {_pct(ocean) if ocean > 0 else '未知比例'}。{tail}",
        0.46, _src(world, "cosmology.bodies[0].planet_map.summary.ocean_fraction"), "很可能")


def _h09(world, ctx):
    ss = str(ctx["civ"].get("social_shape") or "").strip()
    if not ss:
        return None
    P = ctx["p_of"](0.56 * ctx["t_max"])
    return _ev(
        ctx, "H09", "state", "成国",
        (f"人口 {_people(P)}人，灌溉、防洪、运粮都需要跨村落调度，"
         f"于是有了不种地也能吃饭的人。他们的社会形状是：{_q(ss, 34)}"
         f"——这不是文化选择，是地理与能量密度允许的唯一几种解法之一。"),
        0.56, _src(world, "civilization.social_shape"), "很可能")


def _h10(world, ctx):
    P = ctx["p_of"](0.68 * ctx["t_max"])
    peak = ctx["p_peak"] * ctx["k"]
    return _ev(
        ctx, "H10", "war", "争地",
        (f"人口 {_people(P)}人，而这条曲线终点是 {_people(peak)}人。"
         f"人均好地已经分完，边际产出开始下降——"
         f"**马尔萨斯压力不是一种观点，是一条曲线**：再往前，每多一个人就少一口饭。"
         f"于是战争从掠夺变成了必需。"),
        0.68, _src(world, "biology.carrying_capacity.humans_subsistence"), "很可能")


def _h11(world, ctx):
    P = ctx["p_of"](0.76 * ctx["t_max"])
    return _ev(
        ctx, "H11", "plague", "大疫",
        (f"人口 {_people(P)}人，城市密度足够让病原体把宿主当成道路。"
         f"一次大疫抹掉了一到三成人口——在他们的编年史里，这往往比任何一场战争都更接近「天意」。"),
        0.76, _src(world, "cosmology.bodies[0].planet_map.summary.land_fraction"), "很可能")


def _h12(world, ctx):
    tp = str(ctx["civ"].get("tech_path") or "").strip()
    if not tp:
        return None
    return _ev(
        ctx, "H12", "reform", "变法",
        (f"他们的技术树不走地球那条路：{_q(tp, 40)}"
         f"这条路少了一整段材料的台阶，也因此在别处更早撞到天花板。"
         f"技术路径由元素与相态决定，不由聪明程度决定。"),
        0.84, _src(world, "civilization.tech_path"), "很可能")


def _h13(world, ctx):
    phen = ctx["phen"]
    if not phen:
        return None
    anchor = _clip(phen[0], 38)
    return _ev(
        ctx, "H13", "faith", "国教",
        (f"信仰锚定在最不容置疑的那一幕上：「{anchor}」"
         f"它每天/每年准时发生，可预测、可复用、无法反驳——"
         f"**一个能被算出来的神，比一个全能的神更像真的。**"),
        0.90, _src(world, "cosmology.sky_phenomena"), "很可能")


def _h14(world, ctx):
    k, peak = ctx["k"], ctx["p_peak"] * ctx["k"]
    return _ev(
        ctx, "H14", "peak", "顶点",
        (f"人口 {_people(peak)}人，占理论上限 {_people(k)}人的 {_pct(ctx['p_peak'])}。"
         f"没有到 100%：真实文明永远卡在「能养活」与「真的养活」之间那道沟里——"
         f"战争、瘟疫、盐碱化与赋税各吃掉一部分。"
         f"**这个百分比是引擎给的，不是史书给的。**"),
        1.00, _src(world, "biology.carrying_capacity.humans_subsistence"), "必然")


def _h15(world, ctx):
    rng = ctx["rng"]
    fit = ctx["fit"]
    if fit < 0.6 or ctx["p_peak"] <= 0.012:
        kind, text = "衰退", (
            "气候与承载力的余量太薄，一次摆动就够。人口在顶点下方来回震荡，"
            "每一代人都觉得「我们正在恢复」，而曲线一直在缓慢地往下走。"
            "他们没有灭亡，只是一直没能再站起来。")
    else:
        pick = rng.random()
        if pick < 0.45:
            kind, text = "停滞", (
                "技术在凸轮与杠杆处停住，制度在税与徭役之间循环。"
                "两千年过去，农民种的东西、背的赋、怕的事，与顶点那年几乎一致。"
                "**停滞不是懒惰，是能量与材料的上限先到了。**")
        elif pick < 0.78:
            kind, text = "外扩", (
                "他们把过剩的人口推上船（或推过山口），在外海与高原上复制了一套同类社会。"
                "母星的人口曲线因此被削平——扩张是历史上唯一被反复验证过的减速器。")
        else:
            kind, text = "断裂", (
                "一次技术跃迁与一次生态崩溃撞在一起。旧秩序在几十年内解体，"
                "文字还在，但已经没人能读懂上一个纪元的账本——"
                "**这是考古学家的起点，不是文明的终点。**")
    return _ev(
        ctx, "H15", "aftermath", "余波", text, 1.15,
        _src(world, "biology.carrying_capacity.humans_subsistence"), "很可能")


def _h20(world, ctx):
    st = ctx["stars"]
    if len(st) < 2:
        return None
    names = "、".join(str(s.get("name") or s.get("id") or "?") for s in st[:2])
    period = _num(_dict(st[0].get("orbit")).get("period_days"))
    tail = (f"两颗星每 {period:g} 天互绕一周，影子每天换一次夹角，每 {period:g} 天重合一次。"
            f"他们的时间单位不是太阳给的，是**两颗星的相对位置**给的。"
            if period > 0 else "两颗星的位置决定了他们的时间单位。")
    return _ev(
        ctx, "H20", "binary", "双日之民",
        f"天上不只有一个光源：{names}。{tail}",
        0.06, _src(world, "cosmology.stars"), "必然")


def _h21(world, ctx):
    st = ctx["stars"]
    if not st:
        return None
    lum = sum(_num(s.get("luminosity_solar")) for s in st)
    if len(st) < 2 or lum < 1.0:
        return None
    return _ev(
        ctx, "H21", "dark", "没有黑夜",
        (f"恒星总光度 {lum:g} L☉，夜里的天光被压在 19 等上下。"
         f"他们抬头只能看见两百来颗星，银河是传说不是景。"
         f"**在一个没有真正黑夜的世界里，「怕黑」这种情绪根本不会进化出来**；"
         f"守夜、宵禁、夜祷这套制度也就无从谈起——他们的问题从来不是黑，是亮。"),
        0.34, _src(world, "cosmology.stars"), "必然")


def _h22(world, ctx):
    dh = ctx["day_hours"]
    if dh <= 0 or abs(dh - 24.0) / 24.0 <= 0.25:
        return None
    long_day = dh > 24.0
    return _ev(
        ctx, "H22", "rhythm", "两段睡眠" if long_day else "碎觉",
        (f"一昼夜 {dh:g} 小时。{'一次睡眠撑不到下一个天亮' if long_day else '一昼夜太短，一次长睡是奢侈'}，"
         f"于是作息被切成两段{'（昼中一觉、夜中一觉）' if long_day else '（多次短睡）'}。"
         f"他们的语言里没有「熬夜」——因为『夜』本来就长到必须被切开。"),
        0.22, _src(world, "cosmology.calendar.day_hours"), "必然")


def _h23(world, ctx):
    if not ctx["pm"].get("tidal_locked"):
        return None
    return _ev(
        ctx, "H23", "terminator", "晨昏线",
        ("行星被潮汐锁定：一半永昼，一半永夜，中间一条永远停在同一经度的晨昏线。"
         "**所有城市都长在这条线上**，所有迁徙都是沿着它走——"
         "「向北」在他们的语言里不是一个方向，是一次自杀。"),
        0.50, _src(world, "cosmology.bodies[0].planet_map.tidal_locked"), "必然")


RULES = [_h01, _h02, _h03, _h04, _h05, _h06, _h07, _h08,
         _h09, _h10, _h11, _h12, _h13, _h14, _h15,
         _h20, _h21, _h22, _h23]


# ════════════════════════════════════════════════════════════════════
# 推演与存档
# ════════════════════════════════════════════════════════════════════

def derive(world: dict, seed=None) -> dict:
    """从 world.json 推出一条文明编年史（纯函数，同输入同输出）。"""
    ctx = context(world, seed)
    events = []
    for fn in RULES:
        try:
            e = fn(world, ctx)
        except Exception:  # noqa: BLE001 —— 单条规则挂了不该吞掉整条时间轴
            e = None
        if e:
            events.append(e)
    events.sort(key=lambda e: (e["t_year"], e["id"]))

    t_max = ctx["t_max"]
    span = int(round(events[-1]["t_year"] if events else 0))
    summary = {
        "n_events": len(events),
        "span_years": span,
        "carrying_capacity": round(ctx["k"], 0),
        "peak_population": int(round(ctx["p_peak"] * ctx["k"])),
        "peak_share": round(ctx["p_peak"], 4),
        "growth_per_year": round(ctx["r"], 6),
        "climate_fit": round(ctx["fit"], 3),
        "eras": [{"name": n, "from_year": int(round(e * t_max))}
                 for e, n in ERA_BANDS[:-1]],
    }
    return {
        "generator": GENERATOR,
        "seed": ctx["seed"],
        "hash": event_hash(events),
        "calendar": {
            "epoch": str(ctx["cal"].get("epoch") or ""),
            "day_hours": ctx["day_hours"],
            "year_days": ctx["year_days"],
            "months": ctx["months"],
            "month_days": round(ctx["month_days"], 3),
        },
        "population": {
            "start": int(ctx["p0"]),
            "carrying_capacity": round(ctx["k"], 0),
            "carrying_capacity_source": ctx["k_src"],
            "peak": int(round(ctx["p_peak"] * ctx["k"])),
            "peak_share": round(ctx["p_peak"], 4),
            "growth_per_year": round(ctx["r"], 6),
            "model": "logistic：P(t)=K/(1+(K/P0-1)e^(-rt))",
        },
        "summary": summary,
        "events": events,
    }


def event_hash(events: list) -> str:
    """只对「内容」取哈希：改一岁、改一句都会变，改排版不会。"""
    payload = json.dumps(
        [{"id": e["id"], "t": e["t_year"], "title": e["title"], "text": e["text"]}
         for e in events],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def stored(world: dict) -> dict:
    return _dict(_dict(world.get("history")).get("chronicle"))


def check(world: dict) -> dict:
    """复算对账 + 引用失效检测。返回 {ok, hash_ok, stale, over, why}。"""
    ch = stored(world)
    if not ch:
        return {"ok": False, "hash_ok": None, "stale": [], "over": [],
                "why": "history.chronicle 不存在（未跑过 chronicle --write）",
                "recomputed": None, "stored_hash": None, "now_hash": None}
    seed = ch.get("seed")
    now = derive(world, seed=seed)
    # 两把锁：① 存档内容对不对得上它自己的 hash（手改检测）
    #         ② 存档 hash 对不对得上按当前设定重推的结果（下游漂移检测）
    stored_hash = str(ch.get("hash") or "")
    content_hash = event_hash([e for e in _list(ch.get("events")) if isinstance(e, dict)])
    self_ok = content_hash == stored_hash
    hash_ok = self_ok and stored_hash == now["hash"]
    stale = []
    for e in _list(ch.get("events")):
        if not isinstance(e, dict):
            continue
        bad = [p for p in _list(e.get("src"))
               if isinstance(p, str) and not ws.resolve_path(world, p)[0]]
        if bad:
            stale.append({"id": e.get("id"), "title": e.get("title"), "bad": bad})
    k = _num(_dict(ch.get("population")).get("carrying_capacity"))
    over = []
    if k > 0:
        for e in _list(ch.get("events")):
            if isinstance(e, dict) and _num(e.get("people")) > k * 1.02:
                over.append({"id": e.get("id"), "people": _num(e.get("people")),
                             "k": k})
    why = ""
    if not self_ok:
        why = ("存档内容与它自己的 hash 对不上：史被手改过"
               f"（内容 {content_hash} ≠ 存档 {stored_hash}）")
    elif not hash_ok:
        why = ("存档 hash 与按当前设定重推的结果不一致："
               f"改了下游字段没重跑 --write（存档 {stored_hash} ≠ 现算 {now['hash']}）")
    elif stale:
        why = f"{len(stale)} 条事件引用的字段已不存在"
    elif over:
        why = f"{len(over)} 条事件的人口超过了承载力"
    return {"ok": hash_ok and not stale and not over,
            "hash_ok": hash_ok, "self_ok": self_ok,
            "stale": stale, "over": over, "why": why,
            "recomputed": now, "stored_hash": stored_hash,
            "content_hash": content_hash, "now_hash": now["hash"]}


# ════════════════════════════════════════════════════════════════════
# 呈现
# ════════════════════════════════════════════════════════════════════

_ICON = {"必然": "●", "很可能": "○"}


def format_report(ch: dict, world: dict, kind: str = "all") -> str:
    name = str(_dict(world.get("meta")).get("name") or "这个世界")
    pop = _dict(ch.get("population"))
    sm = _dict(ch.get("summary"))
    cal = _dict(ch.get("calendar"))
    events = [e for e in _list(ch.get("events")) if isinstance(e, dict)]
    if kind != "all":
        events = [e for e in events if e.get("kind") == kind]

    L = []
    L.append(f"【盘古 · 编年史】{name}"
             + (f" · {_civ(world).get('name')}" if _civ(world).get("name") else ""))
    L.append("-" * 62)
    L.append(f"  年长 {cal.get('year_days', 0):g} 天 ｜ 日长 {cal.get('day_hours', 0):g} 小时"
             f" ｜ 纪元「{cal.get('epoch') or '未命名'}」")
    L.append(f"  可养活 {_people(_num(pop.get('carrying_capacity')))}人"
             f" ｜ 实际峰值 {_people(_num(pop.get('peak')))}人"
             f"（{_pct(_num(pop.get('peak_share')))}）")
    L.append(f"  跨度 {sm.get('span_years', 0):,} 年 ｜ 增速 {_num(pop.get('growth_per_year')):.5f}/年"
             f" ｜ 气候适配 {_num(sm.get('climate_fit')):.2f}")
    L.append("-" * 62)

    era = None
    for e in events:
        if e.get("era") != era:
            era = e.get("era")
            L.append(f"\n◆ {era}")
        tone = _ICON.get(str(e.get("strength")), "·")
        L.append(f"  {tone} 第 {int(e.get('t_year', 0)):,} 年  "
                 f"{e.get('id')} {e.get('title')}"
                 f"   〔人 {_people(_num(e.get('people')))}〕")
        for line in _wrap(str(e.get("text") or "").replace("**", ""), 56):
            L.append("      " + line)

    L.append("\n" + "-" * 62)
    L.append(f"  共 {len(events)} 条 ｜ hash {ch.get('hash')} ｜ seed {ch.get('seed')}"
             f" ｜ 生成器 {ch.get('generator')}")
    L.append("  ● 必然（可由数值算出）  ○ 很可能（生态与社会的合理外推）")
    L.append("  口径：事件时刻由人口曲线反解，人口上限来自承载力声明；"
             "不写人名、不写国名——那是作者的活。")
    return "\n".join(L)


_NO_HEAD = "，。、；：？！）」』%…—·"

# 「629.0亿」「355.9 天」「1.468 L☉」这类数字+量词是不可分割单元：
# 折行时把它们整体换行，否则会出现「629.0 / 亿人」这种断口。
_UNIT_RE = re.compile(
    r"\d+(?:[.,]\d+)?(?:\s*)(?:亿|万|千|%|℃|K|km|m|s|Gyr|年|天|小时|人|L☉)?")


def _units(text: str) -> list:
    out, i = [], 0
    while i < len(text):
        m = _UNIT_RE.match(text, i)
        if m and m.end() > i:
            out.append(m.group(0))
            i = m.end()
        else:
            out.append(text[i])
            i += 1
    return out


def _wrap(text: str, width: int) -> list:
    """按显示宽度折行（中文算 2），带避头尾与数字整体换行。"""
    out, line, w = [], "", 0
    for u in _units(text):
        uw = sum(2 if ord(c) > 0x2E80 else 1 for c in u)
        if w + uw > width and line and u[0] not in _NO_HEAD:
            out.append(line)
            line, w = "", 0
        line += u
        w += uw
    if line:
        out.append(line)
    return out or [""]


def to_markdown(ch: dict, world: dict, heading: bool = True) -> str:
    name = str(_dict(world.get("meta")).get("name") or "这个世界")
    pop = _dict(ch.get("population"))
    sm = _dict(ch.get("summary"))
    L = [f"### 编年史 · {name}", ""] if heading else []
    L.append(f"- 年长 {_num(_dict(ch.get('calendar')).get('year_days')):g} 天 ｜ "
             f"跨度 {sm.get('span_years', 0):,} 年 ｜ "
             f"可养活 {_people(_num(pop.get('carrying_capacity')))} 人 ｜ "
             f"峰值 {_people(_num(pop.get('peak')))}")
    L.append(f"- 模型：{pop.get('model', '')}；hash `{ch.get('hash')}`")
    L.append("")
    L.append("| 年 | 纪元 | 事件 | 人口 | 依据 |")
    L.append("|---|---|---|---|---|")
    for e in _list(ch.get("events")):
        if not isinstance(e, dict):
            continue
        src = "、".join(f"`{p}`" for p in _list(e.get("src"))[:2]) or "—"
        L.append(f"| {int(e.get('t_year', 0)):,} | {e.get('era')} | "
                 f"**{e.get('title')}** | {_people(_num(e.get('people')))} | {src} |")
    L.append("")
    for e in _list(ch.get("events")):
        if not isinstance(e, dict):
            continue
        L.append(f"**第 {int(e.get('t_year', 0)):,} 年 · {e.get('title')}**"
                 f"（{e.get('strength')}）")
        L.append("")
        L.append(str(e.get("text") or ""))
        L.append("")
    return "\n".join(L)


def meta_rows() -> list:
    return [{"id": i, "name": n, "when": w, "strength": s}
            for i, n, w, s in RULES_META]


def known_ids() -> dict:
    return {i: n for i, n, _w, _s in RULES_META}
