# -*- coding: utf-8 -*-
"""
盘古 · 世界模型核心
===================
纯函数模块：结构校验、天体物理计算、公理库解析。无 IO 副作用（除显式 load）。

对外接口：
    load(path)              -> dict
    compute_derived(world)  -> dict
    validate(world)         -> Report
    format_report(report)   -> str
    axiom_library(root)     -> list[dict]
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

# ── 物理常数（地球基准） ────────────────────────────────────────────
EARTH_RADIUS_KM = 6371.0
EARTH_MASS_KG = 5.972e24
EARTH_DENSITY_GCC = 5.514
G_EARTH = 6.67430e-11
EARTH_G = 9.807
AU_KM = 1.495978707e8
SOLAR_LUM = 3.828e26

# ── 判定阈值 ────────────────────────────────────────────────────────
TOL_FOUR_NUMBERS = 0.03      # 四数自洽容差
TOL_KEPLER = 0.15            # 开普勒容差
TOL_CALENDAR = 0.05          # 历法一致容差
TOL_ROTATION = 0.10          # 自转一致容差
BINARY_SAFE = 2.5            # 双星稳定保守系数
BINARY_MIN = 2.0             # 双星稳定绝对下限

DIMENSIONS = ("structure", "energy", "observation", "evolution", "narrative",
              "quantitative")

# 引擎版本：doctor 用它和 SKILL / README / CHANGELOG / MCP 对齐（1.1.3）
VERSION = "1.1.6"


# ════════════════════════════════════════════════════════════════════
# 基础工具
# ════════════════════════════════════════════════════════════════════

def _num(v: Any, default: float = 0.0) -> float:
    """安全取数：接受 int/float/数字字符串，失败返回 default。"""
    if isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", v)
        if m:
            try:
                return float(m.group(0))
            except ValueError:
                return default
    return default


def _parse_first(s: Any) -> Optional[float]:
    """从 '6.674e-11 m3kg-1s-2' 这类字符串里取出第一个数。"""
    if s is None:
        return None
    if isinstance(s, (int, float)) and not isinstance(s, bool):
        return float(s)
    if isinstance(s, str):
        m = re.search(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", s)
        if m:
            try:
                return float(m.group(0))
            except ValueError:
                return None
    return None


def _get(d: Any, *keys, default=None):
    """安全多级取值。"""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur


# ════════════════════════════════════════════════════════════════════
# 点路径解析（切片引用 / 红队靶点 / CA 规则溯源 共用）
# ════════════════════════════════════════════════════════════════════

_SEG_RE = re.compile(r"^([^\[\]\.]+)((?:\[\d+\])*)$")


def parse_path(path: Any) -> list:
    """
    把 'cosmology.bodies[0].mass_earth' 拆成 ['cosmology', 'bodies', 0, 'mass_earth']。

    路径非法时抛 ValueError。1.1.2 起对外公开：patch / sweep / diff 与三处引用
    （切片 cites、红队 target、CA source）共用同一套路径文法，避免各写一份。
    """
    if not isinstance(path, str) or not path.strip():
        return []
    tokens = []
    for seg in path.strip().split("."):
        seg = seg.strip()
        if not seg:
            continue
        m = _SEG_RE.match(seg)
        if not m:
            raise ValueError(f"路径段无法解析：{seg}")
        tokens.append(m.group(1))
        for idx in re.findall(r"\[(\d+)\]", m.group(2) or ""):
            tokens.append(int(idx))
    return tokens


def resolve_path(root: Any, path: Any):
    """
    解析 'cosmology.sky_phenomena[0]' 形式的点路径（支持下标）。

    返回 (found: bool, value: Any, error: str)。

    这是 1.1 三件新功能的公共地基：
      · narrative.slice.cites     —— 切片引用了哪些字段
      · consistency.redteam[].target —— 红队打的是哪个字段
      · biology.evolution.rules[].source —— CA 规则出自哪个字段
    """
    if not isinstance(path, str) or not path.strip():
        return False, None, "路径为空"
    if root is None:
        return False, None, "数据源为空"

    try:
        tokens = parse_path(path)
    except ValueError as e:
        return False, None, str(e)
    if not tokens:
        return False, None, "路径无有效段"

    cur = root
    walked = []
    for t in tokens:
        if isinstance(t, int):
            if not isinstance(cur, (list, tuple)):
                return False, None, f"{'.'.join(walked)} 不是数组，无法取下标 [{t}]"
            if t >= len(cur):
                return False, None, f"{'.'.join(walked)}[{t}] 越界（长度 {len(cur)}）"
            cur = cur[t]
            walked.append(f"[{t}]")
        else:
            if not isinstance(cur, dict):
                return False, None, f"{'.'.join(walked)} 不是对象，无法取字段 {t}"
            if t not in cur:
                return False, None, f"字段不存在：{'.'.join(walked + [t])}"
            cur = cur[t]
            walked.append(t)
    return True, cur, ""


def _count_cjk(text: str) -> int:
    """去标点后的字符数（汉字、字母、数字都算一个字）。"""
    if not isinstance(text, str):
        return 0
    return len(re.findall(r"[\w\u4e00-\u9fff]", text))


def phenomenon_names(world: dict) -> dict:
    """
    收集「抬头能看见的现象」的可匹配名。返回 {现象名: [别名...]}。

    来源两处：
      1. sky_phenomena 里的「……」书名号短语（作者写现象时惯用的命名位）
      2. cosmology.sky_phenomena_aliases 显式声明的别名表
    """
    cos = world.get("cosmology") or {}
    sky = cos.get("sky_phenomena") or []
    out = {}
    for s in sky:
        if not isinstance(s, str):
            continue
        for m in re.findall(r"「([^」]{1,16})」", s):
            out.setdefault(m, [])
    aliases = cos.get("sky_phenomena_aliases")
    if isinstance(aliases, dict):
        for k, v in aliases.items():
            out.setdefault(str(k), [])
            if isinstance(v, (list, tuple)):
                out[str(k)].extend(str(x) for x in v)
            elif v:
                out[str(k)].append(str(v))
    return out


# ════════════════════════════════════════════════════════════════════
# 报告结构
# ════════════════════════════════════════════════════════════════════

@dataclass
class Check:
    id: str
    dim: str
    question: str
    verdict: str          # pass | warn | fatal | skip
    note: str = ""

    def as_dict(self) -> dict:
        return {"id": self.id, "dim": self.dim, "question": self.question,
                "verdict": self.verdict, "note": self.note}


@dataclass
class Report:
    checks: list = field(default_factory=list)
    derived: dict = field(default_factory=dict)
    missing: list = field(default_factory=list)

    @property
    def fatal(self) -> int:
        return sum(1 for c in self.checks if c.verdict == "fatal")

    @property
    def warn(self) -> int:
        return sum(1 for c in self.checks if c.verdict == "warn")

    @property
    def score(self) -> int:
        s = 100 - 25 * self.fatal - 4 * self.warn - 2 * len(self.missing)
        return max(0, min(100, s))

    @property
    def grade(self) -> str:
        s = self.score
        if s >= 90:
            return "可发表"
        if s >= 75:
            return "可用"
        if s >= 60:
            return "需修"
        return "重造"

    def by_dim(self, dim: str) -> list:
        return [c for c in self.checks if c.dim == dim]

    def as_dict(self) -> dict:
        return {
            "score": self.score,
            "grade": self.grade,
            "fatal": self.fatal,
            "warn": self.warn,
            "missing": self.missing,
            "checks": [c.as_dict() for c in self.checks],
            "derived": self.derived,
        }


# ════════════════════════════════════════════════════════════════════
# 读取
# ════════════════════════════════════════════════════════════════════

def load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    # 容忍注释与尾逗号（作者手写时常见）
    raw = re.sub(r"^\s*//.*$", "", raw, flags=re.M)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        cleaned = re.sub(r",(\s*[}\]])", r"\1", raw)
        return json.loads(cleaned)


# ════════════════════════════════════════════════════════════════════
# 派生量计算
# ════════════════════════════════════════════════════════════════════

def g_ratio(world: dict) -> float:
    """世界引力常数 / 地球引力常数。默认 1.0。"""
    consts = _get(world, "physics", "constants", default=[]) or []
    for c in consts:
        if not isinstance(c, dict):
            continue
        if str(c.get("symbol", "")).strip().upper() in ("G", "引力常数", "G_GRAV"):
            wv = _parse_first(c.get("world_value"))
            ev = _parse_first(c.get("earth_value")) or G_EARTH
            if wv and ev:
                ratio = wv / ev
                if 0.01 <= ratio <= 100:
                    return ratio
    return 1.0


def total_luminosity(world: dict) -> float:
    stars = _get(world, "cosmology", "stars", default=[]) or []
    return sum(_num(s.get("luminosity_solar"), 0.0) for s in stars if isinstance(s, dict))


def star_hierarchy(world: dict) -> dict:
    """
    识别恒星层级构型。
    返回 {pair_ids, sep, pair_mass, mass_total, outer_ids}：
      · 取轨道半长轴最小的两颗，若比值 ≤3 则判为内层双星，sep = 两者 a 之和
      · 其余归为外层层级伴星（绕内双星质心公转，二体近似只用 pair_mass）
    """
    stars = [s for s in (_get(world, "cosmology", "stars", default=[]) or [])
             if isinstance(s, dict)]
    orbiters = [s for s in stars if _num(_get(s, "orbit", "a_au"), 0) > 0]
    res = {"pair_ids": [], "sep": None, "pair_mass": 0.0,
           "mass_total": sum(_num(s.get("mass_solar"), 0) for s in stars),
           "outer_ids": []}
    if len(orbiters) >= 2:
        srt = sorted(orbiters, key=lambda s: _num(_get(s, "orbit", "a_au"), 0))
        a0 = _num(_get(srt[0], "orbit", "a_au"), 0)
        a1 = _num(_get(srt[1], "orbit", "a_au"), 0)
        if a0 > 0 and a1 > 0 and a1 <= a0 * 3.0:
            res["pair_ids"] = [srt[0].get("id"), srt[1].get("id")]
            res["sep"] = a0 + a1
            res["pair_mass"] = (_num(srt[0].get("mass_solar"), 0)
                                + _num(srt[1].get("mass_solar"), 0))
            res["outer_ids"] = [s.get("id") for s in srt[2:]]
    return res


def binary_separation(world: dict) -> Optional[float]:
    """双星间距（AU）= 内层两颗星到质心距离之和。无内层双星时返回 None。"""
    return star_hierarchy(world)["sep"]


# 推荐偏离带：低于下限 = 换皮，高于上限 = 读者放弃。
WEIRD_BAND = (40, 70)


def weirdness(world: dict) -> dict:
    """
    反常识度指数（0–100）。

    改太少是地球换皮，改太多是噪声。本函数把「偏离地球」拆成八类可数项，
    每类封顶，加总后与 WEIRD_BAND 比较：

        常数改写 ≤32（每条 8）｜ 新相互作用 ≤18（每条 6）
        定律偏离 ≤16（每条 4）｜ 守恒破缺 ≤16（每条 8）
        另类生化 ≤18（每项 6）｜ 虚构元素 ≤12（每条 4）
        时空尺度 ≤18（每项 6）｜ 天体构型 ≤12（每项 6）

    这是**信息量指标，不是质量指标**：100 分不代表好，40 以下才代表没改动。
    """
    phys = world.get("physics") or {}
    bio = world.get("biology") or {}
    cos = world.get("cosmology") or {}
    chem = world.get("chemistry") or {}
    items = []

    def add(name: str, points: float, detail: str) -> None:
        if points > 0:
            items.append({"name": name, "points": round(points, 1),
                          "detail": detail or "—"})

    # 1. 常数改写
    changed = []
    for c in phys.get("constants") or []:
        if not isinstance(c, dict):
            continue
        wv = _parse_first(c.get("world_value"))
        ev = _parse_first(c.get("earth_value"))
        if wv is None or not ev:
            continue
        ratio = wv / ev
        if abs(ratio - 1) > 1e-3:
            changed.append(f"{c.get('symbol', '?')}={ratio:.3g}×")
    add("常数改写", min(32, 8 * len(changed)), "、".join(changed))

    # 2. 新相互作用
    ni = [i for i in (phys.get("new_interactions") or []) if isinstance(i, dict)]
    add("新相互作用", min(18, 6 * len(ni)),
        "、".join(str(i.get("name", "?")) for i in ni[:4]))

    # 3. 定律偏离（"标准/未改"不算）
    devs = []
    for l in phys.get("laws") or []:
        if not isinstance(l, dict):
            continue
        dev = str(l.get("deviation") or "").strip()
        if dev and not re.match(r"^(标准|未改|无改动|无$|完整保留)", dev):
            devs.append(f"{l.get('name', '?')}：{dev}")
    add("定律偏离", min(16, 4 * len(devs)), "；".join(devs[:3]))

    # 4. 守恒 / 对称性破缺
    bs = phys.get("broken_symmetries")
    if isinstance(bs, list) and bs:
        add("守恒破缺", min(16, 8 * len(bs)),
            "；".join(str(x)[:24] for x in bs[:3]))

    # 5. 另类生化（能量货币 / 遗传载体 / 生命基座）
    alt = []
    for key, label in (("energy_currency", "能量货币"), ("genetic_carrier", "遗传载体")):
        v = bio.get(key)
        nm = (v.get("name") if isinstance(v, dict) else str(v or "")).strip()
        if nm and not re.search(r"(?i)\b(ATP|DNA|RNA)\b|碳基|水基", nm):
            alt.append(f"{label}：{nm}")
    bic = bio.get("biochemistry") if isinstance(bio.get("biochemistry"), dict) else {}
    base = str(bic.get("base") or "").strip()
    if base and not re.fullmatch(r"碳基|碳", base):
        alt.append(f"基座：{base}")
    add("另类生化", min(18, 6 * len(alt)), "；".join(alt))

    # 5b. 虚构元素
    els = [e for e in (chem.get("fictional_elements") or []) if isinstance(e, dict)]
    add("虚构元素", min(12, 4 * len(els)),
        "、".join(str(e.get("symbol") or e.get("name") or "?") for e in els[:4]))

    # 6. 时空尺度（日长 / 年长 / 表面重力）
    cal = cos.get("calendar") or {}
    anom = []
    day = _num(cal.get("day_hours"), 0)
    if day and abs(day - 24) / 24 > 0.10:
        anom.append(f"一天 {day:g} 小时")
    year = _num(cal.get("year_days"), 0)
    if year and abs(year - 365.25) / 365.25 > 0.10:
        anom.append(f"一年 {year:g} 天")
    bodies = [b for b in (cos.get("bodies") or []) if isinstance(b, dict)]
    body_ids = {b.get("id") for b in bodies}
    planets = [b for b in bodies if str(_get(b, "orbit", "parent", default="")) not in body_ids]
    if planets:
        g = _num(planets[0].get("gravity_g"), 0)
        if g and abs(g - 1) > 0.10:
            anom.append(f"表面 {g:g} g")
    add("时空尺度", min(18, 6 * len(anom)), "；".join(anom))

    # 7. 天体构型
    stars = [s for s in (cos.get("stars") or []) if isinstance(s, dict)]
    struct = []
    if not stars:
        struct.append("无恒星")
    elif len(stars) >= 3:
        struct.append(f"{len(stars)} 颗恒星")
    elif len(stars) == 2:
        struct.append("双星")
    if len(planets) >= 2:
        struct.append(f"{len(planets)} 颗行星")
    add("天体构型", min(12, 6 * len(struct)), "；".join(struct))

    score = int(round(min(100, sum(i["points"] for i in items))))
    lo, hi = WEIRD_BAND
    label = ("仍是地球换皮" if score < lo
             else ("推荐区间" if score <= hi else "超出可理解范围"))
    return {"score": score, "band": [lo, hi], "label": label, "items": items}


def _fraction(v) -> float:
    """成分占比：支持 0.78 / "78%" / "78" 三种写法。"""
    if isinstance(v, str):
        s = v.strip()
        pct = s.endswith("%")
        s = s.replace("%", "").strip()
        try:
            x = float(s)
        except ValueError:
            return 0.0
        return x / 100.0 if (pct or x > 1.0) else x
    return _num(v, 0.0)


# 地球基准：420 ppm CO₂ + 1.9 ppm CH₄ + 0.33 ppm N₂O ≈ 560 ppm CO₂e，对应 33 K 温室
EARTH_CO2E_PPM = 420.0 + 28.0 * 1.9 + 265.0 * 0.33
GREENHOUSE_BASE_K = 33.0
CLIMATE_SENSITIVITY = 4.28  # K per e-fold；×ln2 = 2.97 K/2×CO₂（AR6 最佳估计 3.0）


def estimate_greenhouse(body: dict):
    """由大气成分估算温室增温（K）。返回 (K, 依据)。

    口径：ΔT = 33 + 4.28·ln(CO₂e/560)，再把气压按 (P/101.325)^0.15 放大。
    只认长寿命温室气体（CO₂/CH₄/N₂O/SF₆）；水汽是反馈量，按 0.5 权重计入。
    没有成分数据时返回 (0, "none")——等于退回「只有平衡温度」的旧行为。
    """
    atm = body.get("atmosphere") if isinstance(body.get("atmosphere"), dict) else {}
    comp = atm.get("composition") if isinstance(atm.get("composition"), dict) else {}
    if not comp:
        return 0.0, "none"

    def ppm(*keys) -> float:
        for k in keys:
            if k in comp:
                return _fraction(comp[k]) * 1e6
        return 0.0

    co2e = (ppm("CO2", "co2", "二氧化碳")
            + 28.0 * ppm("CH4", "ch4", "甲烷")
            + 265.0 * ppm("N2O", "n2o", "一氧化二氮")
            + 23500.0 * ppm("SF6", "sf6")
            + 0.5 * ppm("H2O", "h2o", "水汽"))
    if co2e <= 0:
        return 0.0, "none"

    p = _num(atm.get("surface_pressure_kpa"), 101.325) or 101.325
    gh = GREENHOUSE_BASE_K + CLIMATE_SENSITIVITY * math.log(co2e / EARTH_CO2E_PPM)
    gh *= (max(1.0, p) / 101.325) ** 0.15
    return max(0.0, gh), "composition"


def compute_derived(world: dict) -> dict:
    """对每个天体算出密度、重力、逃逸速度、平衡温度、温室与恒星寿命。"""
    gr = g_ratio(world)
    lt = total_luminosity(world)
    out = {"g_ratio": round(gr, 4), "total_luminosity": round(lt, 4),
           "binary_sep_au": None, "bodies": [], "stars": [],
           "weirdness": weirdness(world)}

    # 恒星主序寿命 t ≈ 10 Gyr × M/L（M、L 均以太阳为单位）
    for s in (_get(world, "cosmology", "stars", default=[]) or []):
        if not isinstance(s, dict):
            continue
        m = _num(s.get("mass_solar"), 0) or 1.0
        lum = _num(s.get("luminosity_solar"), 0) or (m ** 3.5 if m > 0 else 1.0)
        life = (10.0 * m / lum) if lum > 0 else 0.0
        out["stars"].append({
            "id": s.get("id", "?"), "name": s.get("name", "?"),
            "mass_solar": m, "luminosity_solar": lum,
            "ms_lifetime_gyr": round(life, 2),
            "note": "寿命短于 1 Gyr，复杂生命来不及" if life and life < 1.0 else "",
        })
    if lt > 0:
        out["hz_au"] = [round(math.sqrt(lt / 1.1), 3), round(math.sqrt(lt / 0.53), 3)]

    sep = binary_separation(world)
    if sep:
        out["binary_sep_au"] = round(sep, 4)

    for b in _get(world, "cosmology", "bodies", default=[]) or []:
        if not isinstance(b, dict):
            continue
        r_km = _num(b.get("radius_km"), 0)
        r_e = _num(b.get("radius_earth"), 0) or (r_km / EARTH_RADIUS_KM if r_km else 0)
        m_e = _num(b.get("mass_earth"), 0)

        rho = (m_e * EARTH_DENSITY_GCC / (r_e ** 3)) if r_e > 0 else 0.0
        g = (m_e / (r_e ** 2) * gr) if r_e > 0 else 0.0
        v_esc = 11.19 * math.sqrt(m_e / r_e) if r_e > 0 else 0.0

        # 卫星不直接受恒星辐照，平衡温度由母星决定，此处不计
        body_ids = {x.get("id") for x in (_get(world, "cosmology", "bodies", default=[]) or [])
                    if isinstance(x, dict)}
        parent = str(_get(b, "orbit", "parent", default=""))
        is_sat = parent in body_ids and parent != b.get("id")

        a = _num(_get(b, "orbit", "a_au"), 0)
        alb = _num(b.get("albedo"), 0.3)
        # 温室：声明值优先（作者决策），否则由成分估（1.1.4 增补）
        gh_decl = _num(_get(b, "atmosphere", "greenhouse_delta_k"), 0)
        gh_est, gh_why = estimate_greenhouse(b)
        gh = gh_decl if gh_decl > 0 else gh_est
        gh_src = "declared" if gh_decl > 0 else gh_why
        t_eq = 0.0
        if (not is_sat) and a > 0 and lt > 0:
            x = (1.0 - alb) * lt / (a * a)
            if x > 0:
                t_eq = 278.6 * (x ** 0.25)
        t_surf = (t_eq + gh) if t_eq else 0.0

        out["bodies"].append({
            "id": b.get("id", "?"),
            "name": b.get("name", "?"),
            "is_satellite": is_sat,
            "radius_earth": round(r_e, 3),
            "mass_earth": round(m_e, 3),
            "density_gcc_calc": round(rho, 3),
            "density_gcc_declared": _num(b.get("density_gcc"), 0) or None,
            "gravity_g_calc": round(g, 3),
            "gravity_g_declared": _num(b.get("gravity_g"), 0) or None,
            "v_escape_km_s": round(v_esc, 2),
            "radius_km_calc": round(r_e * EARTH_RADIUS_KM, 1),
            "a_au": a,
            "t_eq_k": round(t_eq, 1),
            "greenhouse_delta_k": round(gh, 1),
            "greenhouse_declared_k": round(gh_decl, 1) if gh_decl > 0 else None,
            "greenhouse_estimated_k": round(gh_est, 1) if gh_est > 0 else None,
            "greenhouse_source": gh_src,
            "t_surface_k": round(t_surf, 1),
        })
    return out


# ════════════════════════════════════════════════════════════════════
# 校验
# ════════════════════════════════════════════════════════════════════

def _score_label(ok: bool, warn_only: bool = False) -> str:
    if ok:
        return "pass"
    return "warn" if warn_only else "fatal"


def validate(world: dict, strict: bool = False) -> Report:
    rep = Report()
    add = lambda *a, **k: rep.checks.append(Check(*a, **k))

    cos = world.get("cosmology") or {}
    phys = world.get("physics") or {}
    bio = world.get("biology") or {}
    seed = world.get("seed") or {}
    meta = world.get("meta") or {}
    nar = world.get("narrative") or {}
    con = world.get("consistency") or {}

    # ── 缺失段统计 ──────────────────────────────────────────────────
    for key in ("mathematics", "chemistry", "biology", "civilization"):
        if world.get(key) is None:
            rep.missing.append(key)

    # ── 三律（灵魂检查）──────────────────────────────────────────────
    paradox = str(seed.get("core_paradox") or "").strip()
    add("L01", "structure", "逆行律：是否存在明确的反常识悖论？",
        "pass" if paradox else "fatal",
        paradox or "seed.core_paradox 为空——这个世界没有被违反的常识，是换皮")

    interactions = phys.get("new_interactions") or []
    has_cost = any(str(i.get("cost") or "").strip() for i in interactions if isinstance(i, dict))
    consts = phys.get("constants") or []
    has_why = any(str(c.get("why") or "").strip() for c in consts if isinstance(c, dict))
    add("L02", "energy", "代价律：反常识是否标了价？",
        "pass" if (has_cost or has_why) else "warn",
        "已标价" if (has_cost or has_why) else "new_interactions 缺 cost、constants 缺 why，免费奇观")

    sky = cos.get("sky_phenomena") or []
    add("L03", "observation", "痕迹律：居民抬头能看见什么异常？",
        "pass" if sky else "warn",
        "；".join(str(s) for s in sky[:3]) if sky else "cosmology.sky_phenomena 为空")

    # ── S01 meta ────────────────────────────────────────────────────
    need = ["id", "name", "version", "created"]
    miss = [k for k in need if not str(meta.get(k) or "").strip()]
    ok_id = bool(re.match(r"^[a-z0-9][a-z0-9_\-]*$", str(meta.get("id") or "")))
    if miss:
        add("S01", "structure", "meta 必填字段齐全？", "fatal", "缺少：" + ", ".join(miss))
    elif not ok_id:
        add("S01", "structure", "meta 必填字段齐全？", "warn", "id 建议用纯小写字母/数字/下划线")
    else:
        add("S01", "structure", "meta 必填字段齐全？", "pass", f"{meta.get('name')} v{meta.get('version')}")

    # ── S02 bodies ──────────────────────────────────────────────────
    bodies = cos.get("bodies") or []
    if not bodies:
        add("S02", "structure", "是否存在天体？", "fatal", "cosmology.bodies 为空")
    else:
        bad = []
        for b in bodies:
            if not isinstance(b, dict):
                bad.append("<非对象>")
                continue
            lack = [f for f in ("id", "name", "kind", "radius_km", "mass_earth")
                    if b.get(f) in (None, "")]
            if lack:
                bad.append(f"{b.get('id', '?')}(缺 {','.join(lack)})")
        if bad:
            add("S02", "structure", "天体必填字段齐全？", "fatal", "；".join(bad))
        else:
            add("S02", "structure", "天体必填字段齐全？", "pass", f"{len(bodies)} 个天体")

    # ── S03 biomes ──────────────────────────────────────────────────
    bio_issues = []
    for b in bodies:
        if not isinstance(b, dict):
            continue
        bs = b.get("biomes") or []
        if not bs:
            continue
        elevs = []
        for x in bs:
            if not isinstance(x, dict):
                continue
            e = _num(x.get("elevation"), -1)
            if e < 0 or e > 1:
                bio_issues.append(f"{b.get('id')} elevation 越界 {e}")
            elevs.append(e)
        if elevs != sorted(elevs):
            bio_issues.append(f"{b.get('id')} biomes 未按 elevation 升序")
        if len(bs) > 8:
            bio_issues.append(f"{b.get('id')} 群系 {len(bs)} 个，超出 3D 上限 8（将截断）")
    add("S03", "structure", "生物群系分布合法？",
        "pass" if not bio_issues else "warn",
        "；".join(bio_issues) if bio_issues else "正常")

    # ── M10–M11 行星地图（1.1.1）────────────────────────────────────
    pm_bodies = [b for b in bodies if isinstance(b, dict)
                 and isinstance(b.get("planet_map"), dict)]
    if not pm_bodies:
        add("M10", "observation", "行星地图摘要可机检？", "skip",
            "未生成地图（pangu.py map --run --write --yes 后才有）")
    else:
        probs = []
        for b in pm_bodies:
            pm = b["planet_map"]
            st = pm.get("summary") if isinstance(pm.get("summary"), dict) else {}
            if not st:
                probs.append(f"{b.get('id')} 缺 summary")
                continue
            try:
                of = float(st.get("ocean_fraction"))
                mt = float(st.get("mean_temperature_k"))
                me = float(st.get("max_elevation_km"))
                rc = int(st.get("river_cells", 0))
            except (TypeError, ValueError):
                probs.append(f"{b.get('id')} summary 数值不可解析")
                continue
            if not (0.0 <= of <= 1.0):
                probs.append(f"{b.get('id')} 海洋占比越界 {of}")
            if not (50.0 <= mt <= 1000.0):
                probs.append(f"{b.get('id')} 均温越界 {mt} K")
            if me <= 0:
                probs.append(f"{b.get('id')} 最高峰非正 {me}")
            if rc <= 0:
                probs.append(f"{b.get('id')} 没有河流（水循环断了？）")
            if not str(pm.get("hash") or ""):
                probs.append(f"{b.get('id')} 缺复算哈希")
            coarse = pm.get("coarse") if isinstance(pm.get("coarse"), dict) else {}
            cnx, cny = int(_num(coarse.get("nx"), 0)), int(_num(coarse.get("ny"), 0))
            if cnx > 0 and cny > 0:
                for key in ("habitat", "temperature", "elevation", "ocean"):
                    if len(str(coarse.get(key) or "")) != cnx * cny:
                        probs.append(f"{b.get('id')} coarse.{key} 长度不符 {cnx}×{cny}")
        add("M10", "observation", "行星地图摘要可机检？",
            "pass" if not probs else "warn",
            "地图摘要自洽" if not probs else "；".join(probs[:4]))

    add("M11", "observation", "地图是否喂给了生态演化？",
        "pass" if any(isinstance(b.get("planet_map"), dict)
                      and b["planet_map"].get("coarse") for b in bodies
                      if isinstance(b, dict)) else "skip",
        "有 coarse 场，CA 可按图分布" if any(
            isinstance(b.get("planet_map"), dict) and b["planet_map"].get("coarse")
            for b in bodies if isinstance(b, dict)) else "未生成 coarse 场")

    # ── S04 开普勒（恒星）────────────────────────────────────────────
    stars = cos.get("stars") or []
    kep_issues = []
    hier = star_hierarchy(world)
    sep, pair_mass, m_tot = hier["sep"], hier["pair_mass"], hier["mass_total"]
    for s in stars:
        if not isinstance(s, dict):
            continue
        a = _num(_get(s, "orbit", "a_au"), 0)
        p_days = _num(_get(s, "orbit", "period_days"), 0)
        if a <= 0 or p_days <= 0:
            continue
        # 双星成员用相对轨道（P² = D³/M_pair）；层级伴星用 P² = a³/M_pair（内层总质量）
        if sep and s.get("id") in hier["pair_ids"]:
            a_eff, m_eff = sep, pair_mass
        elif sep and pair_mass > 0:
            a_eff, m_eff = a, pair_mass
        else:
            a_eff, m_eff = a, m_tot
        if a_eff <= 0 or m_eff <= 0:
            continue
        p_exp = math.sqrt(a_eff ** 3 / m_eff) * 365.25
        if p_exp > 0 and abs(p_days - p_exp) / p_exp > TOL_KEPLER:
            kep_issues.append(
                f"{s.get('id')}: 声明 {p_days:.1f}d / 推算 {p_exp:.1f}d")
    add("S04", "structure", "恒星轨道满足开普勒第三定律？",
        "pass" if not kep_issues else "warn",
        "；".join(kep_issues) if kep_issues else "一致")

    # ── P01 四数自洽 ────────────────────────────────────────────────
    derived = compute_derived(world)
    rep.derived = derived
    four_issues, four_fatal = [], False
    for d in derived["bodies"]:
        rho_c, rho_d = d["density_gcc_calc"], d["density_gcc_declared"]
        g_c, g_d = d["gravity_g_calc"], d["gravity_g_declared"]
        if rho_d and rho_c and abs(rho_d - rho_c) / rho_c > TOL_FOUR_NUMBERS:
            four_issues.append(f"{d['id']} 密度声明 {rho_d} ≠ 推算 {rho_c:.2f}")
            four_fatal = True
        if g_d and g_c and abs(g_d - g_c) / g_c > TOL_FOUR_NUMBERS:
            four_issues.append(f"{d['id']} 重力声明 {g_d} ≠ 推算 {g_c:.2f}")
            four_fatal = True
        # 岩石行星半径硬上限：仅当未改动 G 时才视为未偿还的债
        if (d["radius_earth"] > 2.2 and d["density_gcc_calc"] > 4.0
                and not gr_ratio_ok(derived)):
            four_issues.append(
                f"{d['id']} 半径 {d['radius_earth']}R⊕ 且岩石密度，"
                f"现实中会吸积成迷你海王星——需在 physics 声明支撑机制（如下调 G）")
    add("P01", "structure", "质量/半径/密度/重力四者自洽？",
        "fatal" if four_fatal else ("warn" if four_issues else "pass"),
        "；".join(four_issues) if four_issues else "四数吻合")

    # ── P02 重力范围 ────────────────────────────────────────────────
    g_bad = [f"{d['id']}={d['gravity_g_calc']}g" for d in derived["bodies"]
             if d["gravity_g_calc"] and not (0.05 <= d["gravity_g_calc"] <= 4.0)]
    add("P02", "structure", "表面重力在可演化生命区间？",
        "pass" if not g_bad else "warn",
        "；".join(g_bad) + "（超出 0.05–4 g，需说明生命形态）" if g_bad else "正常")

    # ── P03 双星稳定 ────────────────────────────────────────────────
    sep = derived.get("binary_sep_au")
    if sep:
        p_issues, p_fatal = [], False
        for b in bodies:
            if not isinstance(b, dict):
                continue
            a = _num(_get(b, "orbit", "a_au"), 0)
            if a <= 0:
                continue
            parent = str(_get(b, "orbit", "parent", default=""))
            # 只检查绕双星质心的天体
            star_parents = {str(_get(s, "orbit", "parent", default="")) for s in stars
                            if isinstance(s, dict) and _get(s, "orbit", "parent")}
            if parent and parent not in star_parents and parent not in ("", "AB", "AB-bary"):
                continue
            k = a / sep
            if k < BINARY_MIN:
                p_issues.append(f"{b.get('id')} a/双星间距={k:.2f} < {BINARY_MIN}，轨道将被甩飞")
                p_fatal = True
            elif k < BINARY_SAFE:
                p_issues.append(f"{b.get('id')} a/双星间距={k:.2f} < {BINARY_SAFE}，长期不稳定")
        add("P03", "structure", "环双星轨道稳定？",
            "fatal" if p_fatal else ("warn" if p_issues else "pass"),
            "；".join(p_issues) if p_issues else f"间距 {sep} AU，轨道安全")
    else:
        add("P03", "structure", "环双星轨道稳定？", "skip", "非双星系统，跳过")

    # ── P04 洛希极限（卫星）─────────────────────────────────────────
    roche_issues = []
    body_by_id = {b.get("id"): b for b in bodies if isinstance(b, dict)}
    for b in bodies:
        if not isinstance(b, dict):
            continue
        parent = str(_get(b, "orbit", "parent", default=""))
        if parent in body_by_id and parent != "":
            host = body_by_id[parent]
            r_p = _num(_get(host, "radius_km"), 0)
            rho_p = _num(_get(host, "density_gcc"), 0) or EARTH_DENSITY_GCC
            rho_s = _num(_get(b, "density_gcc"), 0) or EARTH_DENSITY_GCC
            a_au = _num(_get(b, "orbit", "a_au"), 0)
            if r_p > 0 and rho_s > 0 and a_au > 0:
                d_roche = 2.44 * r_p * (rho_p / rho_s) ** (1 / 3)
                d_actual = a_au * AU_KM
                if d_actual < d_roche:
                    roche_issues.append(
                        f"{b.get('id')} 轨道 {d_actual:.0f} km < 洛希极限 {d_roche:.0f} km")
    add("P04", "structure", "卫星未被潮汐撕裂？",
        "fatal" if roche_issues else "pass",
        "；".join(roche_issues) if roche_issues else "无卫星或超限")

    # ── E01 表面温度（1.1：改用含温室补偿的表面温度判定）────────────
    t_bad = [f"{d['id']}={d['t_surface_k']}K" for d in derived["bodies"]
             if d["t_surface_k"] and not (150 <= d["t_surface_k"] <= 400)]
    t_notes = []
    for d in derived["bodies"]:
        if not d["t_surface_k"]:
            continue
        gh = d.get("greenhouse_delta_k") or 0
        t_notes.append(f"{d['id']} T_eq={d['t_eq_k']}K"
                       + (f"+温室{gh:g}→{d['t_surface_k']}K" if gh else f"→{d['t_surface_k']}K"))
    add("E01", "energy", "表面温度能否支持液态溶剂？",
        "pass" if not t_bad else "warn",
        ("；".join(t_bad) + "（150–400 K 之外，需温室/地热补偿）") if t_bad else
        "；".join(t_notes) or "无法计算")

    # ── E02 营养级 ──────────────────────────────────────────────────
    tl = (bio.get("trophic_levels") or []) if isinstance(bio, dict) else []
    if tl:
        ssum = sum(_num(t.get("share"), 0) for t in tl if isinstance(t, dict))
        add("E02", "energy", "营养级份额之和接近 1？",
            "pass" if 0.9 <= ssum <= 1.1 else "warn",
            f"合计 {ssum:.2f}")
    else:
        add("E02", "energy", "营养级份额之和接近 1？", "skip", "未定义营养级")

    # ── E03 气压 ────────────────────────────────────────────────────
    p_bad = []
    for b in bodies:
        if not isinstance(b, dict):
            continue
        atm = b.get("atmosphere")
        if not isinstance(atm, dict):
            continue
        p = _num(atm.get("surface_pressure_kpa"), 0)
        if p and not (20 <= p <= 500):
            p_bad.append(f"{b.get('id')}={p} kPa")
    add("E03", "energy", "表面气压在可呼吸/可存活区间？",
        "pass" if not p_bad else "warn",
        "；".join(p_bad) + "（超出 20–500 kPa）" if p_bad else "正常")

    # ── K01 元素配比 ────────────────────────────────────────────────
    chem = world.get("chemistry") if isinstance(world.get("chemistry"), dict) else {}
    comp = chem.get("composition") if isinstance(chem.get("composition"), dict) else {}
    mix_issues, mix_fatal = [], False

    def _mix_check(label: str, mix: Any) -> None:
        nonlocal mix_fatal
        if not isinstance(mix, dict) or not mix:
            return
        vals = []
        for k, v in mix.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                mix_issues.append(f"{label}.{k} 不是数值")
                mix_fatal = True
                continue
            if v < 0:
                mix_issues.append(f"{label}.{k} 为负")
                mix_fatal = True
                continue
            vals.append(v)
        if not vals:
            return
        s = sum(vals)
        if s <= 0:
            mix_issues.append(f"{label} 合计为 0")
            mix_fatal = True
            return
        dev = abs(s - 1.0)
        if dev > 0.05:
            mix_issues.append(f"{label} 合计 {s:.3f}（偏离 >5%）")
            mix_fatal = True
        elif dev > 0.02:
            mix_issues.append(f"{label} 合计 {s:.3f}（偏离 >2%）")

    _mix_check("行星本体", comp.get("planet"))
    _mix_check("大气", comp.get("atmosphere"))
    _mix_check("海洋", comp.get("ocean"))

    bic = bio.get("biochemistry") if isinstance(bio.get("biochemistry"), dict) else {}
    _mix_check("生命基座", bic.get("composition"))
    for o in bio.get("organisms") or []:
        if isinstance(o, dict):
            _mix_check(f"{o.get('name') or o.get('id') or '物种'}", o.get("composition"))
    add("K01", "structure", "元素配比之和为 1？",
        "fatal" if mix_fatal else ("warn" if mix_issues else "pass"),
        "；".join(mix_issues) if mix_issues else "行星 / 大气 / 生命配比均归一")

    # ── K02 虚构元素命名 ────────────────────────────────────────────
    els = [e for e in (chem.get("fictional_elements") or []) if isinstance(e, dict)]
    el_issues, el_fatal = [], False
    seen_ids, seen_syms = set(), set()
    for i, e in enumerate(els):
        eid = str(e.get("id") or "").strip()
        sym = str(e.get("symbol") or "").strip()
        glyph = str(e.get("glyph") or "").strip()
        comp_ch = str(e.get("component") or "").strip()
        if not eid:
            el_issues.append(f"第 {i + 1} 条缺 id")
        elif eid in seen_ids:
            el_issues.append(f"id 重复：{eid}")
            el_fatal = True
        seen_ids.add(eid)
        if not sym:
            el_issues.append(f"{eid or i} 缺 symbol")
        elif sym in seen_syms:
            el_issues.append(f"symbol 重复：{sym}")
            el_fatal = True
        seen_syms.add(sym)
        m = GLYPH_RE.match(glyph)
        if not m:
            el_issues.append(f"{eid or i} 字形「{glyph}」不符合 气+钅+单字")
            el_fatal = True
        else:
            ch = m.group(1)
            if comp_ch and comp_ch != ch:
                el_issues.append(f"{eid} component={comp_ch} 与字形 {glyph} 不一致")
                el_fatal = True
        phase = str(e.get("phase_at_surface") or "").strip()
        if phase and phase not in ("气", "液", "固", "等离子", "超临界"):
            el_issues.append(f"{eid} 相态「{phase}」不在 气/液/固/等离子/超临界")
        ab = e.get("abundance_ppm")
        if ab is None or not isinstance(ab, (int, float)) or ab < 0:
            el_issues.append(f"{eid} 缺 abundance_ppm 或为负")
        if not str(e.get("role") or "").strip():
            el_issues.append(f"{eid} 缺 role（它在生态里干什么）")
    add("K02", "structure", "虚构元素按「气+钅+单字」命名且唯一？",
        "skip" if not els else ("fatal" if el_fatal else ("warn" if el_issues else "pass")),
        "；".join(el_issues) if el_issues else (f"{len(els)} 个新元素，字形合法" if els else "未定义虚构元素"))

    # ── K03 生命基座 ────────────────────────────────────────────────
    base_issues = []
    if bic:
        base = str(bic.get("base") or "").strip()
        primary = str(bic.get("primary_element") or "").strip()
        if not base:
            base_issues.append("缺 base（碳基 / 硅基 / 其他基）")
        if not primary:
            base_issues.append("缺 primary_element")
        else:
            planet_mix = comp.get("planet") if isinstance(comp.get("planet"), dict) else {}
            if planet_mix and primary not in planet_mix:
                base_issues.append(f"行星配比里没有主元素「{primary}」")
            mix = bic.get("composition") if isinstance(bic.get("composition"), dict) else {}
            if mix and _num(mix.get(primary), 0) < 0.01:
                base_issues.append(f"生命配比中「{primary}」不足 1%")
        if not str(bic.get("solvent") or "").strip():
            base_issues.append("缺 solvent")
        for o in bio.get("organisms") or []:
            if not isinstance(o, dict) or not o.get("playable"):
                continue
            name = o.get("name") or o.get("id") or "物种"
            if _num(o.get("height_m"), 0) <= 0:
                base_issues.append(f"{name} 缺 height_m（第一人称眼高无法定）")
            loco = o.get("locomotion")
            if not isinstance(loco, dict) or _num(loco.get("speed_ms"), 0) <= 0:
                base_issues.append(f"{name} 缺 locomotion.speed_ms（无法操控行走）")
    add("K03", "evolution", "生命基座与可操控物种声明完整？",
        "skip" if not bic else ("warn" if base_issues else "pass"),
        "；".join(base_issues) if base_issues else
        (f"基座：{bic.get('base')}；主元素：{bic.get('primary_element')}" if bic else "未定义 biochemistry"))

    # ── R01 选项卡互斥（1.1.3）──────────────────────────────────────
    brief = seed.get("brief") if isinstance(seed.get("brief"), dict) else {}
    choices = [c for c in (brief.get("choices") or []) if isinstance(c, dict)]
    if not choices:
        add("R01", "narrative", "已采纳的选项卡互不矛盾？", "skip",
            "未采纳选项卡（seed.brief.choices 为空）——1.1.3 可选能力")
    else:
        r01 = []
        for i, c in enumerate(choices):
            if not str(c.get("qid") or "").strip():
                r01.append(f"第 {i + 1} 张缺 qid")
            if not str(c.get("option") or c.get("label") or "").strip():
                r01.append(f"第 {i + 1} 张缺 option / label")
            if not str(c.get("cost") or "").strip():
                r01.append(f"{c.get('qid') or i + 1} 没写代价——免费奇观")
        r01 += card_conflicts(choices)
        r01 += card_world_mismatch(choices, world)
        add("R01", "narrative", "已采纳的选项卡互不矛盾？",
            "pass" if not r01 else "warn",
            "；".join(r01) if r01 else f"{len(choices)} 张卡，无互斥")

    # ── O01 年长一致 ────────────────────────────────────────────────
    cal = cos.get("calendar") or {}
    y_days = _num(cal.get("year_days"), 0)
    main = bodies[0] if bodies and isinstance(bodies[0], dict) else {}
    p_orb = _num(_get(main, "orbit", "period_days"), 0)
    if y_days and p_orb:
        ok = abs(y_days - p_orb) / p_orb <= TOL_CALENDAR
        add("O01", "observation", "历法年长与轨道周期一致？", "pass" if ok else "warn",
            f"历法 {y_days}d / 轨道 {p_orb}d")
    else:
        add("O01", "observation", "历法年长与轨道周期一致？", "skip", "数据不足")

    # ── O02 日长一致 ────────────────────────────────────────────────
    d_h = _num(cal.get("day_hours"), 0)
    rot = _num(main.get("rotation_hours"), 0)
    if d_h and rot:
        ok = abs(d_h - rot) / rot <= TOL_ROTATION
        add("O02", "observation", "历法日长与自转周期一致？", "pass" if ok else "warn",
            f"历法 {d_h}h / 自转 {rot}h")
    elif d_h and main.get("rotation_hours") is None:
        add("O02", "observation", "历法日长与自转周期一致？", "warn",
            "潮汐锁定世界不应有常规昼夜，需说明「日」的定义")
    else:
        add("O02", "observation", "历法日长与自转周期一致？", "skip", "数据不足")

    # ── O03 / O04 地面视角（1.1）────────────────────────────────────
    surf = cos.get("surface")
    if not isinstance(surf, dict):
        add("O03", "observation", "地面观察点合法？", "skip", "未定义 cosmology.surface")
        add("O04", "observation", "地面视角有可观测的恒星？", "skip",
            "未定义 cosmology.surface")
    else:
        obs = surf.get("observer") if isinstance(surf.get("observer"), dict) else {}
        lat = _num(obs.get("lat_deg"), 0.0) if obs else 0.0
        lon = _num(obs.get("lon_deg"), 0.0) if obs else 0.0
        o03_bad = []
        if obs and not (-90.0 <= lat <= 90.0):
            o03_bad.append(f"纬度 {lat} 越界")
        if obs and not (-180.0 <= lon <= 180.0):
            o03_bad.append(f"经度 {lon} 越界")
        add("O03", "observation", "地面观察点合法？",
            "pass" if not o03_bad else "warn",
            "；".join(o03_bad) if o03_bad else
            (f"观察点 {lat}°, {lon}°" if obs else "未指定观察点，地面视图取赤道"))

        star_ids = {s.get("id") for s in stars if isinstance(s, dict)}
        ref_ids = surf.get("star_ids") or []
        bad_ref = [str(r) for r in ref_ids if r not in star_ids]
        if not star_ids:
            add("O04", "observation", "地面视角有可观测的恒星？", "warn",
                "cosmology.stars 为空，地面视图将降级为数据视图")
        elif bad_ref:
            add("O04", "observation", "地面视角有可观测的恒星？", "warn",
                "surface.star_ids 指向不存在的恒星：" + "、".join(bad_ref))
        else:
            add("O04", "observation", "地面视角有可观测的恒星？", "pass",
                f"{len(star_ids)} 颗恒星可观测")

    # ── SK01 / SK02 观测层（1.1.4）──────────────────────────────────
    # 与 sky --check 同源：缺省星表时 skip，旧世界不掉分。
    try:
        import sky as _sky  # 延迟导入，避免 world_schema ↔ sky 的循环依赖
        _ck = _sky.check(world)
        for _c in _ck["checks"]:
            if _c["id"] not in ("S01", "S02"):
                continue
            _v = {"pass": "pass", "skip": "skip"}.get(_c["status"], "warn")
            add("SK" + _c["id"][1:], "observation",
                "星表可复算？" if _c["id"] == "S01" else "星空摘要与星表一致？",
                _v, _c["note"])
    except Exception as _e:  # noqa: BLE001
        add("SK01", "observation", "星表可复算？", "skip",
            f"观测层不可用：{type(_e).__name__}")
        add("SK02", "observation", "星空摘要与星表一致？", "skip", "同上")

    # ── N01 叙事 ────────────────────────────────────────────────────
    nar_miss = [k for k in ("three_seconds", "setpiece", "hook")
                if not str(nar.get(k) or "").strip()]
    add("N01", "narrative", "叙事三件套是否齐全？", "pass" if not nar_miss else "warn",
        "缺少：" + ", ".join(nar_miss) if nar_miss else "齐全")

    # ── N02 参考文献 ────────────────────────────────────────────────
    refs = seed.get("references") or []
    weak = [r for r in refs if isinstance(r, dict) and not str(r.get("use") or "").strip()]
    if len(refs) >= 4 and not weak:
        add("N02", "narrative", "检索依据是否充分且被使用？", "pass", f"{len(refs)} 条")
    elif refs:
        add("N02", "narrative", "检索依据是否充分且被使用？", "warn",
            f"{len(refs)} 条（需 ≥4）" + (f"，{len(weak)} 条缺 use 字段" if weak else ""))
    else:
        add("N02", "narrative", "检索依据是否充分且被使用？", "warn", "无检索记录")

    # ── N03–N06 第一人称切片（1.1）──────────────────────────────────
    sl = nar.get("slice") if isinstance(nar.get("slice"), dict) else None
    sl_text = str(sl.get("text") or "").strip() if sl else ""
    if sl is None or not sl_text:
        add("N03", "narrative", "第一人称切片是否可交付？",
            "fatal" if strict else "skip",
            "缺少 narrative.slice.text——世界还没落到人的感官层" if strict
            else "未定义 narrative.slice（1.1 可选能力）")
        add("N04", "narrative", "切片引用能全部解析？", "skip", "无切片")
        add("N05", "narrative", "切片里出现了抬头可见的现象？", "skip", "无切片")
        add("N06", "narrative", "切片时序与历法对得上？", "skip", "无切片")
    else:
        n = _count_cjk(sl_text)
        n03_bad = []
        if not (180 <= n <= 260):
            n03_bad.append(f"字数 {n}，要求 180–260")
        if str(sl.get("status") or "draft").strip() != "ok":
            n03_bad.append(f"status={sl.get('status', 'draft')}，交付需 ok")
        add("N03", "narrative", "第一人称切片是否可交付？",
            "pass" if not n03_bad else ("fatal" if strict else "warn"),
            "；".join(n03_bad) if n03_bad else f"{n} 字，已定稿")

        cites = sl.get("cites") or []
        bad_cites = []
        for c in cites:
            okk, _, why = resolve_path(world, c)
            if not okk:
                bad_cites.append(f"{c}（{why}）")
        add("N04", "narrative", "切片引用能全部解析？",
            "pass" if not bad_cites else "warn",
            "；".join(bad_cites) if bad_cites else f"{len(cites)} 条引用全部命中")

        hits = []
        for nm, al in phenomenon_names(world).items():
            for cand in [nm] + list(al or []):
                if cand and cand in sl_text:
                    hits.append(nm)
                    break
        add("N05", "narrative", "切片里出现了抬头可见的现象？",
            "pass" if len(hits) >= 2 else "warn",
            "命中 " + "、".join(sorted(set(hits))) if hits else
            "切片里没有任何 sky_phenomena 现象——居民没抬头")

        d_h0 = _num(cal.get("day_hours"), 0)
        y_d0 = _num(cal.get("year_days"), 0)
        hrs = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*(?:个)?(?:小时|时辰)", sl_text)]
        dys = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*(?:个)?(?:天|昼夜)", sl_text)]
        t_bad = []
        if d_h0:
            t_bad += [f"切片写 {x:g} 小时，历法日长 {d_h0:g} 小时"
                      for x in hrs if abs(x - d_h0) / d_h0 > 0.15]
        if y_d0:
            t_bad += [f"切片写 {x:g} 天，历法年长 {y_d0:g} 天"
                      for x in dys if abs(x - y_d0) / y_d0 > 0.15]
        add("N06", "narrative", "切片时序与历法对得上？",
            "pass" if not t_bad else "warn",
            "；".join(t_bad) if t_bad else "时序与历法一致")

    # ── N07 / N08 红队审查（1.1）────────────────────────────────────
    rt = con.get("redteam") if isinstance(con.get("redteam"), list) else []
    if not rt:
        add("N07", "narrative", "红队质疑是否成军？",
            "fatal" if strict else "skip",
            "缺少 consistency.redteam——没有对手的世界经不起拷问" if strict
            else "未定义 consistency.redteam（1.1 可选能力）")
        add("N08", "narrative", "红队质疑是否全部有结论？", "skip", "无红队")
    else:
        bad_targets = []
        for r in rt:
            if not isinstance(r, dict):
                bad_targets.append("非对象条目")
                continue
            okk, _, why = resolve_path(world, r.get("target"))
            if not okk:
                bad_targets.append(f"{r.get('id', '?')}→{r.get('target')}（{why}）")
        n07_bad = list(bad_targets)
        if len(rt) < 5:
            n07_bad.append(f"仅 {len(rt)} 条，建议 ≥5")
        add("N07", "narrative", "红队质疑是否成军？",
            "pass" if not n07_bad else "warn",
            "；".join(n07_bad) if n07_bad else f"{len(rt)} 条，靶点全部可解析")

        opens = [r for r in rt
                 if isinstance(r, dict) and str(r.get("verdict") or "open").strip() == "open"]
        add("N08", "narrative", "红队质疑是否全部有结论？",
            "pass" if not opens else ("fatal" if strict else "warn"),
            (f"{len(opens)} 条仍为 open：" +
             "、".join(str(r.get("id", "?")) for r in opens[:4])) if opens else "全部有结论")

    # ── N09–N11 生态演化（1.1）─────────────────────────────────────
    evo = bio.get("evolution") if isinstance(bio, dict) else None
    if not isinstance(evo, dict):
        add("N09", "evolution", "生态演化模型可编译？", "skip", "未定义 biology.evolution")
        add("N10", "evolution", "演化结果落地到设定里了吗？", "skip", "未定义 biology.evolution")
        add("N11", "evolution", "周期性灾变有演化证据吗？", "skip", "未定义 biology.evolution")
    else:
        prog = None
        try:
            import ca_engine as _ca  # 延迟导入：无 evolution 的世界不加载 CA 引擎
            prog = _ca.compile_evolution(evo, world)
        except Exception as e:  # noqa: BLE001
            add("N09", "evolution", "生态演化模型可编译？", "warn",
                f"CA 引擎不可用：{type(e).__name__}: {e}")
        if prog is not None:
            if prog.errors:
                add("N09", "evolution", "生态演化模型可编译？", "warn",
                    f"{len(prog.errors)} 处规则矛盾：" + "；".join(prog.errors[:3]))
            else:
                add("N09", "evolution", "生态演化模型可编译？", "pass",
                    f"{len(prog.states)} 态 / {len(prog.rules)} 条规则 / "
                    f"{len(prog.forcing)} 项外部强迫")

            impacts = evo.get("impacts") or []
            good_imp = [i for i in impacts
                        if isinstance(i, dict) and str(i.get("target") or "").strip()]
            add("N10", "evolution", "演化结果落地到设定里了吗？",
                "pass" if good_imp else "warn",
                f"{len(good_imp)} 处落地：" + "、".join(
                    str(i.get("target")) for i in good_imp[:3]) if good_imp else
                "CA 跑完却没改动任何 trophic_levels / sky_phenomena——只是装饰图")

            cyc = _num(_get(evo, "summary", "cycle_steps"), 0)
            periodic = [s for s in sky if isinstance(s, str)
                        and re.search(r"每\s*[\d一二三四五六七八九十百]+\s*(?:天|日|月)", s)]
            if not periodic:
                add("N11", "evolution", "周期性灾变有演化证据吗？", "skip",
                    "sky_phenomena 未提及周期灾变")
            elif cyc <= 0:
                add("N11", "evolution", "周期性灾变有演化证据吗？", "warn",
                    f"sky_phenomena 有 {len(periodic)} 处周期描述，但 cycle_steps={cyc:g}")
            else:
                hps = _num(_get(evo, "clock", "hours_per_step"), 0)
                if hps > 0:
                    add("N11", "evolution", "周期性灾变有演化证据吗？", "pass",
                        f"cycle_steps={cyc:g} ≈ {cyc * hps / 24.0:.1f} 天"
                        f"（一步 {hps:g} 小时）")
                else:
                    add("N11", "evolution", "周期性灾变有演化证据吗？", "warn",
                        "clock.hours_per_step 缺失，演化周期无法换算成天")

    # ── C01–C03 守恒与定量（1.1.5）──────────────────────────────────
    try:
        import conservation as _cons
        led = _cons.ledger(world)
    except Exception:  # noqa: BLE001 —— 账本跑不动不该把整个校验拖死
        led = None
    if led is None or not led["scored"]:
        add("C01", "quantitative", "守恒账本配平了吗？", "skip",
            "可算的账不足（缺半径 / 大气 / 水量）")
    elif led["ok"]:
        add("C01", "quantitative", "守恒账本配平了吗？", "pass",
            f"{led['scored']} 本账配平，{led['info']} 本储库只报不算")
    elif not led.get("unexplained"):
        # 声明值压过模型（如声明温室）→ 1.1.4 的口径是「只报不改」，不算自相矛盾
        add("C01", "quantitative", "守恒账本配平了吗？", "pass",
            f"{led['scored']} 本账，{len(led['explained'])} 本由声明值压过模型"
            f"（{'、'.join(led['explained'])}；只报不改，改不改由你定）")
    else:
        bad = [r for r in led["rows"]
               if r["status"] == "warn" and not r.get("explained")]
        add("C01", "quantitative", "守恒账本配平了吗？", "warn",
            "；".join(f"{r['id']} {r['name']} 残差 {r['residual']:+.1%}" for r in bad[:3]))

    try:
        import units as _un
        hard = []
        _bodies = _get(world, "cosmology", "bodies", default=[]) or []
        _b0 = _bodies[0] if _bodies and isinstance(_bodies[0], dict) else {}
        _atm = _get(_b0, "atmosphere", default={}) or {}
        for _src in (_b0, _atm):
            if not isinstance(_src, dict):
                continue
            for _k, _v in _src.items():
                if isinstance(_v, bool) or not isinstance(_v, (int, float)):
                    continue
                _st, _msg = _un.check(_k, _v)
                if _st == "hard":
                    hard.append(_msg)
        if hard:
            add("C02", "quantitative", "数值落在物理硬域内吗？", "warn",
                "；".join(hard[:3]))
        else:
            add("C02", "quantitative", "数值落在物理硬域内吗？", "pass",
                "天体与大气字段均通过量纲硬域")
    except Exception:  # noqa: BLE001
        add("C02", "quantitative", "数值落在物理硬域内吗？", "skip", "量纲层不可用")

    cert = world.get("certification") if isinstance(world, dict) else None
    if not isinstance(cert, dict):
        add("C03", "quantitative", "定量结论标注了来源吗？", "skip",
            "还没跑 certify：哪些是算的、哪些是拍的还没分开")
    else:
        cov = _num(cert.get("coverage"), 0)
        add("C03", "quantitative", "定量结论标注了来源吗？",
            "pass" if cov >= 0.3 else "warn",
            f"覆盖率 {cov:.0%}（算出来的 / 关键结论）")

    # ── X01 遗留问题 ────────────────────────────────────────────────
    issues = con.get("open_issues") or []
    add("X01", "structure", "是否有未解决的遗留问题？", "pass" if not issues else "warn",
        "；".join(str(i) for i in issues[:3]) if issues else "无")

    # ── X02 物理层存在 ──────────────────────────────────────────────
    if not phys or not (phys.get("constants") or phys.get("laws")):
        add("X02", "structure", "物理层是否已立？", "fatal",
            "physics 缺失或为空——违反了「律先于物」")
    else:
        add("X02", "structure", "物理层是否已立？", "pass",
            f"{len(phys.get('constants') or [])} 条常数，{len(phys.get('laws') or [])} 条定律")

    # ── 回写分数 ────────────────────────────────────────────────────
    if isinstance(con, dict):
        con["score"] = rep.score
    return rep


def gr_ratio_ok(derived: dict) -> bool:
    """辅助：G 被显著下调时，大半径岩石行星才说得通。"""
    return derived.get("g_ratio", 1.0) < 0.95


# ════════════════════════════════════════════════════════════════════
# 报告格式化
# ════════════════════════════════════════════════════════════════════

ICON = {"pass": "✓", "warn": "!", "fatal": "✗", "skip": "·"}
DIM_CN = {"structure": "结构", "energy": "能量", "observation": "观测",
          "evolution": "演化", "narrative": "叙事", "quantitative": "定量"}


def format_report(rep: Report, verbose: bool = True) -> str:
    lines = []
    lines.append("=" * 62)
    lines.append(f"  盘古 · 自洽性审查   总分 {rep.score}/100  [{rep.grade}]")
    lines.append(f"  fatal {rep.fatal} ｜ warn {rep.warn} ｜ 缺失段 {len(rep.missing)}")
    lines.append("=" * 62)

    if verbose:
        for dim in DIMENSIONS:
            cs = rep.by_dim(dim)
            if not cs:
                continue
            lines.append("")
            lines.append(f"【{DIM_CN[dim]}】")
            for c in cs:
                lines.append(f"  {ICON.get(c.verdict, '?')} {c.id}  {c.question}")
                if c.note and c.verdict != "pass":
                    lines.append(f"      └ {c.note}")

    d = rep.derived
    if d and d.get("bodies"):
        lines.append("")
        lines.append("【派生量】")
        for b in d["bodies"]:
            tag = "（卫星）" if b.get("is_satellite") else ""
            teq = f"{b['t_eq_k']}K" if b["t_eq_k"] else "—"
            lines.append(f"  {b['name']}{tag}")
            lines.append(
                f"    R={b['radius_earth']}R⊕ · M={b['mass_earth']}M⊕ · "
                f"ρ={b['density_gcc_calc']}g/cc · g={b['gravity_g_calc']}g")
            lines.append(
                f"    v_esc={b['v_escape_km_s']}km/s · T_eq={teq}")
        lines.append(f"  G'/G={d['g_ratio']} ｜ 系统总光度={d['total_luminosity']}L☉"
                     + (f" ｜ 双星间距={d['binary_sep_au']}AU" if d.get("binary_sep_au") else ""))
        w = d.get("weirdness") or {}
        if w:
            lo, hi = w.get("band", (40, 70))
            lines.append(f"  反常识度 {w.get('score')}/100（推荐 {lo}–{hi}，{w.get('label')}）"
                         + ("：" + "、".join(f"{i['name']}{i['points']:g}"
                                            for i in (w.get("items") or [])[:5])
                            if w.get("items") else ""))

    if rep.missing:
        lines.append("")
        lines.append(f"【未开的斧】{', '.join(rep.missing)}")

    if rep.fatal:
        lines.append("")
        lines.append("【必须修】")
        for c in rep.checks:
            if c.verdict == "fatal":
                lines.append(f"  ✗ {c.id} {c.question} — {c.note}")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════
# 公理库
# ════════════════════════════════════════════════════════════════════

DOMAIN_BY_PREFIX = {
    "P": ("physics", "物理"),
    "C": ("cosmos", "宇宙"),
    "M": ("math", "数学"),
    "K": ("chemistry", "化学"),
    "B": ("biology", "生物"),
    "V": ("civilization", "文明"),
}

# 代价类型二次索引：创作时想的不是「哪个学科」，而是「我想让世界付出什么代价」。
COST_TAGS = (
    ("时间", r"寿命|年长|年纪|衰老|永生|瞬间|秒|分钟|小时|一天|周期|计时|时代|世代|时间|历史|迟到"),
    ("空间", r"距离|远行|迁徙|空间|地平线|边界|半径|轨道|星系|不可达|到不了|无法到|跨越|高度|深度"),
    ("能量", r"能量|热量|温度|功率|辐照|输运|供能|耗能|熵|发电|光合|日照|冷|暖"),
    ("物质", r"物质|元素|矿物|材料|密度|金属|重石|资源|稀有|水|大气|化学|相态|晶体"),
    ("感知", r"视觉|颜色|光谱|声音|听觉|看见|看不到|亮度|影|方向|感知|认知|记忆|语言|数|几何|痛觉"),
    ("社会", r"社会|文明|政治|阶级|权力|宗教|制度|城市|贸易|通信|协作|礼仪|战争|人口|技术|历法"),
    ("生命", r"生物|生命|繁殖|代谢|细胞|基因|遗传|物种|生态|疾病|神经|脑|血肉|呼吸|食物"),
    ("结构", r"稳定|坍缩|解体|潮汐|洛希|地震|地壳|共振|刚性|屈服|承压|引力|自转|轨道稳定"),
)


def cost_tags(text: str) -> list:
    """按代价类型给一条积木打标签（0–4 个，按 COST_TAGS 顺序）。"""
    blob = str(text or "")
    return [tag for tag, pat in COST_TAGS if re.search(pat, blob)]


# ── 虚构元素的命名文法（1.1.2）──────────────────────────────────────
# 「气」半包围（左上包围）+ 「钅」+ 一个自选单字。
# 这样造出来的字既不是气体也不是金属，而是两者的夹缝——正是新元素该在的位置。
GLYPH_PREFIX = "⿸气⿰钅"
GLYPH_RE = re.compile(r"^⿸气⿰钅([\u4e00-\u9fff])$")
COMPONENT_POOL = ("辰", "昷", "参", "离", "玄", "敄", "玆", "咢", "肃", "既")


def fictional_glyph(component: str) -> str:
    """
    把一个单字包成虚构元素字：'辰' → '⿸气⿰钅辰'。

    返回值是 Unicode 表意文字描述序列（IDS），能在任何文本里无损传递字形结构：
    ⿸ = 左上包围，气 = 外层偏旁，⿰ = 左右并置，钅 + 单字 = 内层。
    """
    ch = str(component or "").strip()
    if len(ch) != 1:
        raise ValueError("component 必须是单个汉字")
    return GLYPH_PREFIX + ch


def glyph_component(glyph: str) -> str:
    """从 IDS 字形里取回内嵌单字；不合法返回空串。"""
    m = GLYPH_RE.match(str(glyph or ""))
    return m.group(1) if m else ""


def card_conflicts(choices: list) -> list:
    """
    选项卡互斥检查（1.1.3）。

    选项的 `tags` 里，以 `-` 开头的标签表示「排除带这个标签的选项」。
    例：无恒星世界的选项带 `-有恒星`，双日选项带 `有恒星`。
    同一份创作简报里正负标签同时出现，就是互斥。

    返回人类可读的冲突说明（空列表 = 无冲突）。
    """
    pos, neg = {}, {}
    for c in choices or []:
        if not isinstance(c, dict):
            continue
        who = str(c.get("qid") or c.get("label") or "?")
        for t in c.get("tags") or []:
            t = str(t).strip()
            if not t:
                continue
            if t.startswith("-"):
                neg.setdefault(t[1:], []).append(who)
            else:
                pos.setdefault(t, []).append(who)
    out = []
    for tag in sorted(set(pos) & set(neg)):
        out.append(f"「{tag}」不能同时成立：{('、'.join(pos[tag]))} vs {('、'.join(neg[tag]))}")
    return out


def _fact_has_stars(w: dict) -> bool:
    return bool((w.get("cosmology") or {}).get("stars"))


def _fact_locked(w: dict) -> bool:
    bodies = [b for b in ((w.get("cosmology") or {}).get("bodies") or [])
              if isinstance(b, dict)]
    if not bodies:
        return False
    b0 = bodies[0]
    if b0.get("rotation_hours") in (None, 0):
        return True
    return bool((b0.get("planet_map") or {}).get("tidal_locked"))


def _fact_photosynthesis(w: dict) -> bool:
    return isinstance((w.get("biology") or {}).get("photosynthesis"), dict)


def _fact_water(w: dict) -> bool:
    sv = (w.get("chemistry") or {}).get("solvent")
    name = str(sv.get("name") if isinstance(sv, dict) else sv or "").strip()
    return name in ("水", "water", "H2O", "水基")


def _fact_carbon(w: dict) -> bool:
    base = str(((w.get("biology") or {}).get("biochemistry") or {}).get("base") or "")
    return "碳" in base


# 卡上的标签 → world.json 里可机检的事实。没登记的事实标签不检查（只当创作备注）。
CARD_FACTS = {
    "有恒星": _fact_has_stars,
    "锁定": _fact_locked,
    "光合": _fact_photosynthesis,
    "水溶剂": _fact_water,
    "碳基": _fact_carbon,
}


def card_world_mismatch(choices: list, world: dict) -> list:
    """
    卡与世界对不上（1.1.3）：采纳的选项说「没有恒星」，可 world.json 里写着三颗。

    选项卡只是决策记录，不改世界数据——所以这种不一致必须报出来，
    否则「我选了无恒星」和「我写了三颗恒星」会同时存在于同一个世界里。
    """
    out = []
    for c in choices or []:
        if not isinstance(c, dict):
            continue
        qid = c.get("qid") or "?"
        for raw in c.get("tags") or []:
            tag = str(raw).strip()
            neg = tag.startswith("-")
            key = tag[1:] if neg else tag
            fact = CARD_FACTS.get(key)
            if not fact:
                continue
            try:
                actual = bool(fact(world))
            except Exception:      # noqa: BLE001
                continue
            if actual != (not neg):
                out.append(f"{qid} 的「{key}」要求它{'不存在' if neg else '存在'}，"
                           f"但 world.json 里它{'存在' if actual else '不存在'}")
    return out


def axiom_library(skill_root: str) -> list:
    """解析 references/公理库.md 的表格，返回结构化积木列表。"""
    path = os.path.join(skill_root, "references", "公理库.md")
    if not os.path.exists(path):
        return []
    out = []
    row_re = re.compile(r"^\|\s*([PCMKBV]\d{2})\s*\|(.+)\|\s*$")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            m = row_re.match(line.strip())
            if not m:
                continue
            aid = m.group(1)
            cells = [c.strip() for c in m.group(2).split("|")]
            if len(cells) < 4:
                continue
            domain, domain_cn = DOMAIN_BY_PREFIX.get(aid[0], ("unknown", "未知"))
            trace = cells[3]
            scale = ""
            sm = re.search(r"\[(.+?)\]", trace)
            if sm:
                scale = sm.group(1)
                trace = trace[:sm.start()].strip() + trace[sm.end():].strip()
            trace = re.sub(r"[\s`]+$", "", trace).strip("` ")
            out.append({
                "id": aid,
                "domain": domain,
                "domain_cn": domain_cn,
                "name": cells[0],
                "setting": cells[1],
                "cost": cells[2],
                "trace": trace.strip(),
                "scale": scale,
                "cost_tags": cost_tags(" ".join(cells[:3])),
            })
    return out
