"""
盘古 · 地球基准（1.1.4 增补）

把地球参数喂进引擎，拿引擎算出来的六条曲线去对公开数据。
这张表是「模型」与「美术」的分界线：能对表，才谈得上误差；对不上，就老实写偏差。

口径（全部写死在输出里）：
  · 纬向温度   —— 10° 带年均地表温度，参考 NASA GISS 分区平均（1951–1980 基线，+0.5 K 到 2020s）
  · 纬向降水   —— 10° 带年降水，参考 GPCC/WMO 分区平均
  · 昼长       —— 引擎的解析解 vs 独立数值积分（把时角扫 720 步，数太阳在地平线上的比例）
  · 逃逸速度   —— 引擎派生值 vs 11.186 km/s
  · 平衡温度   —— 引擎派生值 vs 255 K（(1−α)S/4σ 标准解）
  · 陆地 NPP   —— 引擎 Miami 模型积分 vs 56 Gt C/yr（IPCC 量级）
  · 板块速度   —— 未建模（声明式字段），只报不算分

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
                    "hydrosphere": {"mean_depth_km": 3.7},
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
    passed = sum(1 for r in rows if r["ok"])
    return {
        "rows": rows, "pairs": {"t": t_pairs, "p": p_pairs},
        "passed": passed, "total": len(rows),
        "ok": passed >= len(rows) - 1,
        "plate_speed": {"modeled": False, "reference": EARTH_PLATE_SPEED,
                        "note": "板块速度尚未建模（声明式字段，默认 3 cm/yr）"},
        "map_stats": {"t_mean_k": res_map.stats.get("mean_temperature_k"),
                      "precip_mm": res_map.stats.get("mean_precip_mm"),
                      "land_fraction": res_map.stats.get("land_fraction")},
    }


def format_report(b: dict) -> str:
    L = ["盘古 · 地球基准（benchmark earth）",
         "-" * 58,
         "  把地球参数喂进引擎，拿六条曲线去对公开数据。",
         ""]
    for r in b["rows"]:
        mark = "✓" if r["ok"] else "×"
        L.append(f"  {mark} {r['id']} {r['name']:<8} 目标 {r['target']:<8g} "
                 f"实测 {r['got']:<8g} {r['unit']}")
        if r["note"]:
            L.append(f"       └ {r['note']}")
    L.append(f"  · B07 板块速度     未建模（参考 {b['plate_speed']['reference']:g} cm/yr，"
             "声明式字段，不计分）")
    L.append("")
    L.append(f"  通过 {b['passed']}/{b['total']} ｜ "
             f"结论：{'经得起对表' if b['ok'] else '有偏差，已如实列出'}")
    L.append("")
    L.append("  口径：温度/降水/昼长是模型实算，NPP 是 Miami 模型积分；")
    L.append("        板块速度、洋流、季节场尚未建模——已知偏差，不假装。")
    return "\n".join(L)


if __name__ == "__main__":
    print(format_report(run()))
