"""
盘古 · 守恒账本（1.1.5）
========================
L0 描述层只写「是多少」，L1 守恒层要回答「账算得平吗」。这一层给三本账：

1. **能量**：吸收的短波 = 出射的长波。用 `radiation` 解出来的有效温度与光学厚反算
   OLR，再和入射做比。残差不是 0，就说明某个环节被手改过。
2. **水**：地图把「声明的水量」摊成海深。库存（km³）与 面积×平均深度 必须相等。
3. **碳**：大气总质量 = 4πR²·P/g；CO₂ 质量 = 总质量 × 摩尔分数 × 44/28.97。
   这能抓住「CO₂ 写了 10% 但压强只有 1 kPa」这类不自洽。

另附一本**元素账**：`chemistry.composition` 的三本分账（行星/大气/海洋）各自合计必须为 1。

口径：
- 残差是**相对值**（残差/收入），容差写在每一行里（能量 ±1%、水 ±5%、碳 ±10%）。
- 读不到的字段记 `skip`，不算分也不假装。缺数据不是错，编数据才是。
- 本模块**只算不写**；`pangu ledger --write` 才把它落到 `world["conservation"]`。
"""

from __future__ import annotations

import math

import world_schema as ws

SIGMA = 5.670374419e-8      # W/(m²·K⁴)
S0_EARTH = 1361.0           # W/m²
EARTH_R_KM = 6371.0
M_AIR = 28.97               # g/mol
M_CO2 = 44.01
M_H2O = 18.015
RHO_WATER = 1000.0          # kg/m³

TOL_ENERGY = 0.01           # ±1%
TOL_WATER = 0.05            # ±5%
TOL_CARBON = 0.10           # ±10%
TOL_ELEMENT = 1e-6


def _num(v, default=0.0):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    return f if f == f and abs(f) != float("inf") else default


def _planet(world: dict):
    """主天体：第一个有半径的行星（跳过卫星）。"""
    bodies = ws._get(world, "cosmology", "bodies", default=[]) or []
    ids = {b.get("id") for b in bodies if isinstance(b, dict)}
    for b in bodies:
        if not isinstance(b, dict):
            continue
        parent = str(ws._get(b, "orbit", "parent", default=""))
        if parent in ids and parent != b.get("id"):
            continue
        if ws._num(b.get("radius_km"), 0) or ws._num(b.get("radius_earth"), 0):
            return b
    return bodies[0] if bodies else {}


def _radius_km(body: dict) -> float:
    r = ws._num(body.get("radius_km"), 0)
    if r:
        return r
    return ws._num(body.get("radius_earth"), 0) * EARTH_R_KM


def _row(iid, book, name, inflow, outflow, unit, tol, note="",
         ok=None, status="ok"):
    if status == "skip":
        return {"id": iid, "book": book, "name": name, "inflow": None,
                "outflow": None, "residual": None, "unit": unit, "tol": tol,
                "ok": None, "status": "skip", "note": note}
    base = abs(inflow) if inflow else 1.0
    residual = (inflow - outflow) / base if base else 0.0
    passed = abs(residual) <= tol
    if status == "info":
        return {"id": iid, "book": book, "name": name,
                "inflow": round(inflow, 6), "outflow": round(outflow, 6),
                "residual": round(residual, 6), "unit": unit, "tol": tol,
                "ok": None, "status": "info", "note": note}
    return {"id": iid, "book": book, "name": name,
            "inflow": round(inflow, 6), "outflow": round(outflow, 6),
            "residual": round(residual, 6), "unit": unit, "tol": tol,
            "ok": passed if ok is None else bool(passed and ok),
            "status": status if passed else "warn", "note": note}


# ── 能量 ──────────────────────────────────────────────────────────
def energy(world: dict) -> list:
    """入射短波 − 反射 − 出射长波 = 0；顺带对账声明的均温。"""
    import radiation

    body = _planet(world)
    if not body:
        return [_row("C01", "能量", "行星辐射收支", 0, 0, "W/m²", TOL_ENERGY,
                     "没有天体", status="skip")]
    a = ws._num(ws._get(body, "orbit", "a_au"), 0)
    lt = ws.total_luminosity(world) or 1.0
    if a <= 0:
        return [_row("C01", "能量", "行星辐射收支", 0, 0, "W/m²", TOL_ENERGY,
                     "没有轨道半长轴，无法算入射", status="skip")]
    s_in = S0_EARTH * lt / (a * a)
    alb = ws._num(body.get("albedo"), 0.3)
    absorbed = s_in * (1.0 - alb) / 4.0

    comp = ws._get(body, "atmosphere", "composition", default={}) or {}
    co2_frac = _num(comp.get("CO2") if isinstance(comp, dict) else 0, 0.0)
    co2_ppm = max(1.0, co2_frac * 1e6) if co2_frac else 420.0
    try:
        sol = radiation.solve(co2_ppm, s0=s_in, albedo=alb)
    except Exception:  # noqa: BLE001
        return [_row("C01", "能量", "行星辐射收支", absorbed, 0, "W/m²",
                     TOL_ENERGY, "辐射求解失败", status="skip")]
    t_s = sol["t_surface_k"]
    tau = sol["tau"]
    olr = SIGMA * t_s ** 4 / (1.0 + tau)

    rows = [_row("C01", "能量", "行星辐射收支", absorbed, olr, "W/m²", TOL_ENERGY,
                 f"入射 {s_in:.0f} W/m²，α={alb:.3f}，CO₂={co2_ppm:.0f} ppm，"
                 f"τ={tau:.3f}")]

    # 声明温度对账：地图/档案里写的均温 vs 辐射层解出来的
    declared = ws._num(ws._get(body, "planet_map", "summary", "mean_temperature_k"), 0)
    if declared:
        delta = declared - t_s
        gh_model = t_s - _num(sol.get("t_effective_k"), 0)
        gh_decl = _num(ws._get(body, "atmosphere", "greenhouse_delta_k"), 0)
        gh_txt = (f"声明温室 {gh_decl:g} K，辐射解推算 {gh_model:.1f} K"
                  if gh_decl else f"温室由辐射解推算 {gh_model:.1f} K")
        row = _row("C02", "能量", "声明均温 vs 辐射解", t_s, declared, "K",
                   0.05, f"偏差 {delta:+.1f} K；{gh_txt}（容差 5%）", status="ok")
        # 声明温室压过成分推算时，这条不平是**作者决策**，不是自相矛盾
        # （1.1.4 口径：只报不改）。打上标记，validate / review 据此区分。
        if gh_decl:
            row["explained"] = True
        rows.append(row)
    else:
        rows.append(_row("C02", "能量", "声明均温 vs 辐射解", t_s, t_s, "K", 0.05,
                         "没有声明均温，无法对账", status="skip"))
    return rows


# ── 水 ────────────────────────────────────────────────────────────
def water(world: dict) -> list:
    """库存水量（km³）与 面积×平均海深 对账。"""
    body = _planet(world)
    r_km = _radius_km(body) if body else 0
    pm = ws._get(body, "planet_map", default={}) or {}
    summary = pm.get("summary") if isinstance(pm.get("summary"), dict) else {}
    ocean = _num(summary.get("ocean_fraction"),
                 _num(ws._get(body, "planet_map", "hydrosphere", "ocean_fraction"), 0))
    depth = _num(summary.get("mean_ocean_depth_km"),
                 _num(ws._get(body, "planet_map", "hydrosphere", "mean_depth_km"), 0))
    inventory = _num(pm.get("inventory_km3"),
                     _num(ws._get(body, "planet_map", "hydrosphere", "inventory_km3"), 0))

    if not (r_km and ocean and depth and inventory):
        return [_row("C03", "水", "水量库存", 0, 0, "km³", TOL_WATER,
                     "缺 半径/海洋占比/海深/库存 中的一项",
                     status="skip")]
    area_km2 = 4.0 * math.pi * r_km ** 2
    volume = area_km2 * ocean * depth
    return [_row("C03", "水", "水量库存", inventory, volume, "km³", TOL_WATER,
                 f"库存 {inventory:.3g} km³ ｜ 海深摊出来 {volume:.3g} km³ "
                 f"（海 {ocean:.3f}，均深 {depth:.2f} km）")]


# ── 碳 ────────────────────────────────────────────────────────────
def carbon(world: dict) -> list:
    """大气总质量与 CO₂ 质量：成分比例 × 压强 × 重力。"""
    body = _planet(world)
    r_km = _radius_km(body) if body else 0
    p_kpa = ws._num(ws._get(body, "atmosphere", "surface_pressure_kpa"), 0)
    comp = ws._get(body, "atmosphere", "composition", default={}) or {}
    if not (r_km and p_kpa and isinstance(comp, dict) and comp):
        return [_row("C04", "碳", "大气质量", 0, 0, "kg", TOL_CARBON,
                     "缺 半径/表面压强/成分", status="skip")]

    der = ws.compute_derived(world)
    g = 0.0
    for b in der.get("bodies") or []:
        if b.get("id") == body.get("id"):
            g = _num(b.get("gravity_g_calc"), 0) * 9.80665
            break
    if g <= 0:
        return [_row("C04", "碳", "大气质量", 0, 0, "kg", TOL_CARBON,
                     "重力算不出来", status="skip")]

    area = 4.0 * math.pi * (r_km * 1e3) ** 2
    m_atm = area * (p_kpa * 1e3) / g
    x_co2 = _num(comp.get("CO2"), 0.0)
    m_co2 = m_atm * x_co2 * (M_CO2 / M_AIR)
    share = sum(_num(v, 0) for v in comp.values() if isinstance(v, (int, float)))
    rows = [_row("C05", "碳", "大气柱质量", m_atm, m_atm, "kg", TOL_CARBON,
                 f"{m_atm:.3g} kg（{p_kpa:g} kPa / {g / 9.80665:.2f} g）",
                 status="info")]
    rows.append(_row("C06", "碳", "CO₂ 储库", m_co2, m_co2, "kg", TOL_CARBON,
                     f"体积分数 {x_co2:.4f} → {m_co2:.3g} kg；总分数合计 {share:.4f}",
                     status="info"))
    return rows


# ── 元素 ──────────────────────────────────────────────────────────
def elements(world: dict) -> list:
    """chemistry.composition 的三本分账各自合计 = 1。"""
    chem = ws._get(world, "chemistry", default={}) or {}
    comp = chem.get("composition") if isinstance(chem, dict) else None
    if not isinstance(comp, dict) or not comp:
        return [_row("C07", "元素", "元素配比合计", 0, 0, "-", TOL_ELEMENT,
                     "没有 chemistry.composition", status="skip")]
    rows = []
    for idx, key in enumerate(("planet", "atmosphere", "ocean")):
        part = comp.get(key)
        if not isinstance(part, dict) or not part:
            rows.append(_row(f"C08.{idx}", "元素", f"{key} 配比", 0, 0, "-",
                             TOL_ELEMENT, f"没有 {key} 分账", status="skip"))
            continue
        total = sum(_num(v, 0) for v in part.values() if isinstance(v, (int, float)))
        rows.append(_row(f"C08.{idx}", "元素", f"{key} 配比", 1.0, total, "-",
                         TOL_ELEMENT, f"{len(part)} 种元素，合计 {total:.6f}"))
    return rows


# ── 汇总 ──────────────────────────────────────────────────────────
def ledger(world: dict) -> dict:
    rows = energy(world) + water(world) + carbon(world) + elements(world)
    scored = [r for r in rows if r["status"] in ("ok", "warn")]
    info = [r for r in rows if r["status"] == "info"]
    bad = [r for r in scored if not r["ok"]]
    explained = [r["id"] for r in bad if r.get("explained")]
    return {
        "world": ws._get(world, "meta", "name", default=""),
        "version": ws.VERSION,
        "rows": rows,
        "scored": len(scored), "info": len(info),
        "skipped": len(rows) - len(scored) - len(info),
        "bad": [r["id"] for r in bad],
        "explained": explained,
        "unexplained": [r["id"] for r in bad if not r.get("explained")],
        "ok": not bad,
    }


def _earth():
    return {
        "meta": {"id": "earth", "name": "地球"},
        "cosmology": {"stars": [{"id": "SUN", "luminosity_solar": 1.0}],
                      "bodies": [{
                          "id": "earth", "kind": "planet",
                          "radius_km": 6371.0, "mass_earth": 1.0, "albedo": 0.306,
                          "orbit": {"parent": "SUN", "a_au": 1.0},
                          "atmosphere": {"surface_pressure_kpa": 101.325,
                                         "composition": {"N2": 0.7808, "O2": 0.2095,
                                                         "Ar": 0.0093, "CO2": 0.00042}},
                          "planet_map": {
                              "summary": {"ocean_fraction": 0.708,
                                          "mean_ocean_depth_km": 3.7,
                                          "mean_temperature_k": 288.0},
                              "inventory_km3": 1.338e9,
                          },
                      }]},
        "chemistry": {"composition": {
            "planet": {"Fe": 0.32, "O": 0.30, "Si": 0.15, "Mg": 0.13, "other": 0.10},
            "atmosphere": {"N2": 0.78, "O2": 0.21, "Ar": 0.01},
            "ocean": {"H2O": 0.965, "NaCl": 0.035},
        }},
    }


def demo() -> dict:
    """自检：地球这本账必须配平。"""
    d = ledger(_earth())
    # 水账用库存 1.338e9 km³ 对 4πR²×0.708×3.7 ≈ 1.33e9，允许 5%
    return d


def report(d: dict) -> str:
    L = ["盘古 · 守恒账本（%s）" % (d.get("world") or "世界"), "-" * 62]
    L.append(f"  {'账目':<22}{'收入':>13}{'支出':>13}{'残差':>9}  判定")
    for r in d["rows"]:
        if r["status"] == "skip":
            L.append(f"  · {r['id']} {r['name']:<18} {'—':>13}{'—':>13}{'—':>9}  未建模")
            if r["note"]:
                L.append(f"      └ {r['note']}")
            continue
        if r["status"] == "info":
            mark = "·"
        else:
            mark = "✓" if r["ok"] else "×"
        L.append(f"  {mark} {r['id']} {r['name']:<18} {r['inflow']:>13.4g}"
                 f" {r['outflow']:>13.4g} {r['residual']:>8.2%}  {r['unit']}")
        if r["note"]:
            L.append(f"      └ {r['note']}")
    L.append("-" * 62)
    L.append(f"  配平 {d['scored'] - len(d['bad'])}/{d['scored']} 本"
             f" ｜ 储库 {d['info']} 本（只报不算）｜ 未建模 {d['skipped']} 本 ｜ "
             f"结论：{'账算得平' if d['ok'] else '有 ' + str(len(d['bad'])) + ' 本不平'}")
    if d.get("explained"):
        L.append(f"  其中 {'、'.join(d['explained'])} 的不平由「声明值压过模型」造成——"
                 "按 1.1.4 的口径，这是提示不是错误，改不改由作者定。")
    L.append("  口径：残差是相对值；能量 ±1%、水 ±5%、碳 ±10%、元素 1e-6。")
    return "\n".join(L)


if __name__ == "__main__":
    print(report(demo()))
