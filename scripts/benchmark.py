"""
盘古 · 地球基准（1.1.4 起步 / 1.1.5 扩到 25 条）

把地球参数喂进引擎，拿引擎算出来的曲线去对公开数据。
这张表是「模型」与「美术」的分界线：能对表，才谈得上误差；对不上，就老实写偏差。

口径（全部写死在输出里）：
  · 纬向温度   —— 10° 带年均地表温度，参考 NASA GISS 分区平均（1951–1980 基线，+0.5 K 到 2020s）
  · 纬向降水   —— 10° 带年降水，参考 GPCC/WMO 分区平均
  · 昼长       —— 引擎的解析解 vs 独立数值积分（把时角扫 720 步，数太阳在地平线上的比例）
  · 逃逸速度   —— 引擎派生值 vs 11.186 km/s
  · 平衡温度   —— 引擎派生值 vs 255 K（(1−α)S/4σ 标准解）
  · 陆地 NPP   —— 引擎 Miami 模型积分 vs 56 Gt C/yr（IPCC 量级）
  · B08–B22    —— 1.2–1.8 六个内核各自的对表指标（辐射、PDE、固体地球、能量平衡、
                  轨道、碳循环、生态），见 `_engine_rows`
  · B23–B25    —— 守恒账本给出的储库量（大气柱、CO₂、海水）

规矩：**曲线只增不减**。删一条 = 承认退步，必须写进 CHANGELOG 的「已知退步」。

用法：
    python scripts/pangu.py benchmark earth
    python scripts/pangu.py benchmark earth --json
"""

import math

import mapgen as mg
import sky as sk
import world_schema as ws

# ── 参考数据 ──────────────────────────────────────────────────────
# (纬度, 年均温度 °C)
ZONAL_T = [
    (85, -28.0), (75, -17.0), (65, -7.0), (55, 0.0), (45, 6.0),
    (35, 13.0), (25, 19.0), (15, 24.0), (5, 26.0),
    (-5, 26.0), (-15, 23.0), (-25, 18.0), (-35, 12.0), (-45, 6.0),
    (-55, 0.0), (-65, -12.0), (-75, -28.0), (-85, -45.0),
]

# (纬度, 年降水 mm/yr)
ZONAL_P = [
    (85, 150.0), (75, 300.0), (65, 600.0), (55, 800.0), (45, 900.0),
    (35, 800.0), (25, 600.0), (15, 1000.0), (5, 1700.0),
    (-5, 1600.0), (-15, 1100.0), (-25, 700.0), (-35, 800.0), (-45, 1100.0),
    (-55, 1100.0), (-65, 700.0), (-75, 300.0), (-85, 100.0),
]

EARTH_V_ESC = 11.186      # km/s
EARTH_T_EQ = 255.0        # K
EARTH_LAND_NPP = 56.0     # Gt C/yr
EARTH_PLATE_SPEED = 5.0   # cm/yr

# 判据（设计意图，不是事后调出来的数）
TARGET_T_RMSE = 8.0       # K
TARGET_P_R = 0.70
TARGET_DAY_RMSE = 0.10    # h
TARGET_ANALYTIC_REL = 0.02
TARGET_NPP_REL = 0.35

# 1.1.5 新增曲线的靶（每条都对着公开数或解析解）
TARGET_GH = 33.0          # K，地球温室
TARGET_2XCO2 = 3.0        # K，AR6 2.5–4.0
TARGET_MARS_T = 210.0     # K，火星年均地表
TARGET_HEAT_FLUX = (60.0, 90.0)     # mW/m²
TARGET_PLATE_SPEED = (1.0, 10.0)    # cm/yr
TARGET_T_GLOBAL = (12.0, 17.0)      # ℃
TARGET_AMP = (2.0, 3.0)             # 极地放大比
TARGET_LEAPFROG = 1e-6
TARGET_PRECESS = 43.0     # ″/世纪
TARGET_TIDE_MS = 1.8      # ms/世纪
TARGET_RELAX = (1e5, 5e6)  # yr
TARGET_SPECIES_AREA = (0.15, 0.40)
EARTH_ATM_MASS = 5.148e18  # kg
EARTH_CO2_MASS = 3.2e15    # kg
EARTH_OCEAN_MASS = 1.4e21  # kg

PLATE_SPEED_DECLARED = 5.0  # 仅作旧字段的兜底


def earth_world() -> dict:
    """构造一个只有必要字段的地球，用引擎自己的路径算。"""
    return {
        "meta": {"id": "earth", "name": "地球", "version": "benchmark"},
        "physics": {"constants": [{"id": "G", "symbol": "G", "world_value": 6.674e-11,
                                   "earth_value": 6.674e-11, "unit": "m^3/(kg·s^2)"}]},
        "cosmology": {
            "has_stars": True,
            "stars": [{"id": "SUN", "name": "太阳", "class": "G2V",
                       "mass_solar": 1.0, "radius_solar": 1.0, "luminosity_solar": 1.0,
                       "temp_k": 5772, "color": "#FFF4E0",
                       "orbit": {"parent": "barycenter", "a_au": 0.0, "period_days": 0}}],
            "bodies": [{
                "id": "earth", "name": "地球", "kind": "planet",
                "radius_km": 6371.0, "radius_earth": 1.0, "mass_earth": 1.0,
                "density_gcc": 5.514, "gravity_g": 1.0,
                "rotation_hours": 23.934, "axial_tilt_deg": 23.44, "albedo": 0.306,
                "orbit": {"parent": "SUN", "a_au": 1.0, "period_days": 365.256},
                "atmosphere": {
                    "surface_pressure_kpa": 101.325,
                    "composition": {"N2": 0.7808, "O2": 0.2095, "Ar": 0.0093,
                                    "CO2": 0.00042, "CH4": 0.0000019},
                },
                "planet_map": {
                    "tectonics": {"plates": 12, "hotspots": 4, "sea_level": 0.46},
                    "hydrosphere": {"mean_depth_km": 3.7, "ocean_fraction": 0.708,
                                    "inventory_km3": 1.338e9},
                    "climate": {"mean_precip_mm": 900},
                },
            }],
            "calendar": {"day_hours": 23.934, "year_days": 365.256, "months": 12},
            "surface": {"observer": {"lat_deg": 0.0, "lon_deg": 0.0, "alt_m": 0}},
        },
    }


# ── 工具 ──────────────────────────────────────────────────────────
def _zonal_mean(values, res, target_lat, half=5.0):
    """按纬度带做面积加权平均（values 是 nx*ny 的展平场）。"""
    nx = res.nx
    s = 0.0
    a = 0.0
    for y in range(res.ny):
        if abs(res.lat[y] - target_lat) > half:
            continue
        base = y * nx
        for x in range(nx):
            i = base + x
            s += values[i] * res.area[i]
            a += res.area[i]
    return (s / a) if a else 0.0


def _rmse(pairs):
    if not pairs:
        return 0.0
    return math.sqrt(sum((x - y) ** 2 for x, y in pairs) / len(pairs))


def _corr(pairs):
    n = len(pairs)
    if n < 2:
        return 0.0
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sx = math.sqrt(sum((p[0] - mx) ** 2 for p in pairs))
    sy = math.sqrt(sum((p[1] - my) ** 2 for p in pairs))
    if sx <= 0 or sy <= 0:
        return 0.0
    return sum((p[0] - mx) * (p[1] - my) for p in pairs) / (sx * sy)


def _daylight_numeric(lat_deg, dec_deg, day_hours, steps=720):
    """独立算法：把时角扫一圈，数太阳在地平线上的比例。"""
    la = math.radians(lat_deg)
    de = math.radians(dec_deg)
    up = 0
    for k in range(steps):
        h = math.radians(-180.0 + 360.0 * k / steps)
        sin_alt = math.sin(la) * math.sin(de) + math.cos(la) * math.cos(de) * math.cos(h)
        if sin_alt > 0:
            up += 1
    return day_hours * up / steps


# ── 1.1.5：六个内核的对表指标 ─────────────────────────────────────
def _row(iid, name, target, got, unit, ok, note=""):
    return {"id": iid, "name": name, "target": target, "got": got,
            "unit": unit, "ok": bool(ok), "note": note}


def _between(x, lo_hi):
    return lo_hi[0] <= x <= lo_hi[1]


def _engine_rows(earth: dict) -> list:
    """把 1.2–1.8 的内核并进同一张表。每个模块只跑一次。"""
    import atmos
    import chem
    import conservation
    import geo
    import life
    import orbit
    import pde
    import radiation

    rows = []

    # 辐射（1.4）
    e = radiation.solve()
    gh = e["greenhouse_k"]
    rows.append(_row("B08", "温室强度", TARGET_GH, gh, "K",
                     abs(gh - TARGET_GH) <= 3.0,
                     f"T_e {e['t_effective_k']} K，τ={e['tau']}"))
    dbl = radiation.sensitivity()["dt"]
    rows.append(_row("B09", "CO₂ 翻倍", TARGET_2XCO2, dbl, "K",
                     2.0 <= dbl <= 4.0, "AR6 2.5–4.0，含水汽反馈"))
    mars = radiation.solve(co2_ppm=950000.0, s0=586.0, albedo=0.25)["t_surface_k"]
    rows.append(_row("B10", "火星地表温度", TARGET_MARS_T, mars, "K",
                     abs(mars - TARGET_MARS_T) <= 40.0,
                     "95% CO₂、586 W/m²、α=0.25；没有沙尘与云"))

    # PDE（1.2）
    p = pde.demo()
    linf = p["heat"][-1]["l_inf"]
    rows.append(_row("B11", "一维热传导", 1e-2, linf, "L∞",
                     linf < 1e-2, "sin(πx) 初始场 vs 解析解，nx=96"))
    order = p["advect"]["order"]
    rows.append(_row("B12", "平流收敛阶", 1.0, order, "阶",
                     0.8 <= order <= 1.2, "一阶迎风，60→120 格"))
    drift = p["shallow"]["drift"]
    rows.append(_row("B13", "浅水能量漂移", 0.02, drift, "rel",
                     drift < 0.02, f"{p['shallow']['steps']} 步交错网格"))

    # 固体地球（1.5）
    g = geo.demo()
    v = g["velocity"]["speed_cm_yr"]
    rows.append(_row("B07", "板块速度", PLATE_SPEED_DECLARED, v, "cm/yr",
                     _between(v, TARGET_PLATE_SPEED),
                     f"Ra={g['velocity']['ra']:.2e}（{g['velocity']['ra_over_rc']:.0f}×Ra_c），"
                     "边界层标度而非对流求解"))
    q = g["flux_mw_m2"]
    rows.append(_row("B14", "地幔热流", 75.0, q, "mW/m²",
                     _between(q, TARGET_HEAT_FLUX), "q = kΔT/δ，δ = d/Nu"))

    # 能量平衡与冰-反照率（1.3）
    a = atmos.demo()
    tg = a["base"]["t_global_c"]
    rows.append(_row("B15", "全球均温", 14.0, tg, "℃",
                     _between(tg, TARGET_T_GLOBAL),
                     f"冰线 {a['base']['ice_line_deg']:.0f}°（实测 ~72°）"))
    amp = a["amp"]["ratio"]
    rows.append(_row("B16", "极地放大", 2.5, amp, "×",
                     _between(amp, TARGET_AMP), "S+2% 时 极地ΔT/全球ΔT"))
    th = a["snow"]["threshold"]
    rows.append(_row("B17", "雪球阈值", 0.98, th or 0.0, "S/S₀",
                     th is not None and th >= 0.93,
                     "Budyko 给 ~2%（即 0.98）；阈值过低 = 反馈太弱"))

    # 轨道（1.6）
    o = orbit.demo()
    le = o["leapfrog"]["drift"]
    rows.append(_row("B18", "辛积分能量漂移", TARGET_LEAPFROG, le, "rel",
                     le < TARGET_LEAPFROG, "KDK leapfrog，2 万步应有界"))
    pre = o["mercury"]["per_century_arcsec"]
    rows.append(_row("B19", "水星近日点进动", TARGET_PRECESS, pre, "″/cy",
                     abs(pre - TARGET_PRECESS) <= 1.0, "6πGM/(c²a(1−e²))"))
    tide = o["tide"]["day_gain_ms_per_century"]
    rows.append(_row("B20", "潮汐去旋", TARGET_TIDE_MS, tide, "ms/cy",
                     abs(tide - TARGET_TIDE_MS) <= 0.6, "地球-月球，k₂=0.3、Q=12"))

    # 碳-硅酸盐（1.7）
    ry = chem.relax()["relax_yr"] or 0.0
    rows.append(_row("B21", "恒温器回落时标", 2e5, round(ry), "yr",
                     _between(ry, TARGET_RELAX), "4×CO₂ 扰动回落到 63%"))

    # 生命（1.8）
    z = life.demo()["species_area"]["z"]
    rows.append(_row("B22", "物种-面积指数", 0.25, z, "z",
                     _between(z, TARGET_SPECIES_AREA), "Ewens 抽样，窗口 32–8192 个体"))

    # 守恒（1.1.5）
    led = conservation.ledger(earth)
    by = {r["id"]: r for r in led["rows"]}
    atm = (by.get("C05") or {}).get("inflow") or 0.0
    rows.append(_row("B23", "大气柱质量", EARTH_ATM_MASS, atm, "kg",
                     abs(atm - EARTH_ATM_MASS) / EARTH_ATM_MASS <= 0.03,
                     "4πR²P/g"))
    co2 = (by.get("C06") or {}).get("inflow") or 0.0
    rows.append(_row("B24", "CO₂ 储库", EARTH_CO2_MASS, co2, "kg",
                     abs(co2 - EARTH_CO2_MASS) / EARTH_CO2_MASS <= 0.15,
                     "总质量 × 摩尔分数 × 44/28.97"))
    vol = (by.get("C03") or {}).get("inflow") or 0.0
    ocean = vol * 1e9 * 1024.0
    rows.append(_row("B25", "海水质量", EARTH_OCEAN_MASS, round(ocean), "kg",
                     abs(ocean - EARTH_OCEAN_MASS) / EARTH_OCEAN_MASS <= 0.10,
                     "库存 km³ × 1024 kg/m³"))
    return rows


# ── 主流程 ────────────────────────────────────────────────────────
def run(earth: dict = None, res=(144, 72)) -> dict:
    earth = earth or earth_world()
    res_map = mg.build(earth, res=res)

    t_pairs = []
    p_pairs = []
    for lat, ref_t in ZONAL_T:
        got = _zonal_mean(res_map.temperature, res_map, lat) - 273.15
        t_pairs.append((ref_t, got))
    for lat, ref_p in ZONAL_P:
        got = _zonal_mean(res_map.precip, res_map, lat)
        p_pairs.append((ref_p, got))

    t_rmse = _rmse(t_pairs)
    p_corr = _corr(p_pairs)

    # 昼长：同一个函数对独立数值积分
    lats = [0.0, 23.44, 45.0, 60.0, 66.5, 75.0]
    decs = [-23.44, 0.0, 23.44]
    day_pairs = []
    for la in lats:
        for de in decs:
            a = sk.daylight_hours(la, de, 24.0)["hours"]
            b = _daylight_numeric(la, de, 24.0)
            day_pairs.append((b, a))
    day_rmse = _rmse(day_pairs)

    der = ws.compute_derived(earth)
    b0 = der["bodies"][0]
    v_esc = b0["v_escape_km_s"]
    t_eq = b0["t_eq_k"]
    v_rel = abs(v_esc - EARTH_V_ESC) / EARTH_V_ESC
    t_rel = abs(t_eq - EARTH_T_EQ) / EARTH_T_EQ

    npp_total = res_map.stats.get("land_npp_gtc_yr", 0.0)
    npp_rel = abs(npp_total - EARTH_LAND_NPP) / EARTH_LAND_NPP

    rows = [
        {"id": "B01", "name": "纬向年均温", "unit": "K(rmse)",
         "target": TARGET_T_RMSE, "got": round(t_rmse, 2),
         "ok": t_rmse <= TARGET_T_RMSE,
         "note": "18 个纬度带，参考 GISS 分区平均"},
        {"id": "B02", "name": "纬向年降水", "unit": "r",
         "target": TARGET_P_R, "got": round(p_corr, 3),
         "ok": p_corr >= TARGET_P_R,
         "note": "18 个纬度带，参考 GPCC 分区平均"},
        {"id": "B03", "name": "昼长", "unit": "h(rmse)",
         "target": TARGET_DAY_RMSE, "got": round(day_rmse, 4),
         "ok": day_rmse <= TARGET_DAY_RMSE,
         "note": "6 纬 × 3 赤纬 vs 720 步数值积分"},
        {"id": "B04", "name": "逃逸速度", "unit": "km/s",
         "target": EARTH_V_ESC, "got": v_esc,
         "ok": v_rel <= TARGET_ANALYTIC_REL,
         "note": f"相对误差 {v_rel:.2%}"},
        {"id": "B05", "name": "平衡温度", "unit": "K",
         "target": EARTH_T_EQ, "got": t_eq,
         "ok": t_rel <= TARGET_ANALYTIC_REL,
         "note": f"相对误差 {t_rel:.2%}"},
        {"id": "B06", "name": "陆地 NPP", "unit": "Gt C/yr",
         "target": EARTH_LAND_NPP, "got": npp_total,
         "ok": npp_rel <= TARGET_NPP_REL,
         "note": f"相对误差 {npp_rel:.1%}"},
    ]
    rows += _engine_rows(earth)
    rows.sort(key=lambda r: r["id"])
    passed = sum(1 for r in rows if r["ok"])
    return {
        "rows": rows, "pairs": {"t": t_pairs, "p": p_pairs},
        "passed": passed, "total": len(rows),
        "ok": passed >= len(rows) - 1,
        "plate_speed": {"modeled": True, "reference": EARTH_PLATE_SPEED,
                        "note": "1.1.5 起由 geo 的边界层标度算出（B07）"},
        "map_stats": {"t_mean_k": res_map.stats.get("mean_temperature_k"),
                      "precip_mm": res_map.stats.get("mean_precip_mm"),
                      "land_fraction": res_map.stats.get("land_fraction")},
    }


def format_report(b: dict) -> str:
    L = ["盘古 · 地球基准（benchmark earth）",
         "-" * 62,
         f"  把地球参数喂进引擎，拿 {b['total']} 条曲线去对公开数据。",
         ""]
    for r in b["rows"]:
        mark = "✓" if r["ok"] else "×"
        tgt = r["target"]
        got = r["got"]
        L.append(f"  {mark} {r['id']} {r['name']:<10} 目标 {tgt:<9g} "
                 f"实测 {got:<9g} {r['unit']}")
        if r["note"]:
            L.append(f"       └ {r['note']}")
    L.append("")
    L.append(f"  通过 {b['passed']}/{b['total']} ｜ "
             f"结论：{'经得起对表' if b['ok'] else '有偏差，已如实列出'}")
    L.append("")
    L.append("  口径：B01–B06 是地图与几何，B07–B22 是六个内核各自的解析解/公开数，")
    L.append("        B23–B25 是守恒账本的储库量。没建模的（洋流、云、季节海温、")
    L.append("        板块时间演化、文明）不在这张表里——不建就不打分，不假装。")
    return "\n".join(L)


if __name__ == "__main__":
    print(format_report(run()))
