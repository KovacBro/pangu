# -*- coding: utf-8 -*-
"""
盘古 · 行星地图引擎（Planetary Map）
====================================

不是画一张好看的假地图。地图上的每一层都由 `world.json` 的设定推出来：

    板块   ← 行星半径 / 重力 / 自转 / 设定里的构造参数
    海平面 ← 水量（chemistry.solvent）与盆地容积（构造地形）共同决定
    温度   ← 恒星光度 / 轨道 / 转轴倾角 / 大气温室 / 表面重力
    降水   ← 自转风带、海陆分布、山脉迎风坡与雨影
    河流   ← 洼地填充后的最陡下降路径与汇流累积
    群系   ← world.json 自己声明的 biomes[] 高程带 + 极冰 + 气候
    宜居度 ← 温度、溶剂、光照、海拔胁迫的乘积（喂给 CA 当空间承载能力）

输出：高程 / 群系 / 温度 / 降水 / 构造 / 宜居度 / 正射地球 / 交互地图页。
纯标准库，不引 Pillow / numpy。PNG 走 png_writer。

对外接口：
    build(world, res=(360,180), seed=None) -> MapResult
    write_outputs(result, outdir, res_out=(1440,720)) -> dict
    check(world, res, seed) -> dict
"""

from __future__ import annotations

import base64
import heapq
import json
import math
import os
import random
import zlib
from dataclasses import dataclass, field

import png_writer as pw
import world_schema as ws

MAP_VERSION = "1.1.1"
MAX_SIDE = 720
MIN_SIDE = 60
DEFAULT_RES = (360, 180)
RENDER_RES = (1440, 720)
GLOBE_RES = 900

TAU = math.pi * 2.0


# ════════════════════════════════════════════════════════════════════
# 小工具
# ════════════════════════════════════════════════════════════════════

def _clamp(v, a, b):
    return a if v < a else (b if v > b else v)


def _lerp(a, b, t):
    return a + (b - a) * t


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def _percentile(values, q):
    """q ∈ [0,1]，线性插值分位数（会复制并排序，调用方注意规模）。"""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    pos = _clamp(q, 0.0, 1.0) * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


# ════════════════════════════════════════════════════════════════════
# 球面噪声（值噪声 + fBm）
# ════════════════════════════════════════════════════════════════════

class _Noise:
    def __init__(self, seed: int):
        rng = random.Random(seed)
        p = list(range(256))
        rng.shuffle(p)
        self.p = p + p

    def value(self, x: float, y: float, z: float) -> float:
        p = self.p
        xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
        xf, yf, zf = x - xi, y - yi, z - zi
        u, v, w = _smooth(xf), _smooth(yf), _smooth(zf)

        def h(ix, iy, iz):
            return p[(p[(p[ix & 255] + iy) & 255] + iz) & 255] / 255.0

        x00 = _lerp(h(xi, yi, zi), h(xi + 1, yi, zi), u)
        x10 = _lerp(h(xi, yi + 1, zi), h(xi + 1, yi + 1, zi), u)
        x01 = _lerp(h(xi, yi, zi + 1), h(xi + 1, yi, zi + 1), u)
        x11 = _lerp(h(xi, yi + 1, zi + 1), h(xi + 1, yi + 1, zi + 1), u)
        return _lerp(_lerp(x00, x10, v), _lerp(x01, x11, v), w)

    def fbm(self, x, y, z, octaves=5, freq=1.0, lacunarity=2.03,
            gain=0.5, ridge=False) -> float:
        total = 0.0
        amp = 1.0
        norm = 0.0
        f = freq
        for i in range(octaves):
            # 每层转一点坐标，避免格子对齐的十字纹
            n = self.value(x * f + i * 19.7, y * f - i * 7.3, z * f + i * 3.1)
            if ridge:
                n = 1.0 - abs(n * 2.0 - 1.0)
            total += n * amp
            norm += amp
            amp *= gain
            f *= lacunarity
        return total / norm if norm else 0.0


# ════════════════════════════════════════════════════════════════════
# 结果
# ════════════════════════════════════════════════════════════════════

@dataclass
class MapResult:
    nx: int
    ny: int
    radius_km: float
    lat: list
    lon: list
    area: list
    area_total: float
    height: list            # 相对海平面的海拔（km，可为负）
    sea_level: float        # km
    ocean: list
    depth: list             # km，海洋为正
    elev: list              # km，陆地为正
    v: list                 # 展示用归一化高程（0–1，海平面 = sea_v）
    sea_v: float
    temperature: list       # K
    precip: list            # mm/yr
    habitat: list           # 0–1
    biome: list             # 索引
    plate: list
    boundary: list          # 0 none / 1 conv / 2 div / 3 transform
    hotspot: list
    filled: list            # 洼地填充后的高程
    down: list
    discharge: list
    lake: list
    river: list
    micro: list
    biomes: list
    stats: dict
    checks: list
    hash: str
    meta: dict
    noise_meta: dict = field(default_factory=dict)


# ════════════════════════════════════════════════════════════════════
# 设定抽取
# ════════════════════════════════════════════════════════════════════

def main_body(world: dict) -> dict:
    bodies = ws._get(world, "cosmology", "bodies", default=[]) or []
    for b in bodies:
        if isinstance(b, dict) and str(b.get("kind") or "") == "planet":
            return b
    for b in bodies:
        if isinstance(b, dict):
            return b
    return {}


def _cfg(world: dict) -> dict:
    body = main_body(world)
    pm = body.get("planet_map") if isinstance(body.get("planet_map"), dict) else {}
    tect = pm.get("tectonics") if isinstance(pm.get("tectonics"), dict) else {}
    hydro = pm.get("hydrosphere") if isinstance(pm.get("hydrosphere"), dict) else {}
    clim = pm.get("climate") if isinstance(pm.get("climate"), dict) else {}

    r_km = ws._num(body.get("radius_km"), 0.0) or 6371.0
    r_e = ws._num(body.get("radius_earth"), 0.0) or (r_km / 6371.0)
    g = ws._num(body.get("gravity_g"), 0.0) or 1.0
    rot = body.get("rotation_hours")
    period_d = ws._num(ws._get(body, "orbit", "period_days", default=0), 0.0)
    locked = bool(pm.get("tidal_locked")) or rot is None
    if not locked and period_d > 0 and ws._num(rot, 0) > 0:
        locked = abs(ws._num(rot, 0) - period_d * 24.0) / (period_d * 24.0) < 0.02

    derived = ws.compute_derived(world)
    dbody = next((x for x in derived.get("bodies", []) if x.get("id") == body.get("id")),
                 derived.get("bodies", [{}])[0] if derived.get("bodies") else {})
    t_surface = ws._num(dbody.get("t_surface_k"), 0.0)
    if t_surface <= 0:
        t_surface = ws._num(dbody.get("t_eq_k"), 0.0) or 288.0

    # 群系：world.json 自己声明的才是官方分类
    biomes = []
    for b in (body.get("biomes") or []):
        if not isinstance(b, dict):
            continue
        biomes.append({
            "id": str(b.get("id") or "biome"),
            "name": str(b.get("name") or b.get("id") or "群系"),
            "color": str(b.get("color") or "#888888"),
            "elevation": _clamp(ws._num(b.get("elevation"), 0.0), 0.0, 1.0),
        })
    if not biomes:
        biomes = [
            {"id": "ocean", "name": "海", "color": "#1E4058", "elevation": 0.0},
            {"id": "land", "name": "陆", "color": "#8C7B63", "elevation": 0.46},
            {"id": "high", "name": "高地", "color": "#B9C4CE", "elevation": 0.8},
        ]
    biomes.sort(key=lambda x: x["elevation"])

    sea_v = ws._num(body.get("sea_level"), 0.0)
    if sea_v <= 0:
        land = [b for b in biomes if b["elevation"] > 0]
        sea_v = land[0]["elevation"] if land else 0.46
    sea_v = _clamp(sea_v, 0.25, 0.7)

    max_relief = 8.8 / max(0.35, g ** 0.8)
    relief_km = ws._num(tect.get("relief_km"), 0.0) or _clamp(max_relief, 2.5, 12.0)
    plates = int(ws._num(tect.get("plates"), 0)) or int(_clamp(6 + r_e * 2.2, 6, 16))
    hotspots = int(ws._num(tect.get("hotspots"), -1))
    if hotspots < 0:
        hotspots = int(_clamp(2 + r_e, 2, 7))

    area_total = 4.0 * math.pi * r_km * r_km
    mean_depth = ws._num(hydro.get("mean_depth_km"), 0.0)
    if mean_depth <= 0:
        mean_depth = _clamp(0.30 * (2.0 * relief_km), 1.2, 4.5)
    inv = ws._num(hydro.get("inventory_km3"), 0.0)
    if inv <= 0:
        inv = area_total * 0.50 * mean_depth

    atm = body.get("atmosphere") if isinstance(body.get("atmosphere"), dict) else {}
    pressure = ws._num(atm.get("surface_pressure_kpa"), 101.325) or 101.325
    mean_precip = ws._num(clim.get("mean_precip_mm"), 0.0)
    if mean_precip <= 0:
        mean_precip = _clamp(900.0 * (max(1.0, pressure) / 101.325) ** 0.55, 120.0, 3000.0)

    return {
        "body": body, "pm": pm, "r_km": r_km, "r_e": r_e, "g": g,
        "rotation_h": ws._num(rot, 0.0), "locked": locked,
        "tilt": ws._num(body.get("axial_tilt_deg"), 0.0),
        "albedo": ws._num(body.get("albedo"), 0.3),
        "t_mean": t_surface, "biomes": biomes, "sea_v": sea_v,
        "relief_km": relief_km, "plates": plates, "hotspots": hotspots,
        "area_total": area_total, "mean_depth": mean_depth, "inventory": inv,
        "pressure": pressure, "mean_precip": mean_precip,
        "polar_color": str(body.get("polar_color") or "#E8F0F8"),
        "seed": int(ws._num(pm.get("seed"), 7)),
    }


# ════════════════════════════════════════════════════════════════════
# 网格与构造
# ════════════════════════════════════════════════════════════════════

def _grid(nx: int, ny: int, r_km: float):
    lon, lat, area = [], [], []
    ux, uy, uz = [], [], []
    dlon = TAU / nx
    for y in range(ny):
        la = 90.0 - (y + 0.5) * 180.0 / ny
        lat.append(la)
        s1 = math.sin(math.radians(90.0 - y * 180.0 / ny))
        s2 = math.sin(math.radians(90.0 - (y + 1) * 180.0 / ny))
        a = r_km * r_km * dlon * abs(s1 - s2)
        for x in range(nx):
            lo = -180.0 + (x + 0.5) * 360.0 / nx
            lon.append(lo)
            area.append(a)
            cla = math.cos(math.radians(la))
            ux.append(cla * math.cos(math.radians(lo)))
            uy.append(cla * math.sin(math.radians(lo)))
            uz.append(math.sin(math.radians(la)))
    total = sum(area)
    return lon, lat, area, ux, uy, uz, total


def _plate_seeds(count: int, rng: random.Random):
    pts = []
    ga = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(count):
        y = 1.0 - (i + 0.5) * 2.0 / count
        y = _clamp(y + rng.uniform(-0.12, 0.12), -0.98, 0.98)
        r = math.sqrt(max(0.0, 1.0 - y * y))
        th = ga * i + rng.uniform(-0.25, 0.25)
        pts.append((r * math.cos(th), y, r * math.sin(th)))
    return pts


def _tangent(ux, uy, uz):
    """球面单位向量处的东/北基。"""
    cl = math.sqrt(max(1e-9, ux * ux + uy * uy))
    ex, ey, ez = -uy / cl, ux / cl, 0.0
    nx, ny, nz = -ez * uy, ez * ux, ex * uy - ey * ux
    return (ex, ey, ez), (nx, ny, nz)


def _box_blur(field, nx, ny, radius):
    """可分离盒式模糊（经度环绕，纬度不绕）。"""
    if radius <= 0:
        return list(field)
    w = radius * 2 + 1
    tmp = [0.0] * (nx * ny)
    for y in range(ny):
        row = y * nx
        for x in range(nx):
            s = 0.0
            for k in range(-radius, radius + 1):
                s += field[row + (x + k) % nx]
            tmp[row + x] = s / w
    out = [0.0] * (nx * ny)
    for y in range(ny):
        for x in range(nx):
            s = 0.0
            c = 0
            for k in range(-radius, radius + 1):
                yy = y + k
                if 0 <= yy < ny:
                    s += tmp[yy * nx + x]
                    c += 1
            out[y * nx + x] = s / max(1, c)
    return out


def _tectonics(nx, ny, r_km, ux, uy, uz, rng, n_plates, n_hot, noise):
    n = nx * ny
    seeds = _plate_seeds(n_plates, rng)
    plate = [0] * n
    for i in range(n):
        bx = ux[i]
        by = uy[i]
        bz = uz[i]
        best = -2.0
        bi = 0
        for k, (sx, sy, sz) in enumerate(seeds):
            d = bx * sx + by * sy + bz * sz
            if d > best:
                best = d
                bi = k
        plate[i] = bi

    cont = []
    motion = []
    for k, s in enumerate(seeds):
        cont.append(_clamp(0.10 + 0.90 * rng.random() ** 0.85, 0.08, 0.98))
        e, nn = _tangent(*s)
        a = rng.uniform(0, TAU)
        sp = rng.uniform(0.35, 1.0)
        motion.append((math.cos(a) * sp * e[0] + math.sin(a) * sp * nn[0],
                       math.cos(a) * sp * e[1] + math.sin(a) * sp * nn[1],
                       math.cos(a) * sp * e[2] + math.sin(a) * sp * nn[2]))

    boundary = [0] * n
    upl = [0.0] * n
    rift = [0.0] * n
    conv_cells = div_cells = trans_cells = 0

    def pair(i, j):
        nonlocal conv_cells, div_cells, trans_cells
        a, b = plate[i], plate[j]
        if a == b:
            return
        ma, mb = motion[a], motion[b]
        dvx, dvy, dvz = mb[0] - ma[0], mb[1] - ma[1], mb[2] - ma[2]
        # 从 b 指向 a 的方向（弦），与相对速度点乘：正 = 相互靠近
        dx, dy, dz = seeds[a][0] - seeds[b][0], seeds[a][1] - seeds[b][1], seeds[a][2] - seeds[b][2]
        dl = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        approach = (dvx * dx + dvy * dy + dvz * dz) / dl
        both_ocean = cont[a] < 0.4 and cont[b] < 0.4
        if approach > 0.12:
            typ = 1
            amp = _clamp(approach, 0.0, 1.0)
            upl[i] += 0.55 + 1.10 * amp
            upl[j] += 0.55 + 1.10 * amp
            if both_ocean:
                rift[i] -= 0.35 + 0.55 * amp
                rift[j] -= 0.35 + 0.55 * amp
            conv_cells += 1
        elif approach < -0.12:
            typ = 2
            amp = _clamp(-approach, 0.0, 1.0)
            rift[i] -= 0.30 + 0.80 * amp
            rift[j] -= 0.30 + 0.80 * amp
            upl[i] += 0.12
            upl[j] += 0.12
            div_cells += 1
        else:
            typ = 3
            upl[i] += 0.18
            upl[j] += 0.18
            trans_cells += 1
        boundary[i] = max(boundary[i], typ)
        boundary[j] = max(boundary[j], typ)

    for y in range(ny):
        for x in range(nx):
            i = y * nx + x
            pair(i, y * nx + (x + 1) % nx)
            if y + 1 < ny:
                pair(i, (y + 1) * nx + x)

    up2 = _box_blur(upl, nx, ny, 2)
    up3 = _box_blur(up2, nx, ny, 2)
    rf2 = _box_blur(rift, nx, ny, 1)

    # 热点：羽流 + 沿板块运动方向的火山链
    hot = [False] * n
    plume = [0.0] * n
    chosen = []
    tries = 0
    while len(chosen) < n_hot and tries < 400:
        tries += 1
        p = _plate_seeds(1, rng)[0]
        if any(sum(p[k] * c[k] for k in range(3)) > 0.82 for c in chosen):
            continue
        chosen.append(p)
        bi = max(range(len(seeds)), key=lambda k: p[0] * seeds[k][0] + p[1] * seeds[k][1]
                 + p[2] * seeds[k][2])
        mv = motion[bi]
        chain = rng.randint(3, 6)
        for step in range(chain):
            q = (p[0] + mv[0] * step * 0.035, p[1] + mv[1] * step * 0.035,
                 p[2] + mv[2] * step * 0.035)
            ql = math.sqrt(q[0] ** 2 + q[1] ** 2 + q[2] ** 2) or 1.0
            q = (q[0] / ql, q[1] / ql, q[2] / ql)
            amp = math.exp(-step * 0.32)
            sig = 1.4 + 1.6 * rng.random()
            lon0 = math.degrees(math.atan2(q[1], q[0]))
            lat0 = math.degrees(math.asin(_clamp(q[2], -1, 1)))
            x0 = int((lon0 + 180.0) / 360.0 * nx)
            y0 = int((90.0 - lat0) / 180.0 * ny)
            rr = int(sig * 3) + 1
            for dy in range(-rr, rr + 1):
                yy = y0 + dy
                if yy < 0 or yy >= ny:
                    continue
                for dx in range(-rr, rr + 1):
                    xx = (x0 + dx) % nx
                    d2 = (dx * dx + dy * dy) / (sig * sig)
                    if d2 > 9.0:
                        continue
                    idx = yy * nx + xx
                    plume[idx] += amp * math.exp(-d2)
                    hot[idx] = True

    base = [0.0] * n
    n1 = noise.fbm
    # 大陆性先做空间平滑：板块边界是陡的，大陆边缘不该是刀切的
    c_field = [cont[plate[i]] for i in range(n)]
    br = max(2, nx // 48)
    c_smooth = _box_blur(_box_blur(c_field, nx, ny, br), nx, ny, br)
    for i in range(n):
        x, y, z = ux[i], uy[i], uz[i]
        # 域扭曲：让海岸线、山脉和板块边界都长出分形细节
        wx = x + 0.22 * (n1(x + 4.1, y - 2.7, z + 1.9, 3, 2.10) - 0.5)
        wy = y + 0.22 * (n1(x - 1.3, y + 3.4, z - 2.2, 3, 2.10) - 0.5)
        wz = z + 0.22 * (n1(x + 2.6, y + 0.8, z + 4.5, 3, 2.10) - 0.5)
        low = n1(wx, wy, wz, 5, 1.15, ridge=False) - 0.5
        mid = n1(wx, wy, wz, 4, 3.90, ridge=False) - 0.5
        rid = n1(wx, wy, wz, 3, 8.20, ridge=True) - 0.5
        c = c_smooth[i] - 0.55
        base[i] = (0.98 * low + 0.78 * c + 0.44 * mid + 0.20 * rid
                   + 1.15 * up3[i] + 0.95 * rf2[i] + 0.50 * plume[i])

    return {
        "plate": plate, "cont": cont, "motion": motion, "seeds": seeds,
        "boundary": boundary, "hot": hot, "base": base,
        "conv_cells": conv_cells, "div_cells": div_cells, "trans_cells": trans_cells,
    }


# ════════════════════════════════════════════════════════════════════
# 海洋：水量 → 海平面
# ════════════════════════════════════════════════════════════════════

def _solve_sea(height, area, volume):
    """给水量 V，求海平面 h_s 使 ∫_{h<h_s}(h_s-h)dA = V。返回 (h_s, 海洋占比)。"""
    idx = sorted(range(len(height)), key=lambda i: height[i])
    A = 0.0
    I = 0.0
    total = sum(area) or 1.0
    for k, i in enumerate(idx):
        a = area[i]
        h = height[i]
        A += a
        I += h * a
        hs = (volume + I) / A
        if hs < h:
            A -= a
            I -= h * a
            if A <= 0:
                return height[idx[0]], 0.0
            hs = (volume + I) / A
            return hs, A / total
    return height[idx[-1]], 1.0


# ════════════════════════════════════════════════════════════════════
# 温度：真实年辐照 + 温室 + 自转
# ════════════════════════════════════════════════════════════════════

def _daily_coszen(lat_deg, dec_deg):
    phi = math.radians(lat_deg)
    dec = math.radians(dec_deg)
    x = -math.tan(phi) * math.tan(dec)
    if x >= 1.0:
        return 0.0
    if x <= -1.0:
        return max(0.0, math.sin(phi) * math.sin(dec))
    h0 = math.acos(x)
    return (h0 * math.sin(phi) * math.sin(dec)
            + math.cos(phi) * math.cos(dec) * math.sin(h0)) / math.pi


def _annual_factor(lat_deg, tilt_deg):
    if tilt_deg < 0.5:
        return max(0.0, math.cos(math.radians(lat_deg))) * 0.25
    vals = []
    for k in range(13):
        dec = -tilt_deg + 2.0 * tilt_deg * k / 12.0
        vals.append(_daily_coszen(lat_deg, dec))
    return sum(vals) / len(vals)


def _temperature(cfg, res_lat, area, ux, uy, uz, ocean, depth, elev):
    nx, ny = cfg["nx"], cfg["ny"]
    n = nx * ny
    t_mean = cfg["t_mean"]
    tilt = cfg["tilt"]
    locked = cfg["locked"]
    body = cfg["body"]

    fs = [_annual_factor(la, tilt) for la in res_lat]
    area_sum = sum(area) or 1.0
    mean_f = sum(fs[i // nx] * area[i] for i in range(n)) / area_sum

    sub = body.get("substellar") if isinstance(body.get("substellar"), dict) else {}
    slon = ws._num(sub.get("lon_deg"), 0.0)
    slat = ws._num(sub.get("lat_deg"), 0.0)
    sx = math.cos(math.radians(slat)) * math.cos(math.radians(slon))
    sy = math.cos(math.radians(slat)) * math.sin(math.radians(slon))
    sz = math.sin(math.radians(slat))

    T = [0.0] * n
    for i in range(n):
        if locked:
            cospsi = ux[i] * sx + uy[i] * sy + uz[i] * sz
            if cospsi >= 0:
                t = t_mean + 55.0 * cospsi - 18.0
            else:
                t = t_mean - 52.0 + 14.0 * cospsi
        else:
            fn = (fs[i // nx] / mean_f) if mean_f > 0 else 1.0
            t = t_mean + (fn - 1.0) * 62.0
        T[i] = t

    T = _box_blur(T, cfg["nx"], cfg["ny"], 2)

    lapse = 6.5 * (max(0.3, cfg["g"]) ** 0.25)
    for i in range(n):
        if ocean[i]:
            T[i] -= min(0.8, depth[i] * 0.06)
        else:
            T[i] -= lapse * elev[i] * 0.55

    mean_t = sum(T[i] * area[i] for i in range(n)) / (sum(area) or 1.0)
    shift = (t_mean - mean_t) * 0.65
    for i in range(n):
        T[i] = _clamp(T[i] + shift, 90.0, 900.0)
    return T


# ════════════════════════════════════════════════════════════════════
# 降水：风带 + 水汽输送 + 迎风坡
# ════════════════════════════════════════════════════════════════════

def _wind_field(cfg, lat, lon, ux, uy, uz):
    nx, ny = cfg["nx"], cfg["ny"]
    n = nx * ny
    U = [0.0] * n
    V = [0.0] * n
    if cfg["locked"]:
        body = cfg["body"]
        sub = body.get("substellar") if isinstance(body.get("substellar"), dict) else {}
        slon = ws._num(sub.get("lon_deg"), 0.0)
        slat = ws._num(sub.get("lat_deg"), 0.0)
        sx = math.cos(math.radians(slat)) * math.cos(math.radians(slon))
        sy = math.cos(math.radians(slat)) * math.sin(math.radians(slon))
        sz = math.sin(math.radians(slat))
        for i in range(n):
            dot = ux[i] * sx + uy[i] * sy + uz[i] * sz
            wx = ux[i] - dot * sx
            wy = uy[i] - dot * sy
            wz = uz[i] - dot * sz
            wl = math.sqrt(wx * wx + wy * wy + wz * wz) or 1.0
            e, nn = _tangent(ux[i], uy[i], uz[i])
            U[i] = (wx * e[0] + wy * e[1] + wz * e[2]) / wl
            V[i] = (wx * nn[0] + wy * nn[1] + wz * nn[2]) / wl
        return U, V

    for i in range(n):
        la = lat[i // nx]
        ala = abs(la)
        s = 1.0 if la >= 0 else -1.0
        if ala < 30.0:
            U[i] = -1.0
            V[i] = -s * (ala / 30.0) * 0.35
        elif ala < 60.0:
            U[i] = 1.0
            V[i] = s * ((ala - 30.0) / 30.0) * 0.35
        else:
            U[i] = -0.6
            V[i] = s * 0.15
    return U, V


def _bilinear(field, nx, ny, x, y):
    """x 环绕，y 夹紧。x,y 可为 float 格坐标。"""
    x = x % nx
    yy = _clamp(y, 0.0, ny - 1.001)
    x0 = int(x)
    y0 = int(yy)
    x1 = (x0 + 1) % nx
    y1 = min(y0 + 1, ny - 1)
    fx = x - x0
    fy = yy - y0
    a = field[y0 * nx + x0]
    b = field[y0 * nx + x1]
    c = field[y1 * nx + x0]
    d = field[y1 * nx + x1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _precipitation(cfg, lat, lon, area, height, ocean, elev, temp):
    nx, ny = cfg["nx"], cfg["ny"]
    n = nx * ny
    U, V = _wind_field(cfg, lat, lon, cfg["ux"], cfg["uy"], cfg["uz"])

    cell_km = TAU * cfg["r_km"] / nx
    slope = [0.0] * n
    for y in range(ny):
        for x in range(nx):
            i = y * nx + x
            if ocean[i]:
                continue
            xm = y * nx + (x - 1) % nx
            xp = y * nx + (x + 1) % nx
            ym = (y - 1) * nx + x if y > 0 else i
            yp = (y + 1) * nx + x if y + 1 < ny else i
            dhdx = (height[xp] - height[xm]) / (2.0 * cell_km)
            dhdy = (height[yp] - height[ym]) / (2.0 * cell_km)
            slope[i] = U[i] * dhdx + V[i] * dhdy
    pos = [s for s in slope if s > 0]
    p90 = _percentile(pos, 0.90) if pos else 1.0

    evap_base = [0.0] * n
    for i in range(n):
        if temp[i] < 268.0:
            continue
        if ocean[i]:
            evap_base[i] = (temp[i] - 268.0) / 30.0
        else:
            # 陆地蒸腾：森林自己往空中送水，内陆不至于全干
            evap_base[i] = 0.38 * (temp[i] - 268.0) / 30.0
    ev = sum(evap_base)
    if ev <= 0:
        ev = 1.0
    scale_e = n / ev
    for i in range(n):
        evap_base[i] *= scale_e

    wind_speed = [(U[i] * U[i] + V[i] * V[i]) ** 0.5 for i in range(n)]
    m = [0.0] * n
    p_last = [0.0] * n
    for _ in range(14):
        p_last = [0.0] * n
        mnew = [0.0] * n
        for i in range(n):
            sp = max(0.55, wind_speed[i])
            up = _bilinear(m, nx, ny, (i % nx) - U[i] * sp * 1.9,
                           (i // nx) - V[i] * sp * 1.9)
            src = evap_base[i] + 0.965 * up
            lift = _clamp(slope[i] / p90, 0.0, 1.0) if p90 > 0 else 0.0
            k = 0.045 + 0.28 * lift
            loss = src * k
            if loss > src * 0.82:
                loss = src * 0.82
            mnew[i] = src - loss
            p_last[i] = loss
        m = mnew

    mean_p = sum(p_last[i] * area[i] for i in range(n)) / (sum(area) or 1.0)
    scale = (cfg["mean_precip"] / mean_p) if mean_p > 1e-9 else 1.0
    P = [max(0.0, p_last[i] * scale) for i in range(n)]
    return P, U, V


# ════════════════════════════════════════════════════════════════════
# 河流：洼地填充 + 最陡下降 + 汇流
# ════════════════════════════════════════════════════════════════════

def _hydrology(nx, ny, height, sea, ocean, precip, area):
    n = nx * ny
    filled = list(height)
    visited = [False] * n
    heap = []
    for i in range(n):
        if ocean[i]:
            filled[i] = sea
            visited[i] = True
            heapq.heappush(heap, (sea, i))

    while heap:
        h, i = heapq.heappop(heap)
        y, x = divmod(i, nx)
        for dy in (-1, 0, 1):
            yy = y + dy
            if yy < 0 or yy >= ny:
                continue
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                xx = (x + dx) % nx
                j = yy * nx + xx
                if visited[j]:
                    continue
                visited[j] = True
                f = max(height[j], h)
                filled[j] = f
                heapq.heappush(heap, (f, j))

    down = [-1] * n
    for i in range(n):
        if ocean[i]:
            continue
        y, x = divmod(i, nx)
        best = filled[i]
        bj = -1
        for dy in (-1, 0, 1):
            yy = y + dy
            if yy < 0 or yy >= ny:
                continue
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                xx = (x + dx) % nx
                j = yy * nx + xx
                if filled[j] < best - 1e-9:
                    best = filled[j]
                    bj = j
        down[i] = bj

    order = sorted((i for i in range(n) if not ocean[i]), key=lambda i: -filled[i])
    discharge = [0.0] * n
    for i in order:
        discharge[i] += precip[i] * area[i] * 0.55
        j = down[i]
        if j >= 0:
            discharge[j] += discharge[i]

    lake = [False] * n
    for i in range(n):
        if not ocean[i] and filled[i] - height[i] > 0.025 and discharge[i] > 0:
            lake[i] = True

    land_q = [discharge[i] for i in range(n) if not ocean[i] and discharge[i] > 0]
    thr = _percentile(land_q, 0.972) if land_q else 1e18
    river = [False] * n
    for i in range(n):
        if not ocean[i] and discharge[i] >= thr and not lake[i]:
            river[i] = True
    return filled, down, discharge, lake, river


# ════════════════════════════════════════════════════════════════════
# 群系与宜居度
# ════════════════════════════════════════════════════════════════════

def _biomes(cfg, v):
    bands = cfg["biomes"]
    idx = [0] * len(v)
    for i, vi in enumerate(v):
        pick = 0
        for k, b in enumerate(bands):
            if vi >= b["elevation"]:
                pick = k
        idx[i] = pick
    return idx


def _habitat(cfg, ocean, depth, elev, temp, precip):
    n = len(temp)
    out = [0.0] * n
    opt_t = ws._num(ws._get(cfg["pm"], "climate", "temp_optimum_k"), 292.0)
    tol_t = ws._num(ws._get(cfg["pm"], "climate", "temp_tolerance_k"), 30.0)
    for i in range(n):
        ft = math.exp(-((temp[i] - opt_t) / max(8.0, tol_t)) ** 2)
        if ocean[i]:
            h = 0.78 * ft * math.exp(-max(0.0, depth[i]) / 2.2)
        else:
            fw = _clamp(precip[i] / 650.0, 0.0, 1.25)
            fe = math.exp(-max(0.0, elev[i]) / 4.5)
            h = ft * min(1.0, fw) * (0.45 + 0.55 * fe)
        out[i] = _clamp(h, 0.0, 1.0)
    return out


# ════════════════════════════════════════════════════════════════════
# 构建
# ════════════════════════════════════════════════════════════════════

def build(world: dict, res=None, seed=None) -> MapResult:
    nx, ny = res or DEFAULT_RES
    nx = int(_clamp(nx, MIN_SIDE, MAX_SIDE))
    ny = int(_clamp(ny, MIN_SIDE // 2, MAX_SIDE // 2))
    cfg = _cfg(world)
    cfg["nx"], cfg["ny"] = nx, ny
    use_seed = int(seed if seed is not None else cfg["seed"])
    wid = str(ws._get(world, "meta", "id", default="world"))
    rng = random.Random(zlib.crc32((wid + ":" + str(use_seed)).encode("utf-8")))

    lon, lat, area, ux, uy, uz, area_total = _grid(nx, ny, cfg["r_km"])
    cfg["ux"], cfg["uy"], cfg["uz"] = ux, uy, uz
    noise = _Noise(zlib.crc32(("pangu-map:" + wid + ":" + str(use_seed)).encode("utf-8")))

    tec = _tectonics(nx, ny, cfg["r_km"], ux, uy, uz, rng,
                     cfg["plates"], cfg["hotspots"], noise)
    raw = tec["base"]

    relief_total = 2.05 * cfg["relief_km"]
    lo = _percentile(raw, 0.005)
    hi = _percentile(raw, 0.995)
    scale = relief_total / max(1e-6, hi - lo)
    mean_raw = sum(raw[i] * area[i] for i in range(nx * ny)) / area_total
    height = [(raw[i] - mean_raw) * scale for i in range(nx * ny)]

    sea, ocean_frac = _solve_sea(height, area, cfg["inventory"])
    ocean = [height[i] < sea for i in range(nx * ny)]
    # 等ostasy上限：重力越大，地壳能撑起的山越矮。超出的山峰按比例压回。
    peak = max((height[i] - sea for i in range(nx * ny) if not ocean[i]), default=0.0)
    if peak > cfg["relief_km"] > 0:
        f = cfg["relief_km"] / peak
        for i in range(nx * ny):
            if not ocean[i]:
                height[i] = sea + (height[i] - sea) * f
    depth = [max(0.0, sea - height[i]) if ocean[i] else 0.0 for i in range(nx * ny)]
    elev = [max(0.0, height[i] - sea) if not ocean[i] else 0.0 for i in range(nx * ny)]

    max_depth = max(depth) if any(ocean) else 1.0
    max_elev = max(elev) if not all(ocean) else 1.0
    sv = cfg["sea_v"]
    v = [0.0] * (nx * ny)
    for i in range(nx * ny):
        if ocean[i]:
            v[i] = sv * (1.0 - _clamp(depth[i] / max(1e-6, max_depth), 0.0, 1.0)) ** 0.75
        else:
            v[i] = sv + (1.0 - sv) * (_clamp(elev[i] / max(1e-6, max_elev), 0.0, 1.0) ** 0.82)

    temp = _temperature(cfg, lat, area, ux, uy, uz, ocean, depth, elev)
    precip, U, V = _precipitation(cfg, lat, lon, area, height, ocean, elev, temp)
    filled, down, discharge, lake, river = _hydrology(nx, ny, height, sea, ocean, precip, area)
    # 群系不是纯高程带：湿的地方往森林带靠，干的地方往荒原带退
    v_eff = list(v)
    for i in range(nx * ny):
        if ocean[i]:
            continue
        wet = _clamp((precip[i] - 760.0) / 1800.0, 0.0, 0.07)
        dry = _clamp((380.0 - precip[i]) / 900.0, 0.0, 0.09)
        if 0.46 < v[i] < 0.9:
            v_eff[i] = _clamp(v[i] + wet - dry, 0.46, 0.999)
    biome = _biomes(cfg, v_eff)
    habitat = _habitat(cfg, ocean, depth, elev, temp, precip)
    # 高频细节场：给冰盖、陆地和海底一点纹理，避免大面积纯色
    micro = [noise.fbm(ux[i], uy[i], uz[i], 3, 24.0) for i in range(nx * ny)]

    ice_color = cfg["polar_color"]
    biomes = list(cfg["biomes"]) + [
        {"id": "ice", "name": "极冰", "color": ice_color, "elevation": 0.0},
        {"id": "sea_ice", "name": "海冰", "color": ice_color, "elevation": 0.0},
    ]
    ice_idx, sea_ice_idx = len(cfg["biomes"]), len(cfg["biomes"]) + 1
    for i in range(nx * ny):
        edge = (micro[i] - 0.5) * 4.0
        if temp[i] + edge < 265.5 and ocean[i]:
            biome[i] = sea_ice_idx
        elif temp[i] + edge < 268.5 and not ocean[i] and elev[i] > 0.15:
            biome[i] = ice_idx

    stats = _stats(nx, ny, area, area_total, ocean, depth, elev, temp, precip,
                   biome, biomes, habitat, lake, river, tec, cfg)
    checks = _checks(cfg, stats, ocean_frac)
    h = _field_hash(v, temp, precip, habitat, biome)
    meta = {
        "name": str(ws._get(world, "meta", "name", default="")),
        "version": MAP_VERSION,
        "generator": "mapgen",
        "seed": use_seed,
        "res": [nx, ny],
        "sea_level_km": round(sea, 3),
        "relief_total_km": round(relief_total, 2),
        "inventory_km3": round(cfg["inventory"], 1),
        "mean_depth_target_km": round(cfg["mean_depth"], 2),
        "mean_precip_target_mm": round(cfg["mean_precip"], 1),
        "t_mean_k": round(cfg["t_mean"], 1),
        "tidal_locked": bool(cfg["locked"]),
        "plates": cfg["plates"],
        "hotspots": cfg["hotspots"],
        "ocean_fraction": round(ocean_frac, 4),
        "hash": h,
    }

    return MapResult(
        nx=nx, ny=ny, radius_km=cfg["r_km"], lat=lat, lon=lon, area=area,
        area_total=area_total, height=height, sea_level=sea, ocean=ocean,
        depth=depth, elev=elev, v=v, sea_v=sv, temperature=temp, precip=precip,
        habitat=habitat, biome=biome, plate=tec["plate"], boundary=tec["boundary"],
        hotspot=tec["hot"], filled=filled, down=down, discharge=discharge,
        lake=lake, river=river, micro=micro, biomes=biomes, stats=stats,
        checks=checks, hash=h, meta=meta,
        noise_meta={"U": U, "V": V},
    )


def _stats(nx, ny, area, area_total, ocean, depth, elev, temp, precip,
           biome, biomes, habitat, lake, river, tec, cfg):
    n = nx * ny
    A = area_total or 1.0

    def wmean(vals, mask=None):
        s = 0.0
        a = 0.0
        for i in range(n):
            if mask is not None and not mask[i]:
                continue
            s += vals[i] * area[i]
            a += area[i]
        return s / a if a else 0.0

    oce = sum(area[i] for i in range(n) if ocean[i]) / A
    land = 1.0 - oce
    shares = {}
    for b in biomes:
        shares[b["name"]] = 0.0
    for i in range(n):
        shares[biomes[biome[i]]["name"]] += area[i] / A

    land_t = [temp[i] for i in range(n) if not ocean[i]]
    sea_t = [temp[i] for i in range(n) if ocean[i]]
    q = sorted(habitat)
    ice_ids = {len(biomes) - 2, len(biomes) - 1}
    return {
        "ocean_fraction": round(oce, 4),
        "land_fraction": round(land, 4),
        "mean_elevation_km": round(wmean(elev, [not o for o in ocean]), 3),
        "max_elevation_km": round(max(elev) if elev else 0.0, 3),
        "mean_ocean_depth_km": round(wmean(depth, ocean), 3),
        "max_ocean_depth_km": round(max(depth) if depth else 0.0, 3),
        "mean_temperature_k": round(wmean(temp), 2),
        "min_temperature_k": round(min(temp), 2),
        "max_temperature_k": round(max(temp), 2),
        "mean_land_temperature_k": round(sum(land_t) / len(land_t), 2) if land_t else 0.0,
        "mean_sea_temperature_k": round(sum(sea_t) / len(sea_t), 2) if sea_t else 0.0,
        "mean_precip_mm": round(wmean(precip), 1),
        "max_precip_mm": round(max(precip), 1),
        "ice_fraction": round(sum(area[i] for i in range(n) if biome[i] in ice_ids) / A, 4),
        "river_cells": int(sum(1 for r in river if r)),
        "lake_fraction": round(sum(area[i] for i in range(n) if lake[i]) / A, 4),
        "habitat_mean": round(wmean(habitat), 4),
        "habitat_p50": round(q[len(q) // 2], 4) if q else 0.0,
        "plates": len(set(tec["plate"])),
        "convergent_cells": int(tec["conv_cells"]),
        "divergent_cells": int(tec["div_cells"]),
        "transform_cells": int(tec["trans_cells"]),
        "hotspot_cells": int(sum(1 for h in tec["hot"] if h)),
        "biome_shares": shares,
    }


def _checks(cfg, st, ocean_frac):
    return [
        {"id": "M01", "ok": 0.02 < ocean_frac < 0.98,
         "note": f"海洋占比 {ocean_frac:.1%}（水量 {cfg['inventory']:.2e} km³）"},
        {"id": "M02", "ok": st["max_elevation_km"] <= cfg["relief_km"] * 1.25 + 0.1,
         "note": f"最高峰 {st['max_elevation_km']:.2f} km / 重力上限 {cfg['relief_km']:.2f} km"},
        {"id": "M03", "ok": abs(st["mean_temperature_k"] - cfg["t_mean"]) <= 3.0,
         "note": f"均温 {st['mean_temperature_k']:.1f} K / 派生 {cfg['t_mean']:.1f} K"},
        {"id": "M04", "ok": st["river_cells"] > 0, "note": f"河流格 {st['river_cells']}"},
        {"id": "M05", "ok": sum(st["biome_shares"].values()) > 0.999, "note": "群系覆盖 100%"},
        {"id": "M06", "ok": st["habitat_mean"] > 0.02, "note": f"平均宜居度 {st['habitat_mean']:.2f}"},
    ]


def _field_hash(v, temp, precip, habitat, biome):
    b = bytearray()
    step = max(1, len(v) // 20000)
    for i in range(0, len(v), step):
        b.append(int(_clamp(v[i], 0, 1) * 255))
        b.append(int(_clamp((temp[i] - 150) / 500, 0, 1) * 255))
        b.append(int(_clamp(precip[i] / 3000, 0, 1) * 255))
        b.append(int(_clamp(habitat[i], 0, 1) * 255))
        b.append(biome[i] & 255)
    return "%08x" % (zlib.crc32(bytes(b)) & 0xFFFFFFFF)


# ════════════════════════════════════════════════════════════════════
# 出图：重采样与着色
# ════════════════════════════════════════════════════════════════════

def _resample(field, nx, ny, W, H):
    out = [0.0] * (W * H)
    xs = []
    for px in range(W):
        sx = (px + 0.5) * nx / W - 0.5
        x0 = math.floor(sx)
        fx = sx - x0
        xs.append((x0 % nx, (x0 + 1) % nx, fx))
    for py in range(H):
        sy = (py + 0.5) * ny / H - 0.5
        y0 = int(_clamp(math.floor(sy), 0, ny - 1))
        fy = sy - y0
        y1 = min(y0 + 1, ny - 1)
        b0 = y0 * nx
        b1 = y1 * nx
        row = py * W
        for px in range(W):
            x0, x1, fx = xs[px]
            a = field[b0 + x0] * (1 - fx) + field[b0 + x1] * fx
            c = field[b1 + x0] * (1 - fx) + field[b1 + x1] * fx
            out[row + px] = a * (1 - fy) + c * fy
    return out


def _resample_nearest(field, nx, ny, W, H):
    out = [0] * (W * H)
    for py in range(H):
        sy = int(_clamp((py + 0.5) * ny / H, 0, ny - 1))
        row = py * W
        base = sy * nx
        for px in range(W):
            sx = int((px + 0.5) * nx / W) % nx
            out[row + px] = field[base + sx]
    return out


def _lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


def _ramp(stops, t):
    t = _clamp(t, 0.0, 1.0)
    if t <= stops[0][0]:
        return stops[0][1]
    for k in range(len(stops) - 1):
        p0, c0 = stops[k]
        p1, c1 = stops[k + 1]
        if t <= p1:
            u = (t - p0) / max(1e-9, p1 - p0)
            return _lerp3(c0, c1, u)
    return stops[-1][1]


def _shade_color(c, shade):
    return (int(_clamp(c[0] * shade, 0, 255)),
            int(_clamp(c[1] * shade, 0, 255)),
            int(_clamp(c[2] * shade, 0, 255)))


class _Sampled:
    pass


def _sample_grid(res: MapResult, W, H):
    s = _Sampled()
    nx, ny = res.nx, res.ny
    s.v = _resample(res.v, nx, ny, W, H)
    s.temp = _resample(res.temperature, nx, ny, W, H)
    s.precip = _resample(res.precip, nx, ny, W, H)
    s.hab = _resample(res.habitat, nx, ny, W, H)
    s.elev = _resample(res.elev, nx, ny, W, H)
    s.depth = _resample(res.depth, nx, ny, W, H)
    s.biome = _resample_nearest(res.biome, nx, ny, W, H)
    s.ocean = _resample_nearest([1 if o else 0 for o in res.ocean], nx, ny, W, H)
    s.micro = _resample(res.micro, nx, ny, W, H)
    s.plate = _resample_nearest(res.plate, nx, ny, W, H)
    s.boundary = _resample_nearest(res.boundary, nx, ny, W, H)
    s.hot = _resample_nearest([1 if o else 0 for o in res.hotspot], nx, ny, W, H)
    s.W, s.H = W, H
    s.dx = TAU * res.radius_km / W
    s.dy = math.pi * res.radius_km / H
    s.shade = [1.0] * (W * H)
    for py in range(1, H - 1):
        for px in range(W):
            xm = (px - 1) % W
            xp = (px + 1) % W
            hm = s.elev[py * W + xm] + s.depth[py * W + xm] * 0.8
            hp = s.elev[py * W + xp] + s.depth[py * W + xp] * 0.8
            hu = s.elev[(py - 1) * W + px] + s.depth[(py - 1) * W + px] * 0.8
            hd = s.elev[(py + 1) * W + px] + s.depth[(py + 1) * W + px] * 0.8
            dzdx = (hp - hm) / (2 * s.dx)
            dzdy = (hd - hu) / (2 * s.dy)
            nzv = 1.0 / math.sqrt(dzdx * dzdx + dzdy * dzdy + 1.0)
            l = (-0.55 * -dzdx + 0.45 * -dzdy + 0.70) * nzv
            sh = _clamp(0.55 + 0.75 * l, 0.35, 1.45)
            s.shade[py * W + px] = sh if not s.ocean[py * W + px] else 0.75 + (sh - 1.0) * 0.55
    return s


def _coast_mask(s):
    W, H = s.W, s.H
    mask = [False] * (W * H)
    for py in range(H):
        for px in range(W):
            i = py * W + px
            if s.ocean[i]:
                continue
            if (s.ocean[py * W + (px - 1) % W] or s.ocean[py * W + (px + 1) % W]
                    or (py > 0 and s.ocean[(py - 1) * W + px])
                    or (py + 1 < H and s.ocean[(py + 1) * W + px])):
                mask[i] = True
    return mask


def _draw_rivers(px, W, H, res: MapResult, color=(70, 150, 190), width=2):
    nx, ny = res.nx, res.ny
    for i in range(nx * ny):
        if not res.river[i]:
            continue
        y, x = divmod(i, nx)
        X = int((x + 0.5) * W / nx)
        Y = int((y + 0.5) * H / ny)
        cells = [(X, Y)]
        j = res.down[i]
        if j >= 0:
            yy, xx = divmod(j, nx)
            if abs(xx - x) <= 1:
                cells.append((int((xx + 0.5) * W / nx), int((yy + 0.5) * H / ny)))
        for cx, cy in cells:
            for oy in range(-(width // 2), width // 2 + 1):
                for ox in range(-(width // 2), width // 2 + 1):
                    xx = (cx + ox) % W
                    yy = cy + oy
                    if 0 <= yy < H:
                        o = (yy * W + xx) * 3
                        px[o], px[o + 1], px[o + 2] = color


def _render_layer(res: MapResult, layer: str, W, H, s, coast):
    n = W * H
    px = bytearray(n * 3)
    ocean_ramp = [
        (0.0, (5, 14, 26)), (0.25, (8, 30, 50)), (0.55, (12, 60, 86)),
        (0.80, (22, 96, 120)), (1.0, (46, 140, 150)),
    ]
    land_ramp = [
        (0.0, (74, 86, 62)), (0.18, (104, 100, 64)), (0.38, (134, 114, 74)),
        (0.58, (160, 142, 104)), (0.78, (196, 190, 170)), (0.92, (225, 228, 220)),
        (1.0, (248, 250, 250)),
    ]
    temp_ramp = [
        (0.0, (30, 42, 94)), (0.18, (38, 86, 144)), (0.36, (62, 150, 176)),
        (0.52, (156, 200, 150)), (0.68, (232, 196, 94)), (0.84, (226, 120, 60)),
        (1.0, (176, 44, 40)),
    ]
    dry_ramp = [
        (0.0, (86, 66, 44)), (0.22, (132, 112, 66)), (0.45, (110, 140, 76)),
        (0.65, (58, 120, 86)), (0.82, (36, 96, 116)), (1.0, (28, 62, 112)),
    ]
    hab_ramp = [
        (0.0, (10, 18, 28)), (0.18, (24, 48, 50)), (0.40, (44, 96, 66)),
        (0.62, (102, 150, 58)), (0.82, (196, 176, 76)), (1.0, (240, 224, 138)),
    ]
    max_depth = max(0.1, max(res.depth) if res.depth else 0.1)
    max_elev = max(0.1, max(res.elev) if res.elev else 0.1)
    max_precip = max(1.0, _percentile(res.precip, 0.95) if res.precip else 1.0)
    t_lo = _percentile(res.temperature, 0.02)
    t_hi = _percentile(res.temperature, 0.98)
    t_span = max(1.0, t_hi - t_lo)
    plate_cols = [
        (74, 104, 148), (156, 108, 84), (92, 132, 92), (128, 104, 140),
        (168, 140, 84), (78, 128, 132), (140, 84, 84), (96, 112, 156),
        (116, 140, 104), (150, 120, 150), (100, 140, 120), (170, 110, 120),
        (110, 118, 160), (138, 130, 96), (90, 150, 150), (160, 96, 96),
    ]

    for i in range(n):
        o = i * 3
        b = s.biome[i]
        bc = pw.hex_to_rgb(res.biomes[b]["color"]) if b < len(res.biomes) else (128, 128, 128)
        if layer == "elevation":
            if s.ocean[i]:
                dep = s.depth[i] * (0.84 + 0.32 * s.micro[i])
                c = _ramp(ocean_ramp, 1.0 - _clamp(dep / max_depth, 0, 1))
                c = _shade_color(c, 0.62 + 0.38 * s.shade[i])
            else:
                c = _ramp(land_ramp, _clamp((s.elev[i] / max_elev) ** 0.7, 0, 1))
                if s.temp[i] < 271:
                    c = _lerp3(c, (238, 244, 250), 0.55)
                c = _shade_color(c, s.shade[i] * (0.94 + 0.12 * s.micro[i]))
            if coast[i]:
                c = (14, 30, 42)
        elif layer == "biome":
            if b >= len(res.biomes) - 2:
                bc = _lerp3(bc, (198, 218, 238), (s.micro[i] - 0.5) * 0.30)
            if s.ocean[i]:
                dk = _clamp(s.depth[i] / max_depth, 0, 1)
                bc = _lerp3(bc, (6, 18, 32), dk * 0.55)
            else:
                bc = _shade_color(bc, 0.86 + 0.20 * s.micro[i])
            c = _shade_color(bc, 0.88 + 0.24 * (s.shade[i] - 1.0) if not s.ocean[i] else 1.0)
            if coast[i]:
                c = (10, 26, 38)
        elif layer == "temperature":
            t = _clamp((s.temp[i] - t_lo) / t_span, 0, 1)
            c = _ramp(temp_ramp, t)
            if s.ocean[i]:
                c = _lerp3(c, (12, 34, 56), 0.22)
            if coast[i]:
                c = (18, 32, 46)
        elif layer == "precipitation":
            t = _clamp(s.precip[i] / max_precip, 0, 1) ** 0.55
            c = _ramp(dry_ramp, t)
            if s.ocean[i]:
                c = _lerp3(c, (8, 24, 44), 0.45)
            if coast[i]:
                c = (14, 30, 44)
        elif layer == "habitat":
            c = _ramp(hab_ramp, _clamp(s.hab[i], 0, 1))
            if s.ocean[i]:
                c = _lerp3(c, (8, 20, 36), 0.72)
            if coast[i]:
                c = (14, 30, 44)
        elif layer == "tectonics":
            c = plate_cols[s.plate[i] % len(plate_cols)]
            if s.ocean[i]:
                c = _lerp3(c, (10, 22, 38), 0.55)
            bd = s.boundary[i]
            if bd == 1:
                c = (232, 92, 72)
            elif bd == 2:
                c = (72, 200, 210)
            elif bd == 3:
                c = (226, 196, 92)
            if s.hot[i]:
                c = (255, 168, 72)
        elif layer == "relief":
            g = _clamp((s.elev[i] + s.depth[i] * 0.35) / max_elev, 0, 1)
            c = _ramp([(0.0, (34, 44, 48)), (0.35, (92, 92, 82)),
                       (0.65, (168, 162, 146)), (1.0, (240, 242, 238))], g)
            c = _shade_color(c, s.shade[i] if not s.ocean[i] else 0.8)
        else:
            c = bc
        px[o], px[o + 1], px[o + 2] = int(c[0]), int(c[1]), int(c[2])

    if layer in ("elevation", "biome", "relief"):
        _draw_rivers(px, W, H, res, (66, 144, 184), 2 if layer != "relief" else 1)
        for i in range(res.nx * res.ny):
            if not res.lake[i]:
                continue
            y, x = divmod(i, res.nx)
            X = int((x + 0.5) * W / res.nx)
            Y = int((y + 0.5) * H / res.ny)
            for oy in (-1, 0, 1):
                for ox in (-1, 0, 1):
                    xx = (X + ox) % W
                    yy = Y + oy
                    if 0 <= yy < H:
                        o = (yy * W + xx) * 3
                        px[o], px[o + 1], px[o + 2] = (34, 96, 122)
    return W, H, px


def _render_globe(res: MapResult, size=GLOBE_RES, lon0=-38.0, lat0=18.0):
    W = H = size
    px = bytearray(W * H * 3)
    rng = random.Random(90210)
    stars = [(rng.randrange(W), rng.randrange(H), rng.choice([60, 90, 130, 180, 230]))
             for _ in range(260)]
    R = size * 0.46
    cx = cy = size / 2.0
    lx, ly, lz = -0.52, 0.38, 0.76
    ll = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / ll, ly / ll, lz / ll
    sx, sy, sz = -0.30, 0.22, 0.93
    sl = math.sqrt(sx * sx + sy * sy + sz * sz)
    sx, sy, sz = sx / sl, sy / sl, sz / sl

    for py in range(H):
        for pxx in range(W):
            o = (py * W + pxx) * 3
            dx = (pxx + 0.5 - cx) / R
            dy = (cy - (py + 0.5)) / R
            r2 = dx * dx + dy * dy
            if r2 > 1.0:
                base = 6 + int(16 * (1 - min(1.0, ((pxx - cx) ** 2 + (py - cy) ** 2) ** 0.5 / (size * 0.75))))
                px[o], px[o + 1], px[o + 2] = base, base + 6, base + 14
                continue
            z = math.sqrt(max(0.0, 1.0 - r2))
            y2 = dy * math.cos(math.radians(lat0)) + z * math.sin(math.radians(lat0))
            z2 = -dy * math.sin(math.radians(lat0)) + z * math.cos(math.radians(lat0))
            lat = math.degrees(math.asin(_clamp(y2, -1, 1)))
            lon = lon0 + math.degrees(math.atan2(dx, z2))
            if lon > 180:
                lon -= 360
            if lon < -180:
                lon += 360
            x = int((lon + 180.0) / 360.0 * res.nx) % res.nx
            y = int(_clamp(int((90.0 - lat) / 180.0 * res.ny), 0, res.ny - 1))
            i = y * res.nx + x
            bc = pw.hex_to_rgb(res.biomes[res.biome[i]]["color"])
            if res.biome[i] >= len(res.biomes) - 2:
                bc = _lerp3(bc, (198, 218, 238), (res.micro[i] - 0.5) * 0.30)
            elif not res.ocean[i]:
                bc = _shade_color(bc, 0.92 + 0.16 * res.micro[i])
            sh = max(0.0, dx * lx + dy * ly + z * lz)
            sh2 = max(0.0, dx * sx + dy * sy + z * sz)
            lit = 0.16 + 0.80 * (sh ** 0.9) + 0.18 * (sh2 ** 2)
            c = _shade_color(bc, _clamp(lit, 0.10, 1.35))
            rim = _clamp((r2 - 0.80) / 0.20, 0.0, 1.0) ** 1.8
            c = _lerp3(c, (96, 168, 224), rim * 0.55)
            px[o], px[o + 1], px[o + 2] = int(c[0]), int(c[1]), int(c[2])
    for (sx0, sy0, b) in stars:
        if (sx0 - cx) ** 2 + (sy0 - cy) ** 2 > (R * 1.03) ** 2:
            o = (sy0 * W + sx0) * 3
            px[o], px[o + 1], px[o + 2] = b, b, min(255, b + 20)
    return W, H, px


# ════════════════════════════════════════════════════════════════════
# 交互页
# ════════════════════════════════════════════════════════════════════

def _b64(vals, scale=1.0, offset=0.0, raw=False):
    """浮点列 → 1 字节/格 → base64。raw=True 时直接取整（群系索引等）。"""
    if raw:
        b = bytes(int(v) & 255 for v in vals)
    else:
        b = bytes(int(_clamp((v + offset) / scale, 0.0, 1.0) * 255) for v in vals)
    return base64.b64encode(b).decode("ascii")


def _viewer_payload(res: MapResult, W, H):
    vx, vy = 180, 90
    fields = {
        "v": _resample(res.v, res.nx, res.ny, vx, vy),
        "t": _resample(res.temperature, res.nx, res.ny, vx, vy),
        "p": _resample(res.precip, res.nx, res.ny, vx, vy),
        "h": _resample(res.habitat, res.nx, res.ny, vx, vy),
        "e": _resample(res.elev, res.nx, res.ny, vx, vy),
        "d": _resample(res.depth, res.nx, res.ny, vx, vy),
    }
    biome = _resample_nearest(res.biome, res.nx, res.ny, vx, vy)
    ocean = _resample_nearest([1 if o else 0 for o in res.ocean], res.nx, res.ny, vx, vy)
    data = {}
    for k, arr in fields.items():
        if k == "t":
            data[k] = _b64(arr, 500.0, -150.0)
        elif k == "p":
            data[k] = _b64(arr, 3000.0)
        elif k in ("e", "d"):
            data[k] = _b64(arr, 20.0)
        else:
            data[k] = _b64(arr, 1.0)
    data["b"] = _b64(biome, raw=True)
    data["o"] = _b64(ocean, raw=True)
    return {
        "world": res.meta.get("name", ""),
        "version": MAP_VERSION,
        "nx": res.nx, "ny": res.ny, "vx": vx, "vy": vy,
        "sea_v": res.sea_v, "sea_km": res.sea_level,
        "stats": dict(res.stats, seed0=res.meta.get("seed", 0)),
        "checks": res.checks,
        "biomes": [{"name": b["name"], "color": b["color"]} for b in res.biomes],
        "fields": data,
        "layers": {
            "elevation": "map-elevation.png",
            "biome": "map-biome.png",
            "temperature": "map-temperature.png",
            "precipitation": "map-precipitation.png",
            "tectonics": "map-tectonics.png",
            "habitat": "map-habitat.png",
            "relief": "map-relief.png",
        },
        "render": [W, H],
    }


VIEWER_HTML = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>__TITLE__ · 盘古行星地图</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{--bg:#07111e;--ink:#e8f2ff;--dim:#8fa6bf;--acc:#2f8fe0;--line:#1c3a58}
*{box-sizing:border-box}
html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);
  font-family:"Noto Sans SC","Microsoft YaHei",system-ui,sans-serif}
#app{display:grid;grid-template-columns:250px 1fr 250px;grid-template-rows:64px 1fr 44px;height:100%}
header{grid-column:1/-1;display:flex;align-items:center;gap:18px;padding:0 22px;
  border-bottom:1px solid var(--line);background:linear-gradient(90deg,#0a1a2c,#07111e)}
header h1{margin:0;font-size:19px;font-weight:600;letter-spacing:.5px}
header .tag{font-size:11px;color:var(--dim);border:1px solid var(--line);padding:3px 8px;border-radius:20px}
#left,#right{padding:16px;border-right:1px solid var(--line);overflow:auto}
#right{border-right:0;border-left:1px solid var(--line)}
#stage{position:relative;overflow:hidden;background:#03080f;cursor:grab}
#stage.drag{cursor:grabbing}
canvas{display:block;width:100%;height:100%}
.layers{display:flex;flex-direction:column;gap:6px}
.layers button{text-align:left;background:#0b1e32;border:1px solid var(--line);color:var(--dim);
  padding:8px 11px;border-radius:8px;font-size:12.5px;cursor:pointer}
.layers button.on{background:#12395f;color:#fff;border-color:#2f6f9f}
h4{margin:18px 0 8px;font-size:11px;color:var(--dim);font-weight:500;letter-spacing:1.5px}
.kv{display:flex;justify-content:space-between;font-size:11.5px;padding:5px 0;
  border-bottom:1px dashed #17304a;color:var(--dim)}
.kv b{color:var(--ink);font-weight:500;font-variant-numeric:tabular-nums}
.legend{display:flex;flex-wrap:wrap;gap:4px 8px;font-size:10.5px;color:var(--dim)}
.legend i{width:10px;height:10px;border-radius:2px;display:inline-block;margin-right:4px;vertical-align:-1px}
footer{grid-column:1/-1;display:flex;align-items:center;gap:14px;padding:0 22px;
  border-top:1px solid var(--line);font-size:11px;color:var(--dim)}
#probe{position:absolute;pointer-events:none;background:rgba(6,16,28,.92);
  border:1px solid #2a5378;border-radius:8px;padding:8px 10px;font-size:11px;
  line-height:1.6;color:#cfe4f8;display:none;white-space:nowrap;z-index:5}
#hint{position:absolute;right:12px;bottom:12px;font-size:10px;color:#5d7894}
</style></head><body>
<div id="app">
  <header><h1>__TITLE__</h1><span class="tag">行星地图 · __VERSION__</span>
    <span class="tag" id="seed"></span></header>
  <aside id="left">
    <h4>图层</h4><div class="layers" id="layers"></div>
    <h4>读数</h4>
    <div class="kv"><span>海洋占比</span><b id="k-ocean"></b></div>
    <div class="kv"><span>陆地最高</span><b id="k-high"></b></div>
    <div class="kv"><span>海洋最深</span><b id="k-deep"></b></div>
    <div class="kv"><span>平均温度</span><b id="k-temp"></b></div>
    <div class="kv"><span>平均降水</span><b id="k-precip"></b></div>
    <div class="kv"><span>平均宜居度</span><b id="k-hab"></b></div>
    <div class="kv"><span>陆地河流格</span><b id="k-river"></b></div>
    <div class="kv"><span>构造板块</span><b id="k-plates"></b></div>
  </aside>
  <div id="stage"><canvas id="map"></canvas><div id="probe"></div>
    <div id="hint">滚轮缩放 · 拖动平移 · 双击复位</div></div>
  <aside id="right">
    <h4>群系图例</h4><div class="legend" id="legend"></div>
    <h4>体检</h4><div id="checks" style="font-size:11px;line-height:1.9;color:var(--dim)"></div>
    <h4>说明</h4>
    <div style="font-size:11px;line-height:1.8;color:var(--dim)">
      海平面由水量与盆地容积求解；温度含年辐照、温室与海拔递减；
      降水由风带、海陆分布与迎风坡推演；河流为洼地填充后的最陡下降汇流。
      图像为等距圆柱投影，经度环绕。
    </div>
  </aside>
  <footer><span>盘古 · 行星地图</span><span id="clock"></span>
    <span style="margin-left:auto">数字来自 world.json 推演，不是手画的</span></footer>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const $=id=>document.getElementById(id);
const cv=$('map'),ctx=cv.getContext('2d'),stage=$('stage');
const LAYERS=[['elevation','高程与海平面'],['biome','生物群系'],['temperature','年平均温度'],
  ['precipitation','年降水量'],['tectonics','构造板块'],['habitat','宜居度'],['relief','晕渲地形']];
let cur='biome',zoom=1,ox=0,oy=0,drag=null,inited=false;
const imgs={};
function load(){let n=0;const keys=Object.keys(D.layers);
  for(const k of keys){const im=new Image();
    im.onload=()=>{imgs[k]=im;if(++n===keys.length)draw();};
    im.onerror=()=>{if(++n===keys.length)draw();};
    im.src=D.layers[k];}}
function setup(){
  $('seed').textContent='seed '+D.stats.seed0;
  $('k-ocean').textContent=(D.stats.ocean_fraction*100).toFixed(1)+'%';
  $('k-high').textContent=D.stats.max_elevation_km.toFixed(2)+' km';
  $('k-deep').textContent=D.stats.max_ocean_depth_km.toFixed(2)+' km';
  $('k-temp').textContent=D.stats.mean_temperature_k.toFixed(1)+' K';
  $('k-precip').textContent=Math.round(D.stats.mean_precip_mm)+' mm';
  $('k-hab').textContent=D.stats.habitat_mean.toFixed(2);
  $('k-river').textContent=D.stats.river_cells;
  $('k-plates').textContent=D.stats.plates;
  const lg=$('legend');D.biomes.forEach(b=>{const s=document.createElement('span');
    s.innerHTML='<i style="background:'+b.color+'"></i>'+b.name;lg.appendChild(s);});
  D.checks.forEach(c=>{const d=document.createElement('div');
    d.textContent=(c.ok?'✓ ':'! ')+c.id+' '+c.note;d.style.color=c.ok?'#9fc4a8':'#e8b06a';
    $('checks').appendChild(d);});
  $('clock').textContent='等距圆柱 · '+D.nx+'×'+D.ny+' 格 · '+D.version;
  const lb=$('layers');LAYERS.forEach(([k,t])=>{const b=document.createElement('button');
    b.textContent=t;b.dataset.k=k;if(k===cur)b.className='on';
    b.onclick=()=>{cur=k;[...lb.children].forEach(x=>x.className=x.dataset.k===k?'on':'');draw();};
    lb.appendChild(b);});
}
function draw(){
  const w=stage.clientWidth,h=stage.clientHeight;
  cv.width=Math.round(w*devicePixelRatio);cv.height=Math.round(h*devicePixelRatio);
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  ctx.fillStyle='#03080f';ctx.fillRect(0,0,w,h);
  const im=imgs[cur];if(!im)return;
  const s=Math.min(w/im.width,h/im.height)*zoom;
  const dw=im.width*s,dh=im.height*s;
  if(!inited){ox=(w-dw)/2;oy=(h-dh)/2;inited=true;}
  ox = dw<=w ? (w-dw)/2 : Math.min(0, Math.max(w-dw, ox));
  oy = dh<=h ? (h-dh)/2 : Math.min(0, Math.max(h-dh, oy));
  ctx.imageSmoothingEnabled=true;ctx.drawImage(im,ox,oy,dw,dh);
  ctx.strokeStyle='rgba(120,180,240,.22)';ctx.lineWidth=1;
  for(let lon=-150;lon<180;lon+=30){const x=ox+dw*(lon+180)/360;
    ctx.beginPath();ctx.moveTo(x,oy);ctx.lineTo(x,oy+dh);ctx.stroke();}
  for(let lat=-60;lat<=60;lat+=30){const y=oy+dh*(90-lat)/180;
    ctx.beginPath();ctx.moveTo(ox,y);ctx.lineTo(ox+dw,y);ctx.stroke();}
  ctx.strokeStyle='rgba(140,200,255,.28)';ctx.strokeRect(ox,oy,dw,dh);
}
function decode(k){const raw=atob(D.fields[k]);const u=new Uint8Array(raw.length);
  for(let i=0;i<raw.length;i++)u[i]=raw.charCodeAt(i);return u;}
const F={};['v','t','p','h','e','d','b','o'].forEach(k=>F[k]=decode(k));
function probe(ev){
  const r=stage.getBoundingClientRect(),w=r.width,h=r.height;
  const im=imgs[cur];if(!im)return;
  const s=Math.min(w/im.width,h/im.height)*zoom,dw=im.width*s,dh=im.height*s;
  const px=ev.clientX-r.left,py=ev.clientY-r.top;
  if(px<ox||px>ox+dw||py<oy||py>oy+dh){$('probe').style.display='none';return;}
  const lon=((px-ox)/dw)*360-180,lat=90-((py-oy)/dh)*180;
  const x=Math.min(D.vx-1,Math.max(0,Math.floor((lon+180)/360*D.vx)));
  const y=Math.min(D.vy-1,Math.max(0,Math.floor((90-lat)/180*D.vy)));
  const i=y*D.vx+x,ocean=F.o[i]>0,b=F.b[i];
  const elev=(F.e[i]/255)*20,dep=(F.d[i]/255)*20;
  const temp=150+(F.t[i]/255)*500,prec=(F.p[i]/255)*3000,hab=F.h[i]/255;
  const name=D.biomes[b]?D.biomes[b].name:'—';
  $('probe').innerHTML='<b>'+lon.toFixed(1)+'°E · '+lat.toFixed(1)+'°N</b><br>'+
    '群系 '+name+(ocean?' · 海':' · 陆')+'<br>'+
    (ocean?'水深 '+dep.toFixed(1)+' km':'海拔 '+elev.toFixed(1)+' km')+'<br>'+
    '温度 '+temp.toFixed(0)+' K · 降水 '+Math.round(prec)+' mm<br>'+'宜居度 '+hab.toFixed(2);
  $('probe').style.display='block';
  $('probe').style.left=Math.min(w-210,px+14)+'px';
  $('probe').style.top=Math.min(h-120,py+14)+'px';
}
stage.addEventListener('mousemove',e=>{if(drag){const dx=e.clientX-drag.x,dy=e.clientY-drag.y;
  ox+=dx;oy+=dy;drag.x=e.clientX;drag.y=e.clientY;draw();}probe(e);});
stage.addEventListener('mousedown',e=>{drag={x:e.clientX,y:e.clientY};stage.classList.add('drag');});
window.addEventListener('mouseup',()=>{drag=null;stage.classList.remove('drag');});
stage.addEventListener('wheel',e=>{e.preventDefault();const old=zoom;
  zoom=Math.min(6,Math.max(1,zoom*(e.deltaY<0?1.12:0.89)));
  const r=stage.getBoundingClientRect();const mx=e.clientX-r.left,my=e.clientY-r.top;
  ox=mx-(mx-ox)*(zoom/old);oy=my-(my-oy)*(zoom/old);draw();},{passive:false});
stage.addEventListener('dblclick',()=>{zoom=1;ox=oy=0;draw();});
window.addEventListener('resize',draw);
setup();load();
</script></body></html>"""


def _write_viewer(res: MapResult, outdir: str, W, H):
    payload = _viewer_payload(res, W, H)
    title = res.meta.get("name", "") or "行星地图"
    html = (VIEWER_HTML
            .replace("__TITLE__", title)
            .replace("__VERSION__", MAP_VERSION)
            .replace("__DATA__", json.dumps(payload, ensure_ascii=False)))
    path = os.path.join(outdir, "map.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


# ════════════════════════════════════════════════════════════════════
# 对外：出图与检查
# ════════════════════════════════════════════════════════════════════

LAYERS = [
    ("elevation", "map-elevation.png"),
    ("biome", "map-biome.png"),
    ("temperature", "map-temperature.png"),
    ("precipitation", "map-precipitation.png"),
    ("tectonics", "map-tectonics.png"),
    ("habitat", "map-habitat.png"),
    ("relief", "map-relief.png"),
]


def write_outputs(res: MapResult, outdir: str, render=(RENDER_RES[0], RENDER_RES[1]),
                  globe: bool = True, viewer: bool = True) -> dict:
    os.makedirs(outdir, exist_ok=True)
    W, H = int(render[0]), int(render[1])
    s = _sample_grid(res, W, H)
    coast = _coast_mask(s)
    figs = []
    for key, name in LAYERS:
        w, h, px = _render_layer(res, key, W, H, s, coast)
        pw.write_rgb(os.path.join(outdir, name), w, h, px)
        figs.append(name)
    if globe:
        w, h, px = _render_globe(res)
        pw.write_rgb(os.path.join(outdir, "map-globe.png"), w, h, px)
        figs.append("map-globe.png")
    html = _write_viewer(res, outdir, W, H) if viewer else None
    with open(os.path.join(outdir, "map-data.json"), "w", encoding="utf-8") as f:
        json.dump({
            "version": MAP_VERSION, "meta": res.meta, "stats": res.stats,
            "checks": res.checks, "hash": res.hash, "biomes": res.biomes,
            "figures": figs,
        }, f, ensure_ascii=False, indent=2)
    return {"outdir": outdir, "figures": figs, "html": html, "hash": res.hash}


def check(world: dict, res=None, seed=None) -> dict:
    a = build(world, res=res, seed=seed)
    b = build(world, res=res, seed=seed)
    out = {"ok": True, "hash_a": a.hash, "hash_b": b.hash,
           "checks": a.checks, "stats": a.stats, "diffs": []}
    if a.hash != b.hash:
        out["ok"] = False
        out["diffs"].append(f"同 seed 复算不一致：{a.hash} ≠ {b.hash}")
    for k in ("ocean_fraction", "mean_temperature_k", "max_elevation_km", "river_cells"):
        if abs(ws._num(a.stats.get(k), 0) - ws._num(b.stats.get(k), 0)) > 1e-6:
            out["ok"] = False
            out["diffs"].append(f"{k} 复算不一致")
    bad = [c for c in a.checks if not c["ok"]]
    if bad:
        out["ok"] = False
        out["diffs"] += [f"{c['id']} {c['note']}" for c in bad]
    return out


def coarse_fields(res: MapResult, vx=72, vy=36) -> dict:
    hab = _resample(res.habitat, res.nx, res.ny, vx, vy)
    temp = _resample(res.temperature, res.nx, res.ny, vx, vy)
    elev = _resample(res.elev, res.nx, res.ny, vx, vy)
    ocean = _resample_nearest([1 if o else 0 for o in res.ocean], res.nx, res.ny, vx, vy)
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"

    def enc(vals, scale, offset=0.0):
        return "".join(digits[int(_clamp((v + offset) / scale, 0, 0.999) * 36)] for v in vals)

    return {
        "nx": vx, "ny": vy,
        "habitat": enc(hab, 1.0),
        "temperature": enc(temp, 320.0, -180.0),
        "elevation": enc(elev, 12.0),
        "ocean": "".join("1" if o else "0" for o in ocean),
    }


def decode_coarse(field: dict) -> dict:
    """把 coarse_fields 的 base36 解回 0–1 浮点矩阵（给 ca_engine 用）。"""
    digits = {c: i for i, c in enumerate("0123456789abcdefghijklmnopqrstuvwxyz")}
    nx, ny = int(field.get("nx") or 0), int(field.get("ny") or 0)
    if nx <= 0 or ny <= 0:
        return {}
    out = {}
    for k in ("habitat", "temperature", "elevation"):
        s = str(field.get(k) or "")
        if len(s) != nx * ny:
            continue
        out[k] = [digits.get(c, 0) / 36.0 for c in s]
    oc = str(field.get("ocean") or "")
    if len(oc) == nx * ny:
        out["ocean"] = [1.0 if c == "1" else 0.0 for c in oc]
    out["nx"], out["ny"] = nx, ny
    return out
