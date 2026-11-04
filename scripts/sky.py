# -*- coding: utf-8 -*-
"""
盘古 · 观测层（1.1.4 大条 A/B）
================================
「这个世界的居民抬头，到底看见什么？」

盘古已经有三层：地（map / ca / preview）、改（patch / sweep / diff / whatif）、
推（entail）。缺的第四层是**看**——`cosmology.surface.observer`、`bodies[].axial_tilt_deg`、
`stars[]` 的轨道与光度、`calendar` 的日长年长，全都已经写在 world.json 里，
只是没人把它们算成一张星图。

本模块只做四件事：

    星表   按 (seed, count, color_mix, galaxy) 确定性生成，不引真实星表
    天球   圆轨道近似，算恒星 / 行星 / 卫星的 alt-az
    天光   经验模型：空气辉光 + 暮光 + 明亮点光源散射 + 尘埃消光（±0.5 等）
    昼长   cos H0 = -tanφ·tanδ，δ = ε·sin(2π d / year)

设计约束（写死，别松）：
  · 只用标准库；新增字段全可选，旧世界不加 starfield 也能跑
  · 输出一律标「简化模型」，不把 4.1 等说成「精确 4.1 等」
  · 星表是本世界观测点的计算结果，**不是**真实天空，也不是 Gaia/HYG 的转述
  · 只报矛盾，不改世界：天象文本与实算不符时给提示，改不改是作者的设定决策
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random

import world_schema as ws

# ════════════════════════════════════════════════════════════════════
# 常数（全部是「经验值」，改之前先看 docs/开发文档-v1.1.4.md §2）
# ════════════════════════════════════════════════════════════════════

SKY_VERSION = "1.1.4"

AIRGLOW = 21.9          # 无月无暮光的暗空天光（mag/arcsec²）
SUN_SKY = 13.0          # 太阳在地平线上时的白天天光
SUN_MAG = -26.74        # 1 AU 处类太阳恒星的视星等
MOON_MAG = -12.7        # 满月视星等
MOON_SKY = 18.0         # 满月夜的天光
POINT_PENALTY = 2.5     # 点光源散射修正：同光度但张角 <10′ 时，天光弱 2.5 等
POINT_ARCMIN = 10.0     # 判「点光源」的张角阈值
LIMIT_SLOPE = 0.9       # 天光亮 1 mag/arcsec²，肉眼极限星等降 0.9 等
DARK_LIMIT = 6.5        # 暗空肉眼极限星等
TWILIGHT_DEG = 18.0     # 天文暮光结束的太阳高度角
EXTINCTION_K = 0.20     # 地平附近尘埃消光系数（按 1/sin h 放大）
HAZE_K = 0.40           # 气压每高出 1 个地球大气，夜空被散射抬亮多少等
MW_MIN_SKY = 21.0       # 银河可见的天光下限（比这更亮就被洗掉）

DEFAULT_COUNT = 2000
MAG_MIN, MAG_MAX = -1.5, 6.5
POWER_LAW = 0.45        # 星数按 10^(0.45 m) 增长
CLASS_COLORS = {
    "O": "#9BB0FF", "B": "#AABFFF", "A": "#CAD7FF", "F": "#F8F7FF",
    "G": "#FFF4EA", "K": "#FFD2A1", "M": "#FFCC6F",
}

SUN, PLANET, MOON = "@", "O", "C"
MAG_SYMBOLS = ((-1.0, "#"), (2.0, "*"), (4.0, "+"), (99.0, "."))


# ════════════════════════════════════════════════════════════════════
# 取值助手
# ════════════════════════════════════════════════════════════════════

def _dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _list(v) -> list:
    return v if isinstance(v, list) else []


def _num(v, d: float = 0.0) -> float:
    return ws._num(v, d)


def _cos(world: dict) -> dict:
    return _dict(world.get("cosmology"))


def _bodies(world: dict) -> list:
    return [b for b in _list(_cos(world).get("bodies")) if isinstance(b, dict)]


def _stars(world: dict) -> list:
    return [s for s in _list(_cos(world).get("stars")) if isinstance(s, dict)]


def _b0(world: dict) -> dict:
    """主天体：第一个不绕行其它天体的行星。"""
    bs = _bodies(world)
    ids = {b.get("id") for b in bs}
    for b in bs:
        if str(_dict(b.get("orbit")).get("parent") or "") not in ids:
            return b
    return bs[0] if bs else {}


def _satellites(world: dict) -> list:
    pid = _b0(world).get("id")
    return [b for b in _bodies(world)
            if str(_dict(b.get("orbit")).get("parent") or "") == str(pid)]


def calendar(world: dict) -> dict:
    cal = _dict(_cos(world).get("calendar"))
    body = _b0(world)
    day_h = _num(cal.get("day_hours"), _num(body.get("rotation_hours"), 24.0)) or 24.0
    year_d = _num(cal.get("year_days"), _num(_dict(body.get("orbit")).get("period_days"), 365.25))
    months = int(_num(cal.get("months"), 12)) or 12
    month_days = _num(cal.get("month_days"), year_d / months if months else year_d)
    return {"day_hours": day_h, "year_days": year_d, "months": months,
            "month_days": month_days, "epoch": str(cal.get("epoch") or ""),
            "names": [str(x) for x in _list(cal.get("month_names"))]}


def observer(world: dict) -> dict:
    surf = _dict(_cos(world).get("surface"))
    obs = _dict(surf.get("observer"))
    return {"lat": max(-90.0, min(90.0, _num(obs.get("lat_deg"), 0.0))),
            "lon": max(-180.0, min(180.0, _num(obs.get("lon_deg"), 0.0))),
            "elev": _num(obs.get("elev_m"), 0.0),
            "defined": bool(obs)}


# ════════════════════════════════════════════════════════════════════
# 星表：程序生成，可复算
# ════════════════════════════════════════════════════════════════════

def starfield_params(world: dict) -> dict:
    """读 cosmology.starfield，缺省补一份能跑的默认星表（标「未登记」）。"""
    sf = _dict(_cos(world).get("starfield"))
    seed = world.get("seed")
    base_seed = 0
    if isinstance(seed, dict):
        base_seed = int(_num(seed.get("rng_seed"), _num(seed.get("seed"), 0)))
    elif isinstance(seed, (int, float)):
        base_seed = int(seed)
    count = int(_num(sf.get("count"), DEFAULT_COUNT))
    mix = _dict(sf.get("color_mix"))
    if not mix:
        mix = {"K": 0.2, "G": 0.5, "F": 0.2, "M": 0.1}
    gal = _dict(sf.get("galaxy"))
    return {
        "seed": int(_num(sf.get("seed"), base_seed)),
        "count": max(50, min(200000, count)),
        "magnitude_dist": str(sf.get("magnitude_dist") or "power-law"),
        "color_mix": {str(k).upper(): float(v) for k, v in mix.items()},
        "galaxy": {
            "present": bool(gal.get("present", False)),
            "inclination_deg": _num(gal.get("inclination_deg"), 30.0),
            "width_deg": max(2.0, _num(gal.get("width_deg"), 15.0)),
            "brightness": max(0.0, min(1.0, _num(gal.get("brightness"), 0.5))),
        },
        "declared": bool(sf),
    }


def _mag_from_u(u: float) -> float:
    a = POWER_LAW * math.log(10.0)
    lo, hi = math.exp(a * MAG_MIN), math.exp(a * MAG_MAX)
    return math.log(lo + max(0.0, min(0.999999, u)) * (hi - lo)) / a


def _pick_class(mix: dict, u: float) -> str:
    total = sum(max(0.0, v) for v in mix.values()) or 1.0
    acc = 0.0
    for k in sorted(mix):
        acc += max(0.0, mix[k]) / total
        if u <= acc:
            return k
    return sorted(mix)[-1] if mix else "G"


def _gal_to_eq(l_deg: float, b_deg: float, inc_deg: float):
    """银道坐标 → 赤道坐标。银道面绕 x 轴倾斜 inc_deg。"""
    i = math.radians(inc_deg)
    l, b = math.radians(l_deg), math.radians(b_deg)
    e1 = (1.0, 0.0, 0.0)
    e2 = (0.0, math.cos(i), math.sin(i))
    n = (0.0, -math.sin(i), math.cos(i))
    x = math.cos(b) * math.cos(l) * e1[0] + math.cos(b) * math.sin(l) * e2[0] + math.sin(b) * n[0]
    y = math.cos(b) * math.cos(l) * e1[1] + math.cos(b) * math.sin(l) * e2[1] + math.sin(b) * n[1]
    z = math.cos(b) * math.cos(l) * e1[2] + math.cos(b) * math.sin(l) * e2[2] + math.sin(b) * n[2]
    return math.degrees(math.atan2(y, x)) % 360.0, math.degrees(math.asin(max(-1.0, min(1.0, z))))


def starfield_hash(params: dict) -> str:
    body = {k: params[k] for k in ("seed", "count", "magnitude_dist", "color_mix", "galaxy")}
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]


_CATALOG_CACHE = {}


def gen_starfield(params: dict) -> list:
    """确定性生成星表：[{ra, dec, mag, cls, color}]。同参数必得同结果。"""
    key = starfield_hash(params)
    if key in _CATALOG_CACHE:
        return _CATALOG_CACHE[key]
    rnd = random.Random(int(params["seed"]) * 1000003 + 17)
    gal = params["galaxy"]
    gal_frac = 0.35 * gal["brightness"] if gal["present"] else 0.0
    out = []
    for _ in range(int(params["count"])):
        mag = _mag_from_u(rnd.random())
        cls = _pick_class(params["color_mix"], rnd.random())
        if gal_frac and rnd.random() < gal_frac:
            # 银河带：银纬集中在 ±width/2，银经均匀
            b = rnd.gauss(0.0, gal["width_deg"] / 2.0)
            ra, dec = _gal_to_eq(rnd.random() * 360.0, max(-89.0, min(89.0, b)),
                                 gal["inclination_deg"])
            mag = min(MAG_MAX, mag + 1.6)      # 银河成员星总体更暗
        else:
            ra = rnd.random() * 360.0
            dec = math.degrees(math.asin(2.0 * rnd.random() - 1.0))
        out.append({"ra": ra, "dec": dec, "mag": round(mag, 3), "cls": cls,
                    "color": CLASS_COLORS.get(cls, "#FFFFFF")})
    _CATALOG_CACHE[key] = out
    return out


# ════════════════════════════════════════════════════════════════════
# 天球：圆轨道近似
# ════════════════════════════════════════════════════════════════════

def _obliquity(world: dict) -> float:
    return _num(_b0(world).get("axial_tilt_deg"), 23.4)


def _lst_deg(hour: float, day_hours: float, lon_deg: float = 0.0) -> float:
    """
    本地恒星时。约定 t=0 为**本地午夜**（主星在下中天）。

    这里用本地时刻，所以经度不进入天球几何——同一本地时刻，全世界看见同一片天。
    经度只影响「本地时刻 ↔ 绝对时刻」的换算，本模块不做那一步（只算一个观测点）。
    """
    return (180.0 + 360.0 * (hour / (day_hours or 24.0))) % 360.0


def _eq_to_hor(ra: float, dec: float, lst: float, lat: float):
    h = math.radians((lst - ra) % 360.0)
    d = math.radians(dec)
    p = math.radians(lat)
    sin_alt = math.sin(d) * math.sin(p) + math.cos(d) * math.cos(p) * math.cos(h)
    alt = math.degrees(math.asin(max(-1.0, min(1.0, sin_alt))))
    az = math.degrees(math.atan2(
        math.cos(d) * math.sin(h),
        math.sin(d) * math.cos(p) - math.cos(d) * math.sin(p) * math.cos(h)))
    return alt, az % 360.0


def _ecl_to_eq(x: float, y: float, z: float, eps_deg: float):
    e = math.radians(eps_deg)
    y2 = y * math.cos(e) - z * math.sin(e)
    z2 = y * math.sin(e) + z * math.cos(e)
    r = math.sqrt(x * x + y2 * y2 + z2 * z2) or 1.0
    return (math.degrees(math.atan2(y2, x)) % 360.0,
            math.degrees(math.asin(max(-1.0, min(1.0, z2 / r)))))


def _apparent_mag(lum_solar: float, dist_au: float) -> float:
    lum = max(1e-9, lum_solar)
    dist = max(1e-6, dist_au)
    return SUN_MAG - 2.5 * math.log10(lum) + 5.0 * math.log10(dist)


def _sun_positions(world: dict, hour: float) -> list:
    """恒星相对观测者的方向、距离、视星等、alt-az。"""
    cal = calendar(world)
    obs = observer(world)
    eps = _obliquity(world)
    lst = _lst_deg(hour, cal["day_hours"], obs["lon"])
    b0 = _b0(world)
    o = _dict(b0.get("orbit"))
    a_p = _num(o.get("a_au"), 0.0)
    p_p = _num(o.get("period_days"), 0.0) or cal["year_days"] or 365.25
    phi = math.pi + 2.0 * math.pi * (hour / 24.0) / p_p
    px, py = a_p * math.cos(phi), a_p * math.sin(phi)

    out = []
    for s in _stars(world):
        so = _dict(s.get("orbit"))
        a_s = _num(so.get("a_au"), 0.0)
        p_s = _num(so.get("period_days"), 0.0) or 365.25
        th = math.radians(_num(so.get("phase_deg"), 0.0)) + 2.0 * math.pi * (hour / 24.0) / p_s
        sx, sy = a_s * math.cos(th), a_s * math.sin(th)
        dx, dy = sx - px, sy - py
        dist = max(1e-6, math.hypot(dx, dy))
        ra, dec = _ecl_to_eq(dx, dy, 0.0, eps)
        alt, az = _eq_to_hor(ra, dec, lst, obs["lat"])
        radius_solar = _num(s.get("radius_solar"), 1.0)
        radius_km = radius_solar * 696000.0
        diam = math.degrees(2.0 * math.atan(radius_km / (dist * 149597870.7))) * 60.0
        out.append({
            "id": str(s.get("id") or "?"), "name": str(s.get("name") or s.get("id") or "?"),
            "kind": "star", "class": str(s.get("class") or ""),
            "color": str(s.get("color") or "#FFF6E2"),
            "alt": round(alt, 1), "az": round(az, 1),
            "dist_au": round(dist, 4),
            "mag": round(_apparent_mag(_num(s.get("luminosity_solar"), 1.0), dist), 2),
            "diam_arcmin": round(diam, 2),
            "lum": _num(s.get("luminosity_solar"), 1.0),
        })
    return out


def _moon_phase(phase_deg: float) -> tuple:
    """相位角 → (名称, 被照亮比例)。0° 为满相。"""
    a = phase_deg % 360.0
    lit = (1.0 + math.cos(math.radians(a))) / 2.0
    for lim, name in ((22.5, "满月"), (67.5, "凸月"), (112.5, "上弦"), (157.5, "蛾眉"),
                      (202.5, "新月"), (247.5, "蛾眉"), (292.5, "下弦"), (337.5, "凸月")):
        if a < lim:
            return name, lit
    return "满月", lit


def _body_positions(world: dict, hour: float) -> list:
    """卫星与其它行星：从观测行星看过去的方向。"""
    cal = calendar(world)
    obs = observer(world)
    eps = _obliquity(world)
    lst = _lst_deg(hour, cal["day_hours"], obs["lon"])
    out = []
    for b in _satellites(world):
        o = _dict(b.get("orbit"))
        a_km = _num(o.get("a_km"), 0.0)
        if a_km <= 0:
            a_au = _num(o.get("a_au"), 0.0)
            a_km = a_au * 149597870.7
        if a_km <= 0:
            continue
        p_d = _num(o.get("period_days"), 0.0) or cal["day_hours"] / 24.0
        th = math.radians(_num(o.get("phase_deg"), 0.0)) + 2.0 * math.pi * (hour / 24.0) / p_d
        dx = a_km * math.cos(th)
        dy = a_km * math.sin(th)
        dist_au = a_km / 149597870.7
        ra, dec = _ecl_to_eq(dx, dy, 0.0, eps)
        alt, az = _eq_to_hor(ra, dec, lst, obs["lat"])
        radius_km = _num(b.get("radius_km"), 0.0) or _num(b.get("radius_earth"), 0.5) * 6371.0
        diam = math.degrees(2.0 * math.atan(radius_km / max(1.0, a_km))) * 60.0
        albedo = max(0.02, _num(b.get("albedo"), 0.12))
        phase = math.degrees(th - math.pi) % 360.0
        name, lit = _moon_phase(phase)
        mag = (MOON_MAG + 5.0 * math.log10(max(0.05, diam) / 31.0)
               - 5.0 * math.log10(max(1e-3, lit)) - 2.5 * math.log10(albedo / 0.12))
        out.append({
            "id": str(b.get("id") or "?"), "name": str(b.get("name") or b.get("id") or "?"),
            "kind": "moon", "class": "", "color": str(b.get("color") or "#D8DEE9"),
            "alt": round(alt, 1), "az": round(az, 1), "dist_au": round(dist_au, 6),
            "mag": round(mag, 2), "diam_arcmin": round(diam, 2),
            "phase": name, "lit": round(lit, 2),
        })
    return out


# ════════════════════════════════════════════════════════════════════
# 天光：经验模型
# ════════════════════════════════════════════════════════════════════

def _twilight_sky(alt: float, mag: float):
    if alt <= -TWILIGHT_DEG:
        return None
    base = SUN_SKY if alt >= 0 else SUN_SKY + (AIRGLOW - SUN_SKY) * (-alt / TWILIGHT_DEG)
    base += max(0.0, (mag - SUN_MAG) * 0.5)      # 比太阳暗的恒星，白天天光也暗
    return max(SUN_SKY, min(AIRGLOW, base))


def _illuminator_sky(alt: float, mag: float, diam_arcmin: float):
    """明亮点光源（远星、巨月）对夜天光的贡献。两点标定：日面 13.0 / 满月 18.0。"""
    if alt <= 0 or mag >= -10.0:
        return None
    b = MOON_SKY + (mag - MOON_MAG) * (SUN_SKY - MOON_SKY) / (SUN_MAG - MOON_MAG)
    if diam_arcmin < POINT_ARCMIN:
        b += POINT_PENALTY
    return max(SUN_SKY, min(AIRGLOW, b))


def _combine(values: list):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return -2.5 * math.log10(sum(10 ** (-0.4 * v) for v in vals))


def _limit_from_sky(bright: float) -> float:
    return max(1.0, min(DARK_LIMIT, DARK_LIMIT - LIMIT_SLOPE * (AIRGLOW - bright)))


def _extinction(alt: float) -> float:
    if alt <= 0:
        return 99.0
    return EXTINCTION_K * (1.0 / max(0.03, math.sin(math.radians(alt))) - 1.0)


def sky_brightness(world: dict, hour: float = 0.0) -> dict:
    """天光（mag/arcsec²）+ 极限星等 + 银河可见性。数值越小越亮。"""
    suns = _sun_positions(world, hour)
    moons = _body_positions(world, hour)
    parts = {"airglow": AIRGLOW, "twilight": [], "illuminator": []}
    contributions = [AIRGLOW]
    sun_up = False
    for s in suns:
        # 真太阳（比 -20 等更亮）在地平线上 → 白天；其余亮天体走「明亮点光源」模型。
        if s["alt"] >= 0 and s["mag"] < -20.0:
            b = _twilight_sky(s["alt"], s["mag"])
            if b is not None:
                parts["twilight"].append((s["name"], round(b, 2)))
                contributions.append(b)
            sun_up = True
        elif s["alt"] < 0:
            b = _twilight_sky(s["alt"], s["mag"])
            if b is not None and b < AIRGLOW - 0.05:
                parts["twilight"].append((s["name"], round(b, 2)))
                contributions.append(b)
        b2 = _illuminator_sky(s["alt"], s["mag"], s["diam_arcmin"])
        if b2 is not None:
            parts["illuminator"].append((s["name"], round(b2, 2)))
            contributions.append(b2)
    for m in moons:
        b = _illuminator_sky(m["alt"], m["mag"], m["diam_arcmin"])
        if b is not None:
            parts["illuminator"].append((m["name"], round(b, 2)))
            contributions.append(b)
    bright = _combine(contributions) or AIRGLOW
    # 尘埃与水汽：气压越高，高空散射越多，夜空被整体抬亮（经验项）
    p_kpa = _num(_dict(_b0(world).get("atmosphere")).get("surface_pressure_kpa"), 101.3)
    haze = HAZE_K * max(0.0, p_kpa / 101.3 - 1.0)
    if haze > 0.01:
        parts["haze"] = round(haze, 2)
        bright = max(12.0, bright - haze)
    limit = _limit_from_sky(bright)
    params = starfield_params(world)
    gal = params["galaxy"]
    mw = bool(gal["present"] and bright >= MW_MIN_SKY and gal["brightness"] >= 0.3)
    obs = observer(world)
    stars = gen_starfield(params)
    vis = 0
    for st in stars:
        alt, _az = _eq_to_hor(st["ra"], st["dec"],
                              _lst_deg(hour, calendar(world)["day_hours"], obs["lon"]),
                              obs["lat"])
        if alt <= 0:
            continue
        if st["mag"] + _extinction(alt) <= limit:
            vis += 1
    return {
        "hour": round(hour, 3),
        "sky_brightness": round(bright, 2),
        "limit_mag": round(limit, 2),
        "visible_stars": vis,
        "catalog": params["count"],
        "milky_way": mw,
        "sun_up": sun_up,
        "components": parts,
    }


# ════════════════════════════════════════════════════════════════════
# 一年：昼长与季节
# ════════════════════════════════════════════════════════════════════

def _declination(day: float, year_days: float, tilt_deg: float) -> float:
    """δ = ε·sin(2π d / year)：第 0 天取春分。"""
    if year_days <= 0:
        return 0.0
    return tilt_deg * math.sin(2.0 * math.pi * day / year_days)


def daylight_hours(lat: float, dec: float, day_hours: float) -> dict:
    """昼长：cos H0 = -tanφ·tanδ；|cos H0| > 1 判极昼/极夜。"""
    if abs(lat) >= 89.999:
        lat = 89.999 if lat > 0 else -89.999
    cos_h0 = -math.tan(math.radians(lat)) * math.tan(math.radians(dec))
    if cos_h0 <= -1.0:
        return {"hours": day_hours, "polar": "极昼", "h0_deg": 180.0}
    if cos_h0 >= 1.0:
        return {"hours": 0.0, "polar": "极夜", "h0_deg": 0.0}
    h0 = math.degrees(math.acos(cos_h0))
    return {"hours": 2.0 * h0 / 360.0 * day_hours, "polar": "无", "h0_deg": h0}


def year_table(world: dict) -> dict:
    cal = calendar(world)
    obs = observer(world)
    tilt = _obliquity(world)
    rows = []
    base = sky_brightness(world, 0.0)
    for i in range(max(1, cal["months"])):
        mid = i * cal["month_days"] + cal["month_days"] / 2.0
        dec = _declination(mid, cal["year_days"], tilt)
        dl = daylight_hours(obs["lat"], dec, cal["day_hours"])
        # 极昼/极夜可能落在月中的某几天，不能只看中点
        polar_scan = set()
        for k in range(12):
            d = i * cal["month_days"] + cal["month_days"] * (k + 0.5) / 12.0
            polar_scan.add(daylight_hours(
                obs["lat"], _declination(d, cal["year_days"], tilt),
                cal["day_hours"])["polar"])
        polar = ("极昼" if "极昼" in polar_scan else
                 ("极夜" if "极夜" in polar_scan else "无"))
        noon_alt = 90.0 - abs(obs["lat"] - dec)
        # 夜半天光：主星高度按 -（90 - |φ-δ|）估；星数只随极限星等变
        sun_mid_alt = -(90.0 - abs(obs["lat"] - dec))
        name = cal["names"][i] if i < len(cal["names"]) else f"第 {i + 1} 月"
        rows.append({
            "month": i + 1, "name": name, "day": round(mid, 1),
            "declination_deg": round(dec, 1),
            "daylight_hours": round(dl["hours"], 1),
            "noon_alt_deg": round(noon_alt, 1),
            "polar": polar,
            "night_stars": _visible_at_sun_alt(world, sun_mid_alt, base),
        })
    # 极值按全年细扫，别按月中采样——否则报不出真正的至日
    hours = [r["daylight_hours"] for r in rows]
    if cal["year_days"] > 0:
        step = max(1.0, cal["year_days"] / 720.0)
        d = 0.0
        while d < cal["year_days"]:
            hours.append(daylight_hours(
                obs["lat"], _declination(d, cal["year_days"], tilt),
                cal["day_hours"])["hours"])
            d += step
    polar = [r["polar"] for r in rows if r["polar"] != "无"]
    longest = min(rows, key=lambda r: r["daylight_hours"]) if rows else None
    return {
        "tilt_deg": round(tilt, 1),
        "day_hours": round(cal["day_hours"], 2),
        "year_days": round(cal["year_days"], 1),
        "months": cal["months"],
        "lat": obs["lat"],
        "min_daylight_hours": round(min(hours), 1) if hours else 0.0,
        "max_daylight_hours": round(max(hours), 1) if hours else 0.0,
        "polar_day": "有" if "极昼" in polar else "无",
        "polar_night": "有" if "极夜" in polar else "无",
        "longest_night_month": longest["name"] if longest else "—",
        "rows": rows,
    }


def _visible_at_sun_alt(world: dict, sun_alt: float, base: dict) -> int:
    """按月估算夜可见星：只把主星的暮光项换成本月的夜半高度。"""
    parts = [AIRGLOW]
    b = _twilight_sky(sun_alt, SUN_MAG)
    if b is not None:
        parts.append(b)
    bright = _combine(parts) or AIRGLOW
    limit = _limit_from_sky(bright)
    if limit >= base["limit_mag"] - 0.05:
        return base["visible_stars"]
    params = starfield_params(world)
    obs = observer(world)
    lst = _lst_deg(0.0, calendar(world)["day_hours"], obs["lon"])
    n = 0
    for st in gen_starfield(params):
        alt, _az = _eq_to_hor(st["ra"], st["dec"], lst, obs["lat"])
        if alt > 0 and st["mag"] + _extinction(alt) <= limit:
            n += 1
    return n


# ════════════════════════════════════════════════════════════════════
# 时刻解析
# ════════════════════════════════════════════════════════════════════

def _sunset_hour(world: dict, primary_down: bool = True):
    """主星（最亮那颗）的落下时刻——不是「最后一颗太阳落下」。"""
    cal = calendar(world)
    step = max(0.05, cal["day_hours"] / 400.0)
    stars = _stars(world)
    main_id = max(stars, key=lambda s: _num(s.get("luminosity_solar"), 0.0)).get("id") if stars else None
    h = 0.0
    prev = None
    while h < cal["day_hours"]:
        pos = _sun_positions(world, h)
        pick = [s["alt"] for s in pos if s["id"] == main_id] or [s["alt"] for s in pos]
        alt = max(pick) if pick else -90.0
        if prev is not None:
            if primary_down and prev > 0 >= alt:
                return h
            if (not primary_down) and prev <= 0 < alt:
                return h
        prev = alt
        h += step
    return None


def _conjunction_hour(world: dict):
    cal = calendar(world)
    st = _stars(world)
    if len(st) < 2:
        return None
    step = max(0.05, cal["day_hours"] / 400.0)
    best, best_h = 1e9, None
    h = 0.0
    while h < cal["day_hours"]:
        p = _sun_positions(world, h)
        if len(p) >= 2:
            d = math.hypot(p[0]["alt"] - p[1]["alt"], p[0]["az"] - p[1]["az"])
            if d < best:
                best, best_h = d, h
        h += step
    return best_h


def parse_at(spec: str, world: dict) -> dict:
    """支持 "22:10" / "day=12,hour=22" / "日落后 2h" / "双星合前 30m"。"""
    import re
    cal = calendar(world)
    day = cal["day_hours"]
    if not spec:
        return {"hour": 0.0, "label": "夜半", "relative": ""}

    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", spec)
    if m:
        h = int(m.group(1)) + int(m.group(2)) / 60.0
        return {"hour": h % max(1e-6, day), "label": f"{int(m.group(1)):02d}:{m.group(2)}",
                "relative": ""}

    m = re.match(r"^\s*day\s*=\s*([\d.]+)\s*[,，]\s*hour\s*=\s*([\d.]+)\s*$", spec)
    if m:
        h = float(m.group(2))
        return {"hour": h % max(1e-6, day), "label": f"day={m.group(1)} {h:g}h",
                "relative": ""}

    m = re.match(r"^\s*日落后\s*([\d.]+)\s*(?:h|小时)?\s*$", spec)
    if m:
        ss = _sunset_hour(world, True)
        if ss is None:
            raise ValueError("这个世界的太阳整天不落，算不出「日落后」")
        h = (ss + float(m.group(1))) % day
        return {"hour": h, "label": f"日落后 {m.group(1)}h", "relative": f"日落 {ss:.2f}h"}

    m = re.match(r"^\s*(.{1,10}?)合前\s*([\d.]+)\s*(h|小时|m|分)?\s*$", spec)
    if m:
        ch = _conjunction_hour(world)
        if ch is None:
            raise ValueError("只有两颗以上的恒星才算得出「合」")
        off = float(m.group(2))
        if (m.group(3) or "h") in ("m", "分"):
            off /= 60.0
        return {"hour": (ch - off) % day, "label": f"{m.group(1)}合前 {off:g}h",
                "relative": f"合 {ch:.2f}h"}

    raise ValueError(f'看不懂的时刻写法：{spec}（可用 "22:10" / "day=12,hour=22" / '
                     f'"日落后 2h" / "双星合前 30m"）')


# ════════════════════════════════════════════════════════════════════
# 一帧星空
# ════════════════════════════════════════════════════════════════════

def frame(world: dict, hour: float = 0.0, moment: dict = None) -> dict:
    cal = calendar(world)
    obs = observer(world)
    hour = hour % max(1e-6, cal["day_hours"])
    lst = _lst_deg(hour, cal["day_hours"], obs["lon"])
    params = starfield_params(world)
    sky = sky_brightness(world, hour)
    stars = []
    for st in gen_starfield(params):
        alt, az = _eq_to_hor(st["ra"], st["dec"], lst, obs["lat"])
        if alt <= 0:
            continue
        mobs = st["mag"] + _extinction(alt)
        if mobs > sky["limit_mag"] + 0.6:
            continue
        stars.append({"alt": round(alt, 1), "az": round(az, 1),
                      "mag": round(mobs, 2), "color": st["color"]})
    stars.sort(key=lambda s: s["mag"])
    suns = _sun_positions(world, hour)
    moons = _body_positions(world, hour)
    return {
        "world": ws._get(world, "meta", "name", default=""),
        "hour": round(hour, 3),
        "moment": moment or {"hour": hour, "label": "夜半", "relative": ""},
        "observer": obs,
        "calendar": cal,
        "tilt_deg": round(_obliquity(world), 1),
        "sky": sky,
        "stars": stars,
        "suns": suns,
        "moons": moons,
        "starfield": {"count": params["count"], "declared": params["declared"],
                      "hash": starfield_hash(params)},
        "milky_way": {"present": params["galaxy"]["present"],
                      "visible": sky["milky_way"],
                      "inclination_deg": params["galaxy"]["inclination_deg"]},
        "model": "简化模型：圆轨道 + 经验天光，位置与亮度误差见文档",
    }


# ════════════════════════════════════════════════════════════════════
# 星图
# ════════════════════════════════════════════════════════════════════

def _symbol(mag: float) -> str:
    for lim, ch in MAG_SYMBOLS:
        if mag < lim:
            return ch
    return "."


def chart_ascii(fr: dict, width: int = 96, height: int = 30) -> list:
    """地平坐标星图：底边地平线，顶为天顶；30°/60° 高度圈用 · 虚线。"""
    grid = [[" "] * width for _ in range(height)]

    def put(alt, az, ch):
        if alt < 0:
            return
        cx = int(round((az % 360.0) / 360.0 * (width - 1)))
        cy = int(round((90.0 - min(90.0, alt)) / 90.0 * (height - 1)))
        cy = max(0, min(height - 1, cy))
        grid[cy][max(0, min(width - 1, cx))] = ch

    for alt in (30.0, 60.0):
        for az in range(0, 360, 4):
            put(alt, float(az), "·")
    for i in range(width):
        if i % 2 == 0:
            grid[height - 2][i] = "─"
    for name, az in (("N", 0), ("E", 90), ("S", 180), ("W", 270)):
        idx = int(round(az / 360.0 * (width - 1)))
        for k, ch in enumerate(name):
            if 0 <= idx + k < width:
                grid[height - 1][idx + k] = ch

    for m in fr.get("moons") or []:
        put(m["alt"], m["az"], MOON)
    for s in fr.get("suns") or []:
        put(s["alt"], s["az"], SUN)
    for st in reversed(fr.get("stars") or []):
        put(st["alt"], st["az"], _symbol(st["mag"]))
    return ["".join(row) for row in grid]


def render_png(fr: dict, path: str, width: int = 1200, height: int = 900) -> int:
    """黑底 + 地平线弧 + 高度圈 + 银河带 + 星点。零依赖，走 png_writer。"""
    import png_writer

    buf = bytearray(width * height * 3)
    cx, cy = width / 2.0, height / 2.0
    radius = min(width, height) * 0.455

    def px(x, y, rgb, alpha=1.0):
        if not (0 <= x < width and 0 <= y < height):
            return
        i = (y * width + x) * 3
        if alpha >= 1.0:
            buf[i], buf[i + 1], buf[i + 2] = rgb
        else:
            for k in range(3):
                buf[i + k] = int(buf[i + k] * (1 - alpha) + rgb[k] * alpha)

    def disc(x, y, r, rgb, alpha=1.0):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy <= r * r:
                    px(x + dx, y + dy, rgb, alpha)

    # 天空底色：天顶近黑，地平线附近偏钴蓝（鱼眼：天顶在圆心，地平线在圆周）
    for y in range(height):
        for x in range(width):
            d = math.hypot(x - cx, y - cy) / radius
            t = min(1.0, d)
            r = int(3 + 12 * t)
            g = int(5 + 19 * t)
            b = int(11 + 30 * t)
            i = (y * width + x) * 3
            buf[i], buf[i + 1], buf[i + 2] = r, g, b

    def project(alt, az):
        """全天鱼眼：天顶在圆心，N 在正上方，方位顺时针。"""
        rad = radius * (90.0 - max(0.0, min(90.0, alt))) / 90.0
        a = math.radians(az)
        return int(cx + rad * math.sin(a)), int(cy - rad * math.cos(a))

    # 银河：沿银道面撒一条暗带
    if fr.get("milky_way", {}).get("visible"):
        inc = fr["milky_way"].get("inclination_deg", 30.0)
        lst = _lst_deg(fr["hour"], fr["calendar"]["day_hours"])
        rnd = random.Random(11)
        for _ in range(9000):
            l = rnd.random() * 360.0
            b = rnd.gauss(0.0, 7.0)
            ra, dec = _gal_to_eq(l, b, inc)
            alt, az = _eq_to_hor(ra, dec, lst, fr["observer"]["lat"])
            if alt > 0:
                x, y = project(alt, az)
                px(x, y, (44, 50, 76), 0.22)

    # 高度圈与地平线
    for alt in (0.0, 30.0, 60.0):
        for az in range(0, 361, 2):
            x, y = project(alt, float(az))
            if alt == 0.0:
                px(x, y, (86, 108, 132))
            else:
                px(x, y, (38, 46, 62))
    for az in range(0, 360, 10):
        a = math.radians(az)
        r1 = radius + (14.0 if az % 90 == 0 else 6.0)
        for k in range(1, 6):
            rr = radius + (r1 - radius) * k / 5.0
            px(int(cx + rr * math.sin(a)), int(cy - rr * math.cos(a)), (86, 108, 132))

    for st in fr.get("stars") or []:
        x, y = project(st["alt"], st["az"])
        rgb = png_writer.hex_to_rgb(st.get("color"), (230, 236, 255))
        r = 1 if st["mag"] > 3.5 else (2 if st["mag"] > 1.5 else 3)
        disc(x, y, r, rgb)

    for s in fr.get("suns") or []:
        if s["alt"] <= 0:
            continue
        x, y = project(s["alt"], s["az"])
        disc(x, y, 7, png_writer.hex_to_rgb(s.get("color"), (255, 244, 226)))
        disc(x, y, 11, (255, 244, 226), 0.18)
    for m in fr.get("moons") or []:
        if m["alt"] <= 0:
            continue
        x, y = project(m["alt"], m["az"])
        disc(x, y, 5, (216, 222, 233))

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    return png_writer.write_rgb(path, width, height, buf)


# ════════════════════════════════════════════════════════════════════
# 体检
# ════════════════════════════════════════════════════════════════════

NEG_WORDS = ("看不见星", "看不见星星", "不可见星", "没有星", "看不到星", "恒黑")
POS_WORDS = ("满天", "星河", "银河清晰", "能看见星", "看得见星", "星海")


def check(world: dict, fr: dict = None) -> dict:
    """S01 星表可复算 / S02 摘要与星表一致 / S03 天象文本 vs 星图。"""
    fr = fr or frame(world)
    checks, notes = [], []

    sf = _dict(_cos(world).get("starfield"))
    declared_hash = str(sf.get("hash") or "").strip()
    got = starfield_hash(starfield_params(world))
    if not sf:
        checks.append({"id": "S01", "status": "skip",
                       "note": "未登记星表——按 seed 生成默认 %d 颗，标「默认星表（未登记）」"
                               % starfield_params(world)["count"]})
    elif not declared_hash:
        checks.append({"id": "S01", "status": "warn",
                       "note": "有 starfield 但没有 hash——跑 sky --write --yes 生成"})
    else:
        checks.append({"id": "S01", "status": "pass" if declared_hash == got else "fatal",
                       "note": f"星表 hash {declared_hash} / 复算 {got}"})

    summ = _dict(_dict(_cos(world).get("sky")).get("summary"))
    if not summ:
        checks.append({"id": "S02", "status": "skip",
                       "note": "cosmology.sky.summary 未生成——跑 sky --write --yes"})
    else:
        d_lim = abs(_num(summ.get("limit_mag"), 0) - fr["sky"]["limit_mag"])
        v0 = _num(summ.get("visible_stars"), 0)
        v1 = fr["sky"]["visible_stars"]
        ok = d_lim <= 0.6 and (v0 == 0 or abs(v0 - v1) <= max(20, 0.2 * v1))
        checks.append({"id": "S02", "status": "pass" if ok else "warn",
                       "note": f"极限星等 {_num(summ.get('limit_mag'), 0):g} / 实算 "
                               f"{fr['sky']['limit_mag']:g}；可见星 {v0:g} / {v1}"})

    sky_txt = [str(s) for s in _list(_cos(world).get("sky_phenomena"))]
    limit = fr["sky"]["limit_mag"]
    bad = []
    for t in sky_txt:
        if any(w in t for w in NEG_WORDS) and limit >= 5.0:
            bad.append(f"文本说看不见星，实算极限星等 {limit:g}（暗空）")
        if any(w in t for w in POS_WORDS) and limit < 4.0:
            bad.append(f"文本说满天星，实算极限星等 {limit:g}")
    checks.append({"id": "S03", "status": "pass" if not bad else "warn",
                   "note": "；".join(bad) if bad else "天象文本与星图无可见性矛盾"})

    # 亮到不像「小点」的恒星：只提示，不改世界
    for s in fr["suns"]:
        if s["mag"] < -10.0 and s["diam_arcmin"] < POINT_ARCMIN:
            notes.append(
                f"{s['name']} 实算 {s['mag']:.1f} 等（{round(s['dist_au'], 2):g} AU、"
                f"{s['lum']:g} L☉）：它已经亮到能照亮夜天光，"
                "天象文本若把它写成「小点 / 小灯」，要么改光度，要么改写法。")

    ok = all(c["status"] != "fatal" for c in checks)
    return {"ok": ok, "checks": checks, "notes": notes,
            "hash": got, "moment": fr["moment"]["label"]}


def summary_of(world: dict, fr: dict = None) -> dict:
    fr = fr or frame(world)
    sk = fr["sky"]
    suns = [s["name"] for s in fr["suns"] if s["alt"] > 0]
    note = f"天空亮度 {sk['sky_brightness']:g} mag/arcsec²（经验模型 ±0.5）"
    if suns:
        note += "；地平线上：" + "、".join(suns)
    return {"limit_mag": sk["limit_mag"], "visible_stars": sk["visible_stars"],
            "sky_brightness": sk["sky_brightness"], "milky_way": sk["milky_way"],
            "moment": fr["moment"]["label"], "note": note,
            "generator": f"sky/{SKY_VERSION}"}


def write_summary(world: dict) -> dict:
    """把派生摘要写回 cosmology.sky 与 starfield.hash（幂等）。"""
    params = starfield_params(world)
    cos = world.setdefault("cosmology", {})
    sf = cos.get("starfield")
    if not isinstance(sf, dict):
        sf = {"seed": params["seed"], "count": params["count"],
              "magnitude_dist": params["magnitude_dist"],
              "color_mix": params["color_mix"], "galaxy": params["galaxy"]}
        cos["starfield"] = sf
    sf["hash"] = starfield_hash(params)
    fr = frame(world, 0.0)
    ck = check(world, fr)
    block = cos.get("sky") if isinstance(cos.get("sky"), dict) else {}
    block["summary"] = summary_of(world, fr)
    block["checks"] = [{"id": c["id"], "status": c["status"]} for c in ck["checks"]]
    block["generated"] = ""
    cos["sky"] = block
    return {"starfield": sf["hash"], "summary": block["summary"],
            "checks": ck["checks"], "notes": ck["notes"]}


# ════════════════════════════════════════════════════════════════════
# 输出
# ════════════════════════════════════════════════════════════════════

def _fmt_alt(v: float) -> str:
    return f"{v:+05.1f}°"


def format_report(fr: dict, year: dict = None, path: str = "") -> str:
    cal, obs, sk = fr["calendar"], fr["observer"], fr["sky"]
    name = fr["world"] or "世界"
    L = [f"【今夜】{name} · {fr['moment']['label']} ｜ "
         f"观测点 {obs['lat']:.1f}°{'N' if obs['lat'] >= 0 else 'S'} "
         f"{obs['lon']:.1f}°E {obs['elev']:.0f}m" + ("" if obs["defined"] else "（未登记，取赤道）"),
         f"  天空亮度 {sk['sky_brightness']:g} mag/arcsec² ｜ "
         f"极限星等 {sk['limit_mag']:.1f} ｜ 地平线上约 {sk['visible_stars']} 颗 ｜ "
         f"银河 {'可见' if sk['milky_way'] else '不可见'}"
         + (f" ｜ 月相 {fr['moons'][0]['phase']}（{fr['moons'][0]['name']}）"
            if fr["moons"] and fr["moons"][0]["alt"] > 0
            else (" ｜ 卫星都在地平线下" if fr["moons"] else "")),
         "",
         "【全天】地平坐标 96×30 · 顶为天顶 · #<0 *0–2 +2–4 .4–极限 · @恒星 O行星 C卫星"]
    L += chart_ascii(fr)
    L.append("")
    L.append("【关键天体】")
    if not fr["suns"] and not fr["moons"]:
        L.append("  这个世界的天上没有恒星。")
    for s in fr["suns"]:
        L.append(f"  {s['name']:<6} alt {s['alt']:+05.1f}°  az {s['az']:05.1f}°  "
                 f"{s['mag']:+.1f} 等  {s['dist_au']:g} AU")
    for m in fr["moons"]:
        L.append(f"  {m['name']:<6} alt {m['alt']:+05.1f}°  az {m['az']:05.1f}°  "
                 f"{m['mag']:+.1f} 等  相位 {m['phase']}  角直径 {m['diam_arcmin']:.1f}′")
    if not fr["moons"] and fr["suns"]:
        L.append("  没有卫星：夜里没有可辨的月相，潮汐也不由月驱动。")

    y = year or year_table(ws_world_of(fr))
    L.append("")
    L.append("【一年】"
             f"昼长 {y['min_daylight_hours']:.1f}–{y['max_daylight_hours']:.1f} h ｜ "
             f"极昼 {y['polar_day']} ｜ 极夜 {y['polar_night']} ｜ "
             f"最长夜 {y['longest_night_month']}（倾角 {y['tilt_deg']:g}°，"
             f"一天 {y['day_hours']:g} h，一年 {y['year_days']:g} 天）")

    L.append("")
    L.append("【判断】")
    L.append(f"  {judgement(fr)}")
    L.append("  （简化模型：圆轨道近似 + 经验天光；星表程序生成、按 seed 可复算，"
             "不是真实天空。）")
    return "\n".join(L)


def ws_world_of(fr: dict) -> dict:
    """format_report 只拿到帧时，用一个最小世界重建一年表。"""
    o, cal = fr["observer"], fr["calendar"]
    return {"cosmology": {
        "calendar": {"day_hours": cal["day_hours"], "year_days": cal["year_days"],
                     "months": cal["months"], "month_days": cal["month_days"],
                     "month_names": cal["names"]},
        "surface": {"observer": {"lat_deg": o["lat"], "lon_deg": o["lon"],
                                 "elev_m": o["elev"]}},
        "bodies": [{"id": "_", "axial_tilt_deg": fr["tilt_deg"], "rotation_hours": cal["day_hours"],
                    "atmosphere": {}}],
        "stars": [], "starfield": {},
    }}


def judgement(fr: dict) -> str:
    sk = fr["sky"]
    up = [s for s in fr["suns"] if s["alt"] > 0]
    bright_ill = [(n, b) for n, b in sk["components"]["illuminator"]]
    if sk["sun_up"] and sk["sky_brightness"] < 16:
        return (f"有 {len(up)} 颗恒星在地平线上，天是亮的：此刻看不见星，"
                "这不是 bug，是白天。")
    if bright_ill:
        n, b = min(bright_ill, key=lambda x: x[1])
        return (f"{n} 把夜天光压到 {sk['sky_brightness']:g} mag/arcsec² 左右，"
                f"肉眼只能看见约 {sk['visible_stars']} 颗；"
                + ("银河被洗掉了。" if not sk["milky_way"] else "银河仍勉强可辨。"))
    if sk["limit_mag"] >= 6.0:
        return (f"暗空：极限星等约 {sk['limit_mag']:g}，肉眼可见约 {sk['visible_stars']} 颗"
                + ("，银河横过天顶。" if sk["milky_way"] else "。"))
    return (f"夜空被压到 {sk['sky_brightness']:g} mag/arcsec²，"
            f"极限星等约 {sk['limit_mag']:g}，可见约 {sk['visible_stars']} 颗。")


def format_year(y: dict) -> str:
    L = [f"【一年】倾角 {y['tilt_deg']:g}° ｜ 一天 {y['day_hours']:g} h ｜ "
         f"一年 {y['year_days']:g} 天 ｜ 观测点 {y['lat']:g}°",
         "",
         "  月份        昼长(h)  正午太阳高度  极昼/极夜  夜可见星"]
    for r in y["rows"]:
        L.append(f"  {r['name']:<10}  {r['daylight_hours']:>6.1f}  "
                 f"{r['noon_alt_deg']:>10.1f}°  {r['polar']:<6}  {r['night_stars']:>6}")
    L.append("")
    L.append(f"  昼长 {y['min_daylight_hours']:.1f}–{y['max_daylight_hours']:.1f} h ｜ "
             f"极昼 {y['polar_day']} ｜ 极夜 {y['polar_night']} ｜ "
             f"最长夜 {y['longest_night_month']}")
    L.append("  只算天文昼长：不算天气、云量、地形遮挡，也不含大气折射。")
    return "\n".join(L)


def format_check(res: dict) -> str:
    icon = {"pass": "✓", "warn": "!", "fatal": "✗", "skip": "·"}
    L = ["盘古 · 星空体检", "-" * 56]
    for c in res["checks"]:
        L.append(f"  {icon.get(c['status'], '?')} {c['id']} {c['note']}")
    if res["notes"]:
        L.append("")
        L.append("  软提示（只报不改，改不改是作者的设定决策）")
        for n in res["notes"]:
            L.append(f"    ! {n}")
    L.append("-" * 56)
    bad = [c for c in res["checks"] if c["status"] in ("fatal", "warn")]
    L.append("  结论：星表可复算，摘要与实算一致。"
             if not bad else f"  结论：{len(bad)} 项待修（{', '.join(c['id'] for c in bad)}）。")
    return "\n".join(L)


def format_md(fr: dict, year: dict, png_rel: str = "") -> str:
    L = [f"### 今夜 · {fr['world']} {fr['moment']['label']}", ""]
    if png_rel:
        L.append(f"![今夜星图]({png_rel})")
        L.append("")
    L += ["```", *chart_ascii(fr), "```", ""]
    sk = fr["sky"]
    L.append(f"- 天空亮度 **{sk['sky_brightness']:g}** mag/arcsec² ｜ "
             f"极限星等 **{sk['limit_mag']:g}** ｜ 可见星约 **{sk['visible_stars']}** 颗 ｜ "
             f"银河 {'可见' if sk['milky_way'] else '不可见'}")
    for s in fr["suns"]:
        L.append(f"- {s['name']}：alt {s['alt']:+.1f}° / az {s['az']:.1f}° / {s['mag']:+.1f} 等")
    for m in fr["moons"]:
        L.append(f"- {m['name']}：alt {m['alt']:+.1f}° / 相位 {m['phase']} / {m['mag']:+.1f} 等")
    L.append("")
    L.append(f"| 月 | 昼长(h) | 正午太阳高度 | 极昼/极夜 | 夜可见星 |")
    L.append("|---|---|---|---|---|")
    for r in year["rows"]:
        L.append(f"| {r['name']} | {r['daylight_hours']:.1f} | {r['noon_alt_deg']:.1f}° | "
                 f"{r['polar']} | {r['night_stars']} |")
    L.append("")
    L.append("> 简化模型：圆轨道近似 + 经验天光（±0.5 等）；星表由 seed 确定性生成，"
             "是本世界的计算结果，不是真实天空。")
    return "\n".join(L)


# ════════════════════════════════════════════════════════════════════
# 反事实：改一个数，今夜会怎样
# ════════════════════════════════════════════════════════════════════

def _snap(world: dict) -> dict:
    return {"sky": sky_brightness(world, 0.0), "year": year_table(world),
            "tilt": round(_obliquity(world), 1)}


def compare(before: dict, after: dict) -> dict:
    a, b = _snap(before), _snap(after)
    rows = []

    def add(field, va, vb):
        if va != vb:
            rows.append({"field": field, "before": va, "after": vb})

    ya, yb = a["year"], b["year"]
    add("昼长(h)", f"{ya['min_daylight_hours']:.1f}–{ya['max_daylight_hours']:.1f}",
        f"{yb['min_daylight_hours']:.1f}–{yb['max_daylight_hours']:.1f}")
    add("极昼", ya["polar_day"], yb["polar_day"])
    add("极夜", ya["polar_night"], yb["polar_night"])
    add("夜空亮度", f"{a['sky']['sky_brightness']:g}", f"{b['sky']['sky_brightness']:g}")
    add("极限星等", f"{a['sky']['limit_mag']:g}", f"{b['sky']['limit_mag']:g}")
    add("可见星", a["sky"]["visible_stars"], b["sky"]["visible_stars"])
    add("银河", "可见" if a["sky"]["milky_way"] else "不可见",
        "可见" if b["sky"]["milky_way"] else "不可见")
    return {"rows": rows, "before": a, "after": b,
            "headline": ("昼长与季节变了" if any(r["field"].startswith(("昼长", "极"))
                                            for r in rows)
                         else "今夜的天变了")}


def format_compare(cmp: dict, changes: list = None) -> str:
    head = ""
    if changes:
        head = " ｜ ".join(f"{c['path'].split('.')[-1]} {_fmt_num(c.get('old'))} → "
                          f"{_fmt_num(c.get('new'))}" for c in changes[:2])
    L = [f"【抬头】{head}" if head else "【抬头】"]
    if not cmp["rows"]:
        L.append("  改了这一条，今夜星空没有任何可测的变化。")
        return "\n".join(L)
    for r in cmp["rows"]:
        L.append(f"  {r['field']:<10} {str(r['before']):<12} →  {r['after']}")
    L.append("  （今夜按本地夜半算；改的是季节的，表里只有昼长与极昼极夜会动。）")
    return "\n".join(L)


def _fmt_num(v) -> str:
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def diff_line(before: dict, after: dict) -> str:
    try:
        a = sky_brightness(before, 0.0)
        b = sky_brightness(after, 0.0)
    except Exception:       # noqa: BLE001
        return ""
    return (f"抬头：极限星等 {a['limit_mag']:g} → {b['limit_mag']:g} ｜ "
            f"可见星 {a['visible_stars']} → {b['visible_stars']} ｜ "
            f"银河 {'可见' if a['milky_way'] else '不可见'} → "
            f"{'可见' if b['milky_way'] else '不可见'}")


# ════════════════════════════════════════════════════════════════════
# 预览页用的多帧数据
# ════════════════════════════════════════════════════════════════════

def frames_for_preview(world: dict, n: int = 6, cap: int = 1400) -> dict:
    cal = calendar(world)
    out = []
    for i in range(max(1, n)):
        hour = cal["day_hours"] * i / max(1, n)
        fr = frame(world, hour)
        stars = [[s["az"], s["alt"], s["mag"]] for s in fr["stars"][:cap]]
        out.append({
            "hour": round(hour, 2),
            "label": f"{int(hour):02d}:{int((hour % 1) * 60):02d}",
            "stars": stars,
            "limit_mag": fr["sky"]["limit_mag"],
            "visible": fr["sky"]["visible_stars"],
            "milky_way": fr["sky"]["milky_way"],
            "suns": [[s["az"], s["alt"], s["name"], s["color"]] for s in fr["suns"]],
            "moons": [[m["az"], m["alt"], m["name"]] for m in fr["moons"]],
        })
    return {"frames": out, "day_hours": cal["day_hours"],
            "lat": observer(world)["lat"], "name": ws._get(world, "meta", "name", default="")}
