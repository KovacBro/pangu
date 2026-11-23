# -*- coding: utf-8 -*-
"""
盘古 · 问学层（1.1.7）
======================
地理与编年回答「这里有什么、发生过什么」。这个模块回答另外两个问题：

    **住在这里的人，会提出什么假说？会卡在哪？**

跟前面几层同一套规矩——不编故事，只做推导。唯一的自变量是**观测能力**：

    天光 → 极限星等 → 能看到几颗星 → 能测什么 → 假说的形状
    重力/大气/化学 → 他们造得出什么仪器 → 难题在哪里停住

所以同一个物理世界，若把「无黑夜」换成「有黑夜」，整份问学都会变——
不是文风变了，是**可观测的信息集变了**。

三类输出的区别，是这份报告最要紧的地方：

| 类别 | 定义 | 判据 |
|---|---|---|
| `known` | 他们已经确定的事 | 有可重复的测量，且误差小于结论本身 |
| `hypotheses` | 他们在自己信息集内**合理**的解释 | 能解释已见现象，但可能是错的（像托勒密） |
| `puzzles` | 他们提出了、但当前技术解不开的 | 理论上可解，缺的是工具 |
| `unknowable` | **物理上拿不到信息**的 | 不是难，是这条路被封死了 |

最后一条是这份报告的价值所在：把「还没研究出来」和「永远不可能知道」分开，
一个世界才会显得有边界，而不是一个可以无限填充的袋子。
"""

from __future__ import annotations

import hashlib
import json
import random
from typing import Any

import sky as sk
import world_schema as ws

GENERATOR = "inquiry/1.1.7"

RULES_META = [
    ("K01", "历法", "calendar 有日长与年长", "必然"),
    ("K02", "天上有什么", "恒星与卫星可数", "必然"),
    ("K03", "海陆之比", "航海与远行已发生", "很可能"),
    ("H01", "大地是什么形状", "地平线与影长可测", "很可能"),
    ("H02", "双日怎么走", "恒星 ≥ 2 且有互绕周期", "很可能"),
    ("H03", "会呼吸的铜", "存在虚构元素", "很可能"),
    ("H04", "生命从哪来", "biochemistry 已声明", "很可能"),
    ("H05", "星星是什么", "极限星等允许分类", "很可能"),
    ("H06", "潮汐归谁管", "有卫星或无卫星", "很可能"),
    ("H07", "时间是什么", "year_days ÷ month_days 有余数", "很可能"),
    ("H08", "我们脚下还有什么", "溶剂有第二相或地壳分层", "很可能"),
    ("H09", "天会塌吗", "sky_phenomena 有周期灾变", "很可能"),
    ("P01", "三体问题", "恒星 ≥ 3 且轨道耦合", "必然"),
    ("P02", "元素表为什么断档", "虚构元素在周期表外", "很可能"),
    ("P03", "生命为何能活", "biochemistry.limits 苛刻", "很可能"),
    ("P04", "大地为何在动", "板块边界与山脉位置对不上", "很可能"),
    ("U01", "恒星有多远", "极限星等不足以看见暗弱背景", "必然"),
    ("U02", "银河长什么样", "看不到银河", "很可能"),
    ("U03", "有没有别的世界", "系外行星无法观测", "很可能"),
    ("U04", "恒星里面是什么", "无中微子探测能力", "必然"),
    ("U05", "自转这件事", "行星潮汐锁定", "必然"),
]


# ════════════════════════════════════════════════════════════════════
# 取数
# ════════════════════════════════════════════════════════════════════

def _dict(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _list(v: Any) -> list:
    return v if isinstance(v, list) else []


def _num(v: Any, d: float = 0.0) -> float:
    return ws._num(v, d)


def _stars(world: dict) -> list:
    return [s for s in _list(_dict(world.get("cosmology")).get("stars"))
            if isinstance(s, dict)]


def _bodies(world: dict) -> list:
    return [b for b in _list(_dict(world.get("cosmology")).get("bodies"))
            if isinstance(b, dict)]


def _cal(world: dict) -> dict:
    return _dict(_dict(world.get("cosmology")).get("calendar"))


def _pms(world: dict) -> dict:
    for b in _bodies(world):
        pm = _dict(b.get("planet_map"))
        if pm:
            return _dict(pm.get("summary"))
    return {}


def _civ(world: dict) -> dict:
    c = _dict(world.get("civilization"))
    return c if c.get("exists") is not False else {}


def _chem(world: dict) -> dict:
    return _dict(world.get("chemistry"))


def _bio(world: dict) -> dict:
    return _dict(_dict(world.get("biology")).get("biochemistry"))


def _phen(world: dict) -> list:
    return [p for p in _list(_dict(world.get("cosmology")).get("sky_phenomena"))
            if isinstance(p, str) and p.strip()]


def _src(world: dict, *paths) -> list:
    out = [p for p in paths if p and ws.resolve_path(world, p)[0]]
    return out or ["meta.name"]


def _seed_of(world: dict, override=None) -> int:
    if override is not None:
        return int(override)
    for p in ("inquiry.seed", "history.chronicle.seed",
              "cosmology.bodies[0].planet_map.seed", "meta.seed"):
        ok, v, _ = ws.resolve_path(world, p)
        if ok and _num(v) > 0:
            return int(_num(v))
    return 20261107


def _clip(text: Any, n: int = 40) -> str:
    t = str(text or "").strip()
    if t.startswith(("「", "『", "“")):
        t = t[1:].strip()
    if t.endswith(("」", "』", "”")):
        t = t[:-1].strip()
    if len(t) <= n:
        return t
    cut = t[:n]
    for m in ("，", "。", "；", "、", "——"):
        p = cut.rfind(m)
        if p >= n * 0.5:
            return cut[:p] + "……"
    return cut + "……"


# ════════════════════════════════════════════════════════════════════
# 观测能力：一切假说的边界
# ════════════════════════════════════════════════════════════════════

def observatory(world: dict) -> dict:
    b = {}
    try:
        b = sk.sky_brightness(world, 0.0)
    except Exception:  # noqa: BLE001 —— 算不出天光就按「典型黑夜」保守推
        b = {}
    limit = _num(b.get("limit_mag"), 6.5)
    visible = int(_num(b.get("visible_stars"), 6000))
    milky = bool(b.get("milky_way", limit >= 5.0 and visible >= 3000))
    stars = _stars(world)
    n_sun = len(stars)
    n_moon = max(0, len(_bodies(world)) - 1)
    cal = _cal(world)
    day = _num(cal.get("day_hours"), 24.0)
    yr = _num(cal.get("year_days"), 365.256)
    atmo = _dict(world.get("atmosphere"))
    molar = _num(atmo.get("mean_molar_mass_g"), 29.0)
    press = _num(atmo.get("pressure_kpa"), 101.3)
    # 视宁度：水汽与尘埃越多，星像越糊；这里只用一条经验式，标明在口径里
    vapor = _num(_dict(_dict(_chem(world).get("composition")).get("atmosphere"))
                 .get("水汽"), 0.0)
    seeing = "优秀" if vapor < 0.01 and press < 120 else (
        "尚可" if vapor < 0.03 else "很差")
    return {
        "limit_mag": round(limit, 2),
        "visible_stars": visible,
        "milky_way": milky,
        "has_night": limit >= 5.5,
        "deep_sky": limit >= 5.0 and visible >= 2000,
        "n_sun": n_sun,
        "n_moon": n_moon,
        "day_hours": day,
        "year_days": yr,
        "pressure_kpa": press,
        "molar_mass": molar,
        "seeing": seeing,
        "tidal_locked": bool(_dict(_bodies(world)[0] if _bodies(world) else {}).get("tidal_locked")),
        "limits_source": "sky.sky_brightness" if b else "缺省（按典型黑夜）",
    }


# ════════════════════════════════════════════════════════════════════
# 事件构造
# ════════════════════════════════════════════════════════════════════

def _ev(eid, kind, title, text, src, strength="很可能", extra=None) -> dict:
    d = {"id": eid, "kind": kind, "title": title, "text": text,
         "src": src, "strength": strength}
    if extra:
        d.update(extra)
    return d


# ════════════════════════════════════════════════════════════════════
# 已知
# ════════════════════════════════════════════════════════════════════

def _k01(world, ctx):
    cal, obs = _cal(world), ctx["obs"]
    if obs["year_days"] <= 0:
        return None
    days = int(obs["year_days"])
    months = int(_num(cal.get("months"), 0))
    tail = f"，分 {months} 个月" if months else ""
    return _ev("K01", "known", "一年有多长",
               f"一年 {obs['year_days']:g} 天{tail}，一昼夜 {obs['day_hours']:g} 小时。"
               f"这不是推测：只要数够 {days} 次日出，任何人都能复核。"
               f"**他们最早成熟的科学是历法，不是天文。**",
               _src(world, "cosmology.calendar.year_days", "cosmology.calendar.day_hours"),
               "必然")


def _k02(world, ctx):
    obs, stars = ctx["obs"], ctx["stars"]
    if not stars:
        return None
    names = "、".join(str(s.get("name") or s.get("id")) for s in stars[:4])
    moon = f"，另有 {obs['n_moon']} 颗卫星" if obs["n_moon"] else "，没有卫星"
    return _ev("K02", "known", "天上有什么",
               f"{len(stars)} 颗恒星：{names}{moon}。"
               f"亮的那几颗可以用手指数清，它们的相对位置几十年不变——"
               f"所以「天上有几个东西」是他们最早达成共识的问题之一。",
               _src(world, "cosmology.stars", "cosmology.bodies"), "必然")


def _k03(world, ctx):
    pms = ctx["pms"]
    land = _num(pms.get("land_fraction"))
    if land <= 0:
        return None
    return _ev("K03", "known", "海陆之比",
               f"陆地占 {land:.0%}，海洋占 {1 - land:.0%}。"
               f"这个数是航海者用「看不见岸要走几天」反推出来的，"
               f"不同城邦的船队给出的答案相差不到两成——所以他们知道海是通的。",
               _src(world, "cosmology.bodies[0].planet_map.summary.land_fraction"), "很可能")


# ════════════════════════════════════════════════════════════════════
# 假说（信息集内合理，可能是错的）
# ════════════════════════════════════════════════════════════════════

def _h01(world, ctx):
    obs = ctx["obs"]
    if obs["deep_sky"]:
        text = ("夜里能看见足够多的星，于是有人量了两地同一时刻的影长："
                "差一个经度，影长就差一点。他们因此推出「大地是圆的」，"
                "并且算出了半径——误差比他们的船队航线还小。")
        status = "至今成立"
    else:
        text = (f"天光太亮，极限星等只有 {obs['limit_mag']:g} 等，"
                f"肉眼只数得出 {obs['visible_stars']} 颗星。"
                f"他们没有恒星做远方的参照系，只能靠影长与地平线推形状："
                f"「大地是一枚被影子压扁的卵，两端是大雾。」"
                f"**这不是愚昧，是在没有参照物时的最优解。**")
        status = "无法验证"
    return _ev("H01", "hypothesis", "大地是什么形状", text,
               _src(world, "cosmology.sky_phenomena", "meta.name"),
               "很可能", {"status": status})


def _h02(world, ctx):
    stars = ctx["stars"]
    if len(stars) < 2:
        return None
    period = _num(_dict(stars[0].get("orbit")).get("period_days"))
    if period <= 0:
        return None
    n = len(stars)
    tail = (f"{n} 颗星的相互位置永远对不上一个简单的圆——他们很早就知道，"
            "**用本轮套本轮也套不准**，但没有人能证明它无解。"
            if n >= 3 else
            f"两颗星每 {period:g} 天绕一次，影子每天换一个夹角；"
            "他们用「大轮套小轮」解释它，和地球上的本轮说一样好用，也一样错。")
    return _ev("H02", "hypothesis", "双日怎么走",
               f"{n} 颗星的主周期是 {period:g} 天。{tail}",
               _src(world, "cosmology.stars"), "很可能",
               {"status": "后被推翻" if n == 2 else "悬而未决"})


def _h03(world, ctx):
    els = [e for e in _list(_chem(world).get("fictional_elements")) if isinstance(e, dict)]
    if not els:
        return None
    e = els[0]
    name = str(e.get("name") or "未命名元素")
    disc = _clip(e.get("discovered"), 46)
    trace = _clip(e.get("trace"), 34)
    if disc and disc[-1] not in "。！？…":
        disc += "。"
    text = (f"{disc}"
            f"他们能看见的证据是：{trace}"
            f"于是最早的化学假说是「万物由几种气与石配比而成」，"
            f"而 {name} 被归进「会变色的气」——**分类错了，但观察全对**。")
    return _ev("H03", "hypothesis", f"{name} 是什么", text,
               _src(world, "chemistry.fictional_elements"), "很可能",
               {"status": "后被修正"})


def _h04(world, ctx):
    bio = _bio(world)
    if not bio:
        return None
    base = str(bio.get("base") or "")
    struct = str(bio.get("structural_element") or "")
    limits = _clip(bio.get("limits"), 34)
    if limits and limits[-1] not in "。！？…":
        limits += "。"
    how = ("代谢用碳，承重用 " + struct if "碳" in base else
           "整个代谢都建在 " + struct)
    tail = ("于是创世假说必须解释「两种材料为什么会被焊在一起」，"
            "最流行的答案是「一个匠人把骨与肉分开烧，再合上」。"
            if "杂合" in base else
            "于是创世假说必须解释「一个只在这种条件下成立的循环，是怎么启动的」——"
            "最流行的答案是「一开始就有一口气，它从没停过」。")
    text = (f"他们的身体是{base}的：{how}。"
            f"这带来一个绕不开的观察——{limits}"
            f"{tail}")
    return _ev("H04", "hypothesis", "生命从哪来", text,
               _src(world, "biology.biochemistry"), "很可能", {"status": "无法验证"})


def _h05(world, ctx):
    obs, stars = ctx["obs"], ctx["stars"]
    if not stars:
        return None
    if obs["deep_sky"]:
        text = ("星有颜色，颜色不同的星亮度也不同——他们据此把星分成几等，"
                "并猜「星是远处的大火」。这个猜法只对了一半，但方向是对的。")
        status = "方向正确"
    else:
        text = (f"极限星等 {obs['limit_mag']:g} 等，暗星一律看不见，"
                f"所以他们手里的星表只有 {obs['visible_stars']} 个样本，"
                f"而且全是亮的。样本被截断，任何统计都会得出「星只有一种」。"
                f"**他们的恒星分类学，注定是错的。**")
        status = "被样本截断"
    return _ev("H05", "hypothesis", "星星是什么", text,
               _src(world, "cosmology.stars", "cosmology.sky_phenomena"), "很可能",
               {"status": status})


def _h06(world, ctx):
    obs = ctx["obs"]
    if obs["n_moon"] == 0:
        text = ("没有卫星，潮汐近乎为零。他们的语言里没有「潮」这个词，"
                "海平面被视为常数——**一个不存在的现象，不会产生假说**。")
        status = "无此问题"
    elif obs["tidal_locked"]:
        text = ("行星被潮汐锁定，潮汐停在原地：一半海面永远涨着，一半永远退着。"
                "他们最早的宇宙论是「海在慢慢流走，流向看不见的那一面」。")
        status = "部分正确"
    else:
        text = (f"{obs['n_moon']} 颗卫星拉着潮水。他们很早就算出潮与卫星位置同步，"
                f"但「为什么同步」要等到有人想到「远处的东西也能拉东西」——"
                f"这一步花了两千年。")
        status = "后来成立"
    return _ev("H06", "hypothesis", "潮汐归谁管", text,
               _src(world, "cosmology.bodies"), "很可能", {"status": status})


def _h07(world, ctx):
    cal = _cal(world)
    yd, md, months = ctx["obs"]["year_days"], _num(cal.get("month_days")), int(_num(cal.get("months")))
    if md <= 0 or months <= 0 or yd <= 0:
        return None
    rest = abs(yd - months * md)
    if rest < 0.02:
        text = (f"{yd:g} 天正好是 {months} 个整月，一天不多。"
                f"于是他们的时间观是**循环的、可算尽的**："
                f"历史被切成一个个相同的年，而不是一条射向终点的线。")
        status = "至今成立"
    else:
        text = (f"每年剩下 {rest:.2f} 天没有归属。谁来管这几天，谁就管时间——"
                f"他们的历法之争本质是权力之争，而「时间是一条线还是一圈」"
                f"这个问题，被这几天拖着一直没定论。")
        status = "悬而未决"
    return _ev("H07", "hypothesis", "时间是什么", text,
               _src(world, "cosmology.calendar"), "很可能", {"status": status})


def _h08(world, ctx):
    bio = _bio(world)
    solv = str(bio.get("solvent") or "")
    if "超临界" not in solv and "第二相" not in solv:
        return None
    deep = _clip(solv, 44)
    if deep and deep[-1] not in "。！？":
        deep += "。"
    return _ev("H08", "hypothesis", "我们脚下还有什么",
               f"溶剂不是一层：{deep}"
               f"最深的矿井越往下越热，水变得既不像水也不像汽——"
               f"他们把那里叫「第二层海」，并相信死者的名字会沉到那一层。",
               _src(world, "biology.biochemistry.solvent"), "很可能", {"status": "无法验证"})


def _h09(world, ctx):
    phen = ctx["phen"]
    if not phen:
        return None
    anchor = _clip(phen[0], 30)
    return _ev("H09", "hypothesis", "天会塌吗",
               f"最不容置疑的一幕是「{anchor}」。它按周期来，从不缺席。"
               f"于是最早的历史观是**灾变论**：世界每隔一段就被重来一次，"
               f"而「周期」是可以算的——这让他们比地球更早相信「未来可预测」。",
               _src(world, "cosmology.sky_phenomena"), "很可能", {"status": "至今成立"})


# ════════════════════════════════════════════════════════════════════
# 难题（理论可解，缺工具）
# ════════════════════════════════════════════════════════════════════

def _p01(world, ctx):
    stars = ctx["stars"]
    if len(stars) < 3:
        return None
    return _ev("P01", "puzzle", "三体问题",
               f"{len(stars)} 颗星互相拉扯，位置**没有闭式解**——他们的数学家会撞上同一堵墙："
               f"对两颗星能写出公式，对第三颗就不能。"
               f"这不是他们不够聪明，是这个问题本身不可积。"
               f"于是天文学被迫分裂成两派：一派画星表，一派算近似。",
               _src(world, "cosmology.stars"), "必然",
               {"status": "永远解不开", "why": "N≥3 的引力系统一般不可积"})


def _p02(world, ctx):
    els = [e for e in _list(_chem(world).get("fictional_elements")) if isinstance(e, dict)]
    if not els:
        return None
    e = els[0]
    z = _num(e.get("atomic_number"))
    return _ev("P02", "puzzle", "元素表为什么断档",
               f"{e.get('name')} 的原子序数是 {z:g}，比已知最重的元素还大——"
               f"按他们的排序法，它应该出现在表的最末，但它的性质却像最前面的一族。"
               f"**表在这里裂开一道缝**，而他们没有光谱仪去填。",
               _src(world, "chemistry.fictional_elements"), "很可能",
               {"status": "缺工具", "why": "需要光谱与真空技术"})


def _p03(world, ctx):
    bio = _bio(world)
    limits = str(bio.get("limits") or "")
    if len(limits) < 12:
        return None
    return _ev("P03", "puzzle", "生命为何能活",
               f"他们的生化有一条硬约束：{_clip(limits, 46)}"
               f"按他们自己的化学，这条反应需要更高的温度，而身体里测不到那么热。"
               f"**这是一个整整两千年的悬案**：直到有人想到「热可能只在很小的地方发生」。",
               _src(world, "biology.biochemistry.limits"), "很可能",
               {"status": "后来解开", "why": "局部微环境而非整体温度"})


def _p04(world, ctx):
    pms = ctx["pms"]
    relief = _num(pms.get("max_elevation_km"))
    if relief <= 0:
        return None
    conv = int(_num(pms.get("convergent_cells")))
    return _ev("P04", "puzzle", "大地为何在动",
               f"最高的山 {relief:.1f} km，而按他们的侵蚀模型，"
               f"{relief / 0.05:.0f} 万年内就该被削平——可山还在。"
               f"他们数出 {conv} 处「山在长」的地方，却不知道为什么长。"
               f"**「地会动」这个念头，在他们的语言里等同于疯话。**",
               _src(world,
                    "cosmology.bodies[0].planet_map.summary.max_elevation_km",
                    "cosmology.bodies[0].planet_map.summary.convergent_cells"),
               "很可能", {"status": "缺工具", "why": "需要大地测量与深时概念"})


# ════════════════════════════════════════════════════════════════════
# 不可知（物理上拿不到信息）
# ════════════════════════════════════════════════════════════════════

def _u01(world, ctx):
    obs = ctx["obs"]
    if obs["deep_sky"]:
        return None
    return _ev("U01", "unknowable", "恒星有多远",
               f"测距要基线：地球人靠「换个位置看同一颗星，它相对背景挪了一点」。"
               f"可他们的极限星等只有 {obs['limit_mag']:g} 等，"
               f"能看见的 {obs['visible_stars']} 颗星背后**没有更暗的背景**——"
               f"挪了也看不出来。**没有背景，就没有视差；没有视差，就没有距离。**"
               f"恒星的距离，在他们那里不是难题，是不存在的量。",
               _src(world, "cosmology.stars"), "必然",
               {"why": "背景星不可见，视差基线失效"})


def _u02(world, ctx):
    obs = ctx["obs"]
    if obs["milky_way"]:
        return None
    return _ev("U02", "unknowable", "银河长什么样",
               f"银河需要暗到能看见成千上万颗暗星。他们的天光是 {obs['limit_mag']:g} 等，"
               f"整条银河被压在阈值以下——**他们的一生里，天空只有 {obs['visible_stars']} 个点**。"
               f"任何「我们的星系是什么形状」的问题，在他们那里都没有观测入口。",
               _src(world, "cosmology.starfield", "cosmology.stars"), "很可能",
               {"why": "暗星不可见，银河结构无法成像"})


def _u03(world, ctx):
    return _ev("U03", "unknowable", "有没有别的世界",
               "要发现系外行星，得测恒星的微小光度起伏或视向速度——"
               "这需要连续、精密、跨年的观测，而他们的记录工具还停在「画下来」。"
               "**他们可以想象别的世界，但永远无法确认。**",
               _src(world, "civilization.tech_path"), "很可能",
               {"why": "缺精密测光与长期记录"})


def _u04(world, ctx):
    return _ev("U04", "unknowable", "恒星里面是什么",
               "恒星的内部结构只能靠中微子与日震学反推。"
               "他们的世界里没有一种能穿透整颗恒星的粒子探测器——"
               "**看得见表面，看不见里面，而表面永远在骗人。**",
               _src(world, "cosmology.stars"), "必然",
               {"why": "缺中微子探测与日震观测"})


def _u05(world, ctx):
    if not ctx["obs"]["tidal_locked"]:
        return None
    return _ev("U05", "unknowable", "自转这件事",
               "行星被潮汐锁定：天空不动，星不移，日不落。"
               "「我们在转」这个念头在他们的经验里没有任何对应物——"
               "**科里奥利力、傅科摆、时区，整套概念都不会诞生**。",
               _src(world, "cosmology.bodies[0].planet_map.tidal_locked"), "必然",
               {"why": "无自转可观测"})


RULES = [_k01, _k02, _k03, _h01, _h02, _h03, _h04, _h05, _h06, _h07, _h08, _h09,
         _p01, _p02, _p03, _p04, _u01, _u02, _u03, _u04, _u05]


# ════════════════════════════════════════════════════════════════════
# 推演
# ════════════════════════════════════════════════════════════════════

def derive(world: dict, seed=None) -> dict:
    obs = observatory(world)
    ctx = {
        "obs": obs,
        "stars": _stars(world),
        "phen": _phen(world),
        "pms": _pms(world),
        "chem": _chem(world),
        "bio": _bio(world),
    }
    buckets = {"known": [], "hypothesis": [], "puzzle": [], "unknowable": []}
    for fn in RULES:
        try:
            e = fn(world, ctx)
        except Exception:  # noqa: BLE001 —— 单条规则挂了不该吞掉整份报告
            e = None
        if e:
            buckets[e["kind"]].append(e)

    groups = []
    for k in ("known", "hypothesis", "puzzle", "unknowable"):
        groups.extend(buckets[k])

    return {
        "generator": GENERATOR,
        "seed": _seed_of(world, seed),
        "hash": _hash(groups),
        "observatory": obs,
        "groups": {
            "known": buckets["known"],
            "hypotheses": buckets["hypothesis"],
            "puzzles": buckets["puzzle"],
            "unknowable": buckets["unknowable"],
        },
        "summary": {
            "n_known": len(buckets["known"]),
            "n_hypotheses": len(buckets["hypothesis"]),
            "n_puzzles": len(buckets["puzzle"]),
            "n_unknowable": len(buckets["unknowable"]),
            "blind_spot": not obs["deep_sky"],
        },
    }


def _hash(groups: list) -> str:
    payload = json.dumps(
        [{"id": e["id"], "t": e["title"], "x": e["text"]} for e in groups],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def stored(world: dict) -> dict:
    return _dict(world.get("inquiry"))


def check(world: dict) -> dict:
    ch = stored(world)
    if not ch:
        return {"ok": False, "hash_ok": None, "stale": [], "self_ok": None,
                "why": "inquiry 不存在（未跑过 inquiry --write）",
                "stored_hash": None, "now_hash": None, "content_hash": None}
    groups = ch.get("groups") or {}
    flat = []
    for k in ("known", "hypotheses", "puzzles", "unknowable"):
        flat.extend([e for e in _list(groups.get(k)) if isinstance(e, dict)])
    now = derive(world, seed=ch.get("seed"))
    stored_hash = str(ch.get("hash") or "")
    content_hash = _hash(flat)
    self_ok = content_hash == stored_hash
    hash_ok = self_ok and stored_hash == now["hash"]
    stale = []
    for e in flat:
        bad = [p for p in _list(e.get("src"))
               if isinstance(p, str) and not ws.resolve_path(world, p)[0]]
        if bad:
            stale.append({"id": e.get("id"), "title": e.get("title"), "bad": bad})
    why = ""
    if not self_ok:
        why = "存档内容与自己的 hash 对不上：假说被手改过"
    elif not hash_ok:
        why = "存档 hash 与按当前设定重推的结果不一致：改了世界没重跑 --write"
    elif stale:
        why = f"{len(stale)} 条的依据字段已不存在"
    return {"ok": hash_ok and not stale, "hash_ok": hash_ok, "self_ok": self_ok,
            "stale": stale, "why": why, "stored_hash": stored_hash,
            "content_hash": content_hash, "now_hash": now["hash"]}


# ════════════════════════════════════════════════════════════════════
# 呈现
# ════════════════════════════════════════════════════════════════════

_HEAD = [
    ("known", "◆ 他们已经确定的"),
    ("hypotheses", "◇ 他们提出过的假说"),
    ("puzzles", "▸ 他们解不开的难题"),
    ("unknowable", "✗ 他们不可能知道的"),
]


def format_report(d: dict, world: dict) -> str:
    name = str(_dict(world.get("meta")).get("name") or "这个世界")
    civ = str(_civ(world).get("name") or "")
    o = _dict(d.get("observatory"))
    g = _dict(d.get("groups"))
    L = [f"【盘古 · 问学】{name}" + (f" · {civ}" if civ else ""), "-" * 62]
    L.append(f"  日长 {_num(o.get('day_hours')):g} h ｜ 年长 {_num(o.get('year_days')):g} 天"
             f" ｜ {int(_num(o.get('n_sun')))} 颗恒星 ｜ {int(_num(o.get('n_moon')))} 颗卫星")
    L.append(f"  极限星等 {_num(o.get('limit_mag')):.1f} 等 ｜ 肉眼 {int(_num(o.get('visible_stars')))} 颗"
             f" ｜ 银河{'可见' if o.get('milky_way') else '不可见'}"
             f" ｜ 视宁度 {o.get('seeing')}")
    if not o.get("has_night"):
        L.append("  ⚠ 这个世界的夜晚不够黑：所有「看远处」的科学都会被卡住")
    L.append("-" * 62)

    for key, head in _HEAD:
        items = [e for e in _list(g.get(key)) if isinstance(e, dict)]
        if not items:
            continue
        L.append(f"\n{head}")
        for e in items:
            tone = "●" if e.get("strength") == "必然" else "○"
            tag = str(e.get("status") or "")
            L.append(f"  {tone} {e.get('id')} {e.get('title')}"
                     + (f"　〔{tag}〕" if tag else ""))
            for line in _wrap(str(e.get("text") or "").replace("**", ""), 56):
                L.append("      " + line)

    s = _dict(d.get("summary"))
    L.append("\n" + "-" * 62)
    L.append(f"  已知 {s.get('n_known', 0)} ｜ 假说 {s.get('n_hypotheses', 0)}"
             f" ｜ 难题 {s.get('n_puzzles', 0)} ｜ 不可知 {s.get('n_unknowable', 0)}"
             f" ｜ hash {d.get('hash')}")
    L.append("  口径：假说的形状由「看得见什么」决定；不可知由物理封死，不是没研究。")
    return "\n".join(L)


def to_markdown(d: dict, world: dict, heading: bool = True) -> str:
    name = str(_dict(world.get("meta")).get("name") or "这个世界")
    o = _dict(d.get("observatory"))
    g = _dict(d.get("groups"))
    L = [f"### 问学 · {name}", ""] if heading else []
    L.append(f"- 极限星等 {_num(o.get('limit_mag')):.1f} 等 ｜ "
             f"肉眼 {int(_num(o.get('visible_stars')))} 颗 ｜ "
             f"银河{'可见' if o.get('milky_way') else '不可见'} ｜ hash `{d.get('hash')}`")
    L.append("")
    for key, head in _HEAD:
        items = [e for e in _list(g.get(key)) if isinstance(e, dict)]
        if not items:
            continue
        L.append(f"**{head}**")
        L.append("")
        for e in items:
            L.append(f"- **{e.get('id')} {e.get('title')}**"
                     + (f"（{e.get('status')}）" if e.get("status") else ""))
            L.append("")
            L.append(f"  {e.get('text')}")
            L.append("")
    return "\n".join(L)


_NO_HEAD = "，。、；：？！）」』%…—·"


def _wrap(text: str, width: int) -> list:
    out, line, w = [], "", 0
    for ch in text:
        cw = 2 if ord(ch) > 0x2E80 else 1
        if w + cw > width and line and ch not in _NO_HEAD:
            out.append(line)
            line, w = "", 0
        line += ch
        w += cw
    if line:
        out.append(line)
    return out or [""]


def meta_rows() -> list:
    return [{"id": i, "name": n, "when": w, "strength": s} for i, n, w, s in RULES_META]
