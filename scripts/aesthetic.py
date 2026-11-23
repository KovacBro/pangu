# -*- coding: utf-8 -*-
"""
盘古 · 艺术层（1.1.7）
======================
艺术不是装饰，是**感官在特定物理条件下的最优解**。

这个模块只做一件事：把世界已经算出来的物理量，翻译成「他们会做什么样的艺术」。
每一条都要回答三个问题：

    他们的感官收到什么？（光、声、重力、时间）
    这个条件下什么做法是"好"的？（不是地球的好，是这里的好）
    代价是什么？（材料、体力、可保存性）

所以一个 1.76 g、三恒星、没有真正黑夜、大气 1.32 atm 的世界，
不会画出地球的文艺复兴，也不会写 4/4 拍的小夜曲——
它的绘画要先解决「暗部不存在」，它的音乐要把「一昼 31 小时」当成作品的天然长度。

两条硬规矩：
  · 每条结论必须挂 `src`，答不出「凭哪个物理量」的艺术评论，不许出现在引擎的输出里
  · 声速、波长、基频这些都是真算的（`sqrt(γRT/M)`、维恩位移），不是形容词
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import world_schema as ws

GENERATOR = "aesthetic/1.1.7"

R_GAS = 8.314462618          # J/(mol·K)
GAMMA = 1.4                  # 双原子为主的大气
C_EARTH = 343.0              # m/s，20℃ 干空气

RULES_META = [
    ("V01", "调色板", "恒星色温可算峰值波长", "必然"),
    ("V02", "影的画法", "恒星 ≥ 2", "必然"),
    ("V03", "暗部", "极限星等不足", "很可能"),
    ("M01", "音高", "大气温度与摩尔质量可算声速", "必然"),
    ("M02", "节奏", "日长偏离 24 h", "必然"),
    ("M03", "乐器", "重力可算体型", "很可能"),
    ("A01", "建筑", "重力与风", "很可能"),
    ("A02", "城市形态", "海陆与地形", "很可能"),
    ("L01", "文学", "taboo 与天象", "很可能"),
    ("L02", "叙事", "时间观（历法余数）", "很可能"),
    ("R01", "仪式", "sky_phenomena 周期", "很可能"),
    ("W01", "一件作品", "以上全部", "很可能"),
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


def _b0(world: dict) -> dict:
    b = _bodies(world)
    return b[0] if b else {}


def _cal(world: dict) -> dict:
    return _dict(_dict(world.get("cosmology")).get("calendar"))


def _pms(world: dict) -> dict:
    return _dict(_dict(_b0(world).get("planet_map")).get("summary"))


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
    for p in ("aesthetic.seed", "inquiry.seed", "history.chronicle.seed",
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


_CN = {2: "两", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}


def _cn(n: int) -> str:
    """小数目用汉字（两 / 三 / 四），再大就用阿拉伯数字。"""
    return _CN.get(int(n), str(int(n)))


def _gist(txt: Any, n: int = 44) -> str:
    """取第一句（到「。」为止），超长再截。已经带「」的不再套一层。"""
    t = str(txt or "").strip()
    if not t:
        return ""
    i = t.find("。")
    if i > 0:
        t = t[:i + 1]
    if len(t) > n:
        t = t[:n].rstrip("，、；") + "……"
    return t


# ════════════════════════════════════════════════════════════════════
# 感官条件：一切艺术形式的自变量
# ════════════════════════════════════════════════════════════════════

def senses(world: dict) -> dict:
    cal = _cal(world)
    pms = _pms(world)
    atmo = _dict(world.get("atmosphere"))
    t_k = _num(pms.get("mean_temperature_k"), 288.0)
    M = _num(atmo.get("mean_molar_mass_g"), 29.0) / 1000.0
    P = _num(atmo.get("pressure_kpa"), 101.3) * 1000.0

    # 声速 c = sqrt(γRT/M) —— 真物理，不是估计
    c = math.sqrt(GAMMA * R_GAS * t_k / M) if M > 0 else C_EARTH
    rho = P * M / (R_GAS * t_k) if t_k > 0 else 1.2

    # 维恩位移：光谱峰值
    peaks = []
    for s in _stars(world):
        st = _num(s.get("temp_k"))
        if st > 0:
            peaks.append(2.898e6 / st)
    lam = sum(peaks) / len(peaks) if peaks else 550.0

    # 重力：与 validate / entail 取同一处——派生表里第一个天体的 gravity_g_calc
    g = 0.0
    try:
        d = ws.compute_derived(world)
        for b in _list(d.get("bodies")):
            if isinstance(b, dict) and _num(b.get("gravity_g_calc")) > 0:
                g = _num(b.get("gravity_g_calc"))
                break
    except Exception:  # noqa: BLE001
        g = 0.0

    day = _num(cal.get("day_hours"), 24.0)
    year = _num(cal.get("year_days"), 365.256)
    return {
        "temp_k": t_k,
        "molar_mass": M * 1000.0,
        "pressure_kpa": P / 1000.0,
        "sound_speed": round(c, 1),
        "sound_ratio": round(c / C_EARTH, 3),
        "density": round(rho, 3),
        "lambda_nm": round(lam, 0),
        "gravity_g": round(g, 2),
        "day_hours": day,
        "year_days": year,
        "n_sun": len(_stars(world)),
        "n_moon": max(0, len(_bodies(world)) - 1),
        "ocean": round(_num(pms.get("ocean_fraction")), 3),
        "tilt": _num(_dict(_b0(world)).get("axial_tilt_deg"), 0.0),
        "tidal_locked": bool(_dict(_b0(world)).get("tidal_locked")),
    }


def _ev(eid, kind, title, text, src, strength="很可能") -> dict:
    return {"id": eid, "kind": kind, "title": title, "text": text,
            "src": src, "strength": strength}


# ════════════════════════════════════════════════════════════════════
# 视觉
# ════════════════════════════════════════════════════════════════════

def _v01(world, ctx):
    s = ctx["senses"]
    lam = s["lambda_nm"]
    if lam < 480:
        shift = "偏蓝：他们的「暖色」比我们冷一档，红颜料要更贵"
    elif lam > 600:
        shift = "偏红：蓝在环境光里几乎不反射，蓝颜料得靠矿物硬磨"
    else:
        shift = (f"接近太阳白，但 {s['n_sun']} 颗星叠加后色温更散"
                 if s["n_sun"] >= 2 else "接近太阳白，色温单一，白就是白")
    return _ev("V01", "vision", "调色板",
               f"恒星光谱峰值 {lam:.0f} nm（地球 500 nm），{shift}。"
               f"环境光里缺的那一段，他们不会觉得缺——"
               f"**「颜色齐全」是一种地方性错觉**，他们的画从出生起就少几个色。",
               _src(world, "cosmology.stars"), "必然")


def _v02(world, ctx):
    s = ctx["senses"]
    n = s["n_sun"]
    if n < 2:
        return None
    return _ev("V02", "vision", "影的画法",
               f"天上有 {n} 个光源，于是每个物体有 {_cn(n)}道影子，"
               f"方向不同、软硬不同。他们的绘画从第一天起就是**多光源问题**："
               f"单光源的明暗法在这里是错的，真正的基本功是「让{_cn(n)}道影不打架」。"
               f"这也是他们最早的分科——有人专画硬影，有人专画软影。",
               _src(world, "cosmology.stars"), "必然")


def _v03(world, ctx):
    s = ctx["senses"]
    n = s["n_sun"]
    if n < 2:
        return None
    return _ev("V03", "vision", "暗部",
               f"天光压住了暗星，画布上也几乎见不到纯黑："
               f"夜里最暗的地方仍是灰紫色。于是他们的「暗部」不是颜料，"
               f"是**影与影之间的缝**——把构图往缝里收，是他们的高级技法。"
               f"第一幅被公认的杰作，画的是一整面没有物体的墙，只有{_cn(n)}道影在交叠。",
               _src(world, "cosmology.stars", "cosmology.sky_phenomena"), "很可能")


# ════════════════════════════════════════════════════════════════════
# 音乐
# ════════════════════════════════════════════════════════════════════

def _m01(world, ctx):
    s = ctx["senses"]
    c, ratio = s["sound_speed"], s["sound_ratio"]
    semis = 12.0 * math.log2(ratio)
    dirn = "高" if semis > 0 else "低"
    if abs(semis) < 0.5:
        tail = ("差不到半个半音，耳朵分辨不出，但**它是可算的**："
                "偏移来自平均温度与摩尔质量，不来自听觉。")
    else:
        tail = (f"**同样的管长，他们的乐器整个音域{dirn}了 {abs(semis):.1f} 个半音**"
                f"——这不是调音习惯，是气体的性质。")
    return _ev("M01", "music", "音高",
               f"声速 {c:g} m/s（地球 343），同一根管子的基频比地球{dirn} "
               f"{abs(semis):.1f} 个半音。{tail}"
               f"于是「标准音」这件事从一开始就和管长、与当地气温绑定，而不是和频率绑定。",
               _src(world, "atmosphere", "cosmology.bodies[0].planet_map.summary.mean_temperature_k"),
               "必然")


def _m02(world, ctx):
    s = ctx["senses"]
    day = s["day_hours"]
    if abs(day - 24.0) / 24.0 < 0.1:
        return None
    ratio = day / 24.0
    return _ev("M02", "music", "节奏",
               f"一昼夜 {day:g} 小时，是地球的 {ratio:.2f} 倍。"
               f"他们的作品长度单位不是「分钟」，是「一昼的几分之一」——"
               f"**长曲是常态，短曲是技艺**。呼吸与作息的周期决定了"
               f"最舒服的乐句长度，而那个长度比我们"
               f"{'长' if ratio > 1 else '短'} {abs(ratio * 100 - 100):.0f}%。",
               _src(world, "cosmology.calendar.day_hours"), "必然")


def _m03(world, ctx):
    s = ctx["senses"]
    g = s["gravity_g"]
    if g <= 0:
        return None
    # 体型标度：线性尺寸 ∝ g^-0.33
    scale = (1.0 / g) ** 0.33 if g > 0 else 1.0
    bend = "手腕撑不住长号，所以铜管普遍做成盘绕的" if g > 1.3 else (
        "体型大，臂展长，能同时按住更多的孔" if g < 0.8 else "与地球相仿")
    return _ev("M03", "music", "乐器",
               f"重力 {g:.2f} g，体型约为地球人的 {scale:.2f} 倍。{bend}。"
               f"**乐器的尺寸上限不是材料，是演奏者的承重**——"
               f"这条约束在重力越大的世界越早把「大型乐器」逼成「多人乐器」。",
               _src(world, "cosmology.bodies[0].mass_earth",
                    "cosmology.bodies[0].radius_km"), "很可能")


# ════════════════════════════════════════════════════════════════════
# 建筑与城市
# ════════════════════════════════════════════════════════════════════

def _a01(world, ctx):
    s = ctx["senses"]
    g = s["gravity_g"]
    if g <= 0:
        return None
    if g > 1.4:
        form, why = "矮而厚：穹顶与拱券优先，尖塔是炫技而不是结构", "承重墙的厚度随 g 线性增长，尖塔的自重先压垮自己"
    elif g < 0.7:
        form, why = "高而细：塔与索结构先出现，因为自重不再是瓶颈", "同样的材料能撑起两倍的高度"
    else:
        form, why = "与地球相仿：五到十层是自然的经济高度", "材料强度与自重的比值接近临界"
    return _ev("A01", "arch", "建筑",
               f"重力 {g:.2f} g。他们的建筑形态是「{form}」。{why}。"
               f"所以建筑史的第一课不是美学，是**抗压**——"
               f"所有看起来像风格的曲线，底下都有一道受力计算。",
               _src(world, "cosmology.bodies[0].gravity_g",
                    "cosmology.bodies[0].planet_map.summary.max_elevation_km"),
               "很可能")


def _a02(world, ctx):
    s = ctx["senses"]
    ocean = s["ocean"]
    if ocean <= 0:
        return None
    tilt = s["tilt"]
    if s["tidal_locked"]:
        form = ("城市全挤在一条晨昏线上：向光面太热，背光面太冷，"
                "只有那条缝里能住人")
        why = "潮汐锁定把「宜居带」压成一条线"
    elif ocean > 0.6:
        form = "城市长在海岸与河口，内陆是猎场而不是家；港口即首都"
        why = "水运成本比陆运低一个数量级"
    elif tilt > 40:
        form = "城市有「夏址」与「冬址」两套，随季节整体迁移"
        why = "倾角太大，同一纬度在冬夏的生境完全不同"
    else:
        form = "城市沿河谷与山口分布，形成一条条链"
        why = "可耕地与通道决定了几何"
    return _ev("A02", "arch", "城市形态",
               f"海洋 {ocean:.0%}，倾角 {tilt:g}°。{form}——{why}。"
               f"他们的「故乡」概念因此比我们窄：不是一片国土，是**一条线或一个点**。",
               _src(world, "cosmology.bodies[0].planet_map.summary.ocean_fraction",
                    "cosmology.bodies[0].axial_tilt_deg"), "很可能")


# ════════════════════════════════════════════════════════════════════
# 文学与仪式
# ════════════════════════════════════════════════════════════════════

def _l01(world, ctx):
    civ = _civ(world)
    taboo = _gist(civ.get("taboo"), 44)
    phen = _phen(world)
    if not taboo and not phen:
        return None
    def _say(txt):
        t = txt.rstrip("。")
        return t if t[:1] in ("「", "『", "“") else f"「{t}」"

    t = f"最深的禁忌是{_say(taboo)}" if taboo else "没有成文的禁忌"
    p = (f"最常被引用的意象是{_say(_gist(phen[0], 40))}"
         if phen else "没有共同的天象")
    return _ev("L01", "letter", "文学",
               f"{t}；{p}。于是他们的悲剧不写「命运的捉弄」，"
               f"写**「明知会发生，仍要伸手」**——因为天象是准时的，"
               f"而人偏偏要在准时的事情面前做选择。",
               _src(world, "civilization.taboo", "cosmology.sky_phenomena"), "很可能")


def _l02(world, ctx):
    cal = _cal(world)
    yd, md, months = _num(cal.get("year_days")), _num(cal.get("month_days")), int(_num(cal.get("months")))
    if yd <= 0:
        return None
    rest = abs(yd - months * md) if (md > 0 and months > 0) else 1.0
    if rest < 0.02:
        text = (f"一年 {yd:g} 天正好 {months} 个月，没有余数。"
                f"他们的叙事是**闭环的**：故事必须回到开头，"
                f"「从此以后」在他们的句式里不存在，只有「下一个同样的年」。")
    elif rest < 1.0:
        text = (f"每年多出 {rest:.2f} 天，几十年才凑成一天——他们不设闰日，"
                f"设「闰月」：隔一代人补一次。于是年与月**可通约而不可整除**，"
                f"他们的叙事也这样：能对上，但从不在同一点对上；"
                f"故事总有最后一章，只是那一章不落在整数上。")
    else:
        text = (f"每年剩 {rest:.2f} 天无处安放。这 {rest:.2f} 天成了一种特权，"
                f"也成了叙事的裂缝：他们的故事里总有一个「多出来的日子」，"
                f"那天发生的事不算数，也不被记住。")
    return _ev("L02", "letter", "叙事", text,
               _src(world, "cosmology.calendar"), "很可能")


def _r01(world, ctx):
    phen = _phen(world)
    stars = _stars(world)
    if not phen or not stars:
        return None
    period = _num(_dict(stars[0].get("orbit")).get("period_days"))
    if period <= 0:
        return None
    year = s["year_days"] if s["year_days"] > 0 else 365.256
    return _ev("R01", "ritual", "仪式",
               f"最盛大的节庆跟着 {period:g} 天的周期走，而不是跟着年走。"
               f"一年 {year:g} 天里要过 {max(1, int(year / period))} 次同样的节——"
               f"**节庆密度决定了他们的社会节奏**："
               f"协作窗口短而频繁，长周期的计划反而难以维持。",
               _src(world, "cosmology.stars", "cosmology.sky_phenomena"), "很可能")


# ════════════════════════════════════════════════════════════════════
# 一件作品（把上面全部压成一个可用的东西）
# ════════════════════════════════════════════════════════════════════

def _w01(world, ctx):
    s = ctx["senses"]
    stars = _stars(world)
    phen = _phen(world)
    if not stars:
        return None
    names = [str(x.get("name") or x.get("id")) for x in stars[:3]]
    n = s["n_sun"]
    title = (f"《{names[0]}·{names[1]}三叠》" if n >= 3 else
             f"《{names[0]}·{names[1]}对位》" if n == 2 else
             f"《{names[0]}·独影》")
    parts = []
    if n >= 3:
        parts.append(f"三声部，分别对应{'、'.join(names[:3])}的运行周期")
    elif n == 2:
        parts.append(f"两个声部，一句追一句，间距按 {names[0]} 与 {names[1]} 的相位差定")
    else:
        parts.append(f"单声部，主题是 {names[0]} 的弧，从升到落为一完整句")
    if n >= 2:
        parts.append(f"舞台只打 {n} 束方向不同的光，演员必须让{_cn(n)}道影不重叠")
    parts.append(f"全曲长 {s['day_hours']:g} 小时，正好一昼，中途不落幕")
    if phen:
        parts.append(f"最高潮处全场静默，等「{_clip(phen[0], 20)}」出现")
    shadow = (f"默认「{_cn(n)}道影」是常态" if n >= 2 else "默认「一道影、一条准时的弧」")
    return _ev("W01", "work", "一件作品",
               f"{title}。" + "；".join(parts) + "。"
               f"它之所以成立，是因为**这个世界的观众默认「一昼」是一个完整单位**、"
               f"{shadow}、默认「准时发生的事」值得等待——"
               f"换成地球的观众，这三条一条都不成立。",
               _src(world, "cosmology.stars", "cosmology.sky_phenomena",
                    "cosmology.calendar.day_hours"), "很可能")


RULES = [_v01, _v02, _v03, _m01, _m02, _m03, _a01, _a02, _l01, _l02, _r01, _w01]


# ════════════════════════════════════════════════════════════════════
# 推演
# ════════════════════════════════════════════════════════════════════

def derive(world: dict, seed=None) -> dict:
    ctx = {"senses": senses(world),
           "stars": _stars(world), "phen": _phen(world)}
    forms = []
    for fn in RULES:
        try:
            e = fn(world, ctx)
        except Exception:  # noqa: BLE001
            e = None
        if e:
            forms.append(e)
    return {
        "generator": GENERATOR,
        "seed": _seed_of(world, seed),
        "hash": _hash(forms),
        "senses": ctx["senses"],
        "forms": forms,
        "summary": {
            "n_forms": len(forms),
            "sound_speed": ctx["senses"]["sound_speed"],
            "peak_nm": ctx["senses"]["lambda_nm"],
            "day_hours": ctx["senses"]["day_hours"],
        },
    }


def _hash(forms: list) -> str:
    payload = json.dumps(
        [{"id": e["id"], "t": e["title"], "x": e["text"]} for e in forms],
        ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]


def stored(world: dict) -> dict:
    return _dict(world.get("aesthetic"))


def check(world: dict) -> dict:
    ch = stored(world)
    if not ch:
        return {"ok": False, "hash_ok": None, "self_ok": None, "stale": [],
                "why": "aesthetic 不存在（未跑过 aesthetic --write）",
                "stored_hash": None, "now_hash": None, "content_hash": None}
    forms = [e for e in _list(ch.get("forms")) if isinstance(e, dict)]
    now = derive(world, seed=ch.get("seed"))
    stored_hash = str(ch.get("hash") or "")
    content_hash = _hash(forms)
    self_ok = content_hash == stored_hash
    hash_ok = self_ok and stored_hash == now["hash"]
    stale = []
    for e in forms:
        bad = [p for p in _list(e.get("src"))
               if isinstance(p, str) and not ws.resolve_path(world, p)[0]]
        if bad:
            stale.append({"id": e.get("id"), "title": e.get("title"), "bad": bad})
    why = ""
    if not self_ok:
        why = "存档内容与自己的 hash 对不上：艺术评论被手改过"
    elif not hash_ok:
        why = "存档 hash 与重推结果不一致：改了世界没重跑 --write"
    elif stale:
        why = f"{len(stale)} 条的依据字段已不存在"
    return {"ok": hash_ok and not stale, "hash_ok": hash_ok, "self_ok": self_ok,
            "stale": stale, "why": why, "stored_hash": stored_hash,
            "content_hash": content_hash, "now_hash": now["hash"]}


# ════════════════════════════════════════════════════════════════════
# 呈现
# ════════════════════════════════════════════════════════════════════

_KIND = [
    ("vision", "◆ 视觉"),
    ("music", "◆ 音乐"),
    ("arch", "◆ 建筑与城市"),
    ("letter", "◆ 文学"),
    ("ritual", "◆ 仪式"),
    ("work", "◆ 一件作品"),
]


def format_report(d: dict, world: dict) -> str:
    name = str(_dict(world.get("meta")).get("name") or "这个世界")
    s = _dict(d.get("senses"))
    forms = [e for e in _list(d.get("forms")) if isinstance(e, dict)]
    L = [f"【盘古 · 艺术】{name}", "-" * 62]
    L.append(f"  声速 {_num(s.get('sound_speed')):g} m/s（地球的 {_num(s.get('sound_ratio')):.2f} 倍）"
             f" ｜ 光谱峰值 {_num(s.get('lambda_nm')):.0f} nm")
    L.append(f"  重力 {_num(s.get('gravity_g')):.2f} g ｜ 日长 {_num(s.get('day_hours')):g} h"
             f" ｜ {int(_num(s.get('n_sun')))} 颗恒星 ｜ 倾角 {_num(s.get('tilt')):g}°")
    L.append("-" * 62)
    for kind, head in _KIND:
        items = [e for e in forms if e.get("kind") == kind]
        if not items:
            continue
        L.append(f"\n{head}")
        for e in items:
            tone = "●" if e.get("strength") == "必然" else "○"
            L.append(f"  {tone} {e.get('id')} {e.get('title')}")
            for line in _wrap(str(e.get("text") or "").replace("**", ""), 56):
                L.append("      " + line)
    L.append("\n" + "-" * 62)
    L.append(f"  共 {len(forms)} 条 ｜ hash {d.get('hash')} ｜ 生成器 {d.get('generator')}")
    L.append("  口径：声速与波长是真算的；形式是「这个感官条件下最优解」的合理外推，标 ○。")
    return "\n".join(L)


def to_markdown(d: dict, world: dict, heading: bool = True) -> str:
    name = str(_dict(world.get("meta")).get("name") or "这个世界")
    s = _dict(d.get("senses"))
    forms = [e for e in _list(d.get("forms")) if isinstance(e, dict)]
    L = [f"### 艺术 · {name}", ""] if heading else []
    L.append(f"- 声速 {_num(s.get('sound_speed')):g} m/s ｜ "
             f"光谱峰值 {_num(s.get('lambda_nm')):.0f} nm ｜ "
             f"重力 {_num(s.get('gravity_g')):.2f} g ｜ hash `{d.get('hash')}`")
    L.append("")
    for e in forms:
        L.append(f"- **{e.get('id')} {e.get('title')}**（{e.get('strength')}）")
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
