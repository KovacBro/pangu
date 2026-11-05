"""
盘古 · 适用域声明（1.1.5，2.0 收口）
====================================
一份世界档案里有很多数字。麻烦的是它们**来源不同**：

- **算出来的**：从别的字段推出来的（重力、逃逸速度、平衡温度、温室、NPP、星表…），
  可以带 ±，也可以被复算推翻。
- **经验式**：有模型但是拟合出来的（纬向温度场、降水、群系、Habitable 度）。
- **拍的**：作者写的设定值（反照率、倾角、声明温室、板块速度、演化摘要）。
  它们不是错，但**不能**被当成计算结论。

`certify` 把这三类分开列出来，给一个覆盖率，再把与地球/火星基准的偏差并排放。
这正是 1.1.4 不敢说的话：「我知道哪些数是算的、哪些是估的。」

口径：
- 覆盖率 = 算出来的 / 本表收录的关键结论数。**本表收录的是关键结论，不是每个数字。**
- 偏差表只在能算的地方出现；算不了的地方写「未建模」，不写 0。
- 本模块只读；`pangu certify --write` 才落到 `world["certification"]`。
"""

from __future__ import annotations

import world_schema as ws

KIND_CN = {"computed": "算出来的", "mixed": "半算半填",
           "empirical": "经验式", "declared": "作者声明"}

# 派生量 → uq 的输出编号（用来挂 ±）
PM_MAP = {"t_eq_k": "U01", "t_surface_k": "U02", "gravity_g_calc": "U03",
          "v_escape_km_s": "U04", "density_gcc_calc": "U05"}

MODELED = [
    "平衡温度 / 地表温度（灰体两流 + 水汽反馈）",
    "重力 / 逃逸速度 / 密度（几何推导）",
    "恒星寿命与宜居带（M/L 一阶）",
    "昼长与星图（球面天文，解析解）",
    "CO₂-温度-风化恒温器（ODE）",
    "物种-面积指数与营养级传递（中性模型）",
    "板块速度 / 地幔热流（边界层标度）",
    "冰-反照率分岔（Budyko–Sellers）",
]

EMPIRICAL = [
    "纬向温度场（余弦 + 高度 + 海陆）",
    "降水场（水汽输送 + 地形抬升）",
    "群系划分与宜居度",
    "Miami 模型 NPP",
]

NOT_MODELED = [
    "大气环流 / 洋流环流（没有原始方程）",
    "云与云反馈",
    "板块动力学时间演化（地图是快照，不是历史）",
    "生物地球化学（C/N/P/Fe/S 循环）",
    "文明的决策与技术演化",
    "季节海温滞后、ENSO 类振荡",
]


def _pm_table(world) -> dict:
    try:
        import uq
        d = uq.propagate(world)
    except Exception:  # noqa: BLE001
        return {}
    return {r["id"]: r for r in d.get("rows") or []}


def _claim(path, name, kind, value, pm_row=None, note=""):
    pm = pm_row["pm"] if pm_row else None
    return {"path": path, "name": name, "kind": kind,
            "value": value, "pm": pm, "note": note}


def claims(world: dict) -> list:
    """把散落在 world 里的定量结论收成一张表。"""
    der = ws.compute_derived(world)
    body = (der.get("bodies") or [{}])[0]
    pm = _pm_table(world)
    rows = []

    def add(path, name, kind, value, key=None, note=""):
        if value is None or value == "":
            return
        rows.append(_claim(path, name, kind, value,
                           pm.get(PM_MAP.get(key, "")) if key else None, note))

    add("cosmology.bodies[0].t_eq_k", "平衡温度", "computed", body.get("t_eq_k"),
        "t_eq_k", "不含量温室")
    gh_decl_ = ws._num(body.get("greenhouse_declared_k"), 0)
    gh_est_ = ws._num(body.get("greenhouse_estimated_k"), 0)
    if gh_decl_:
        add("cosmology.bodies[0].t_surface_k", "地表温度", "mixed",
            body.get("t_surface_k"), "t_surface_k",
            f"T_eq + 声明温室 {gh_decl_:g} K（经验式推算 {gh_est_:g} K）")
    else:
        add("cosmology.bodies[0].t_surface_k", "地表温度", "computed",
            body.get("t_surface_k"), "t_surface_k", "T_eq + 成分估算的温室")
    add("cosmology.bodies[0].gravity_g_calc", "重力", "computed",
        body.get("gravity_g_calc"), "gravity_g_calc")
    add("cosmology.bodies[0].v_escape_km_s", "逃逸速度", "computed",
        body.get("v_escape_km_s"), "v_escape_km_s")
    add("cosmology.bodies[0].density_gcc_calc", "密度", "computed",
        body.get("density_gcc_calc"), "density_gcc_calc")

    hz = der.get("hz_au")
    if hz:
        add("cosmology.hz_au", "宜居带", "computed",
            f"{hz[0]:g}–{hz[1]:g} au", note="按 0.53–1.1 S⊕ 通量边界")
    stars = der.get("stars") or []
    if stars:
        add("cosmology.stars[0].ms_lifetime_gyr", "主序寿命", "computed",
            f"{stars[0].get('ms_lifetime_gyr'):g} Gyr", note="t ≈ 10·M/L")

    _ok, _summ, _why = ws.resolve_path(world, "cosmology.bodies[0].planet_map.summary")
    summ = _summ if _ok and isinstance(_summ, dict) else {}
    add("planet_map.summary.mean_temperature_k", "地图均温", "empirical",
        summ.get("mean_temperature_k"), note="纬向余弦 + 高度 + 海陆")
    add("planet_map.summary.mean_precip_mm", "年降水", "empirical",
        summ.get("mean_precip_mm"), note="水汽输送 + 地形抬升")
    add("planet_map.summary.mean_npp_gc_m2_yr", "NPP", "empirical",
        summ.get("mean_npp_gc_m2_yr"), note="Miami 模型")
    add("planet_map.summary.ocean_fraction", "海洋占比", "computed",
        summ.get("ocean_fraction"), note="由水量库存解海平面")

    cap = ws._get(world, "biology", "carrying_capacity", "humans_subsistence", default=None)
    add("biology.carrying_capacity.humans_subsistence", "人口上限", "computed", cap,
        note="NPP → 可采收 → kcal/日")

    # 作者声明
    b = (ws._get(world, "cosmology", "bodies", default=[{}]) or [{}])[0]
    add("cosmology.bodies[0].albedo", "反照率", "declared", b.get("albedo"))
    add("cosmology.bodies[0].axial_tilt_deg", "自转轴倾角", "declared", b.get("axial_tilt_deg"))
    _ok, gh, _why = ws.resolve_path(world, "cosmology.bodies[0].atmosphere.greenhouse_delta_k")
    add("atmosphere.greenhouse_delta_k", "声明温室", "declared",
        gh if _ok else None, note="优先于成分估算")
    st = (ws._get(world, "cosmology", "stars", default=[{}]) or [{}])[0]
    add("cosmology.stars[0].luminosity_solar", "恒星光度", "declared", st.get("luminosity_solar"))
    return rows


def _deviations(world: dict, bench: bool = True) -> list:
    """与地球/火星基准并排；算不了的地方直说。"""
    rows = []
    if bench:
        try:
            import benchmark
            b = benchmark.run()
            for r in b["rows"]:
                rows.append({"target": "地球", "curve": r["name"],
                             "reference": r["target"], "model": r["got"],
                             "unit": r["unit"], "ok": r["ok"]})
        except Exception as e:  # noqa: BLE001
            rows.append({"target": "地球", "curve": "基准",
                         "reference": "—", "model": f"跑不动（{type(e).__name__}）",
                         "unit": "", "ok": None})
    try:
        import radiation
        mars = radiation.solve(co2_ppm=950000.0, s0=586.0, albedo=0.25)["t_surface_k"]
        rows.append({"target": "火星", "curve": "地表温度",
                     "reference": 210.0, "model": mars, "unit": "K",
                     "ok": abs(mars - 210.0) <= 40.0})
    except Exception:  # noqa: BLE001
        pass
    return rows


def run(world: dict, bench: bool = True) -> dict:
    rows = claims(world)
    by_kind = {k: [r for r in rows if r["kind"] == k] for k in KIND_CN}
    total = len(rows)
    computed = len(by_kind["computed"])
    coverage = computed / total if total else 0.0
    return {
        "world": ws._get(world, "meta", "name", default=""),
        "id": ws._get(world, "meta", "id", default=""),
        "version": ws._get(world, "meta", "version", default=""),
        "rows": rows, "by_kind": by_kind,
        "total": total, "computed": computed, "coverage": coverage,
        "deviations": _deviations(world, bench),
        "domains": {"modeled": MODELED, "empirical": EMPIRICAL, "not_modeled": NOT_MODELED},
        "ok": coverage >= 0.30 and computed >= 3,
    }


def _fmt(row) -> str:
    v = row["value"]
    if isinstance(v, (int, float)) and abs(v) >= 1e8:
        s = f"{v / 1e8:.1f} 亿"
    else:
        s = f"{v:g}" if isinstance(v, (int, float)) else str(v)
    if isinstance(row.get("pm"), (int, float)) and row["pm"]:
        try:
            import uq
            vv, pp = uq._round_pair(float(v), row["pm"])
            s = f"{vv} ± {pp}"
        except Exception:  # noqa: BLE001
            s += f" ± {row['pm']:g}"
    return s


def format_report(d: dict) -> str:
    L = [f"盘古 · 适用域声明 ｜ {d['world'] or '世界'} {d['version']}", "-" * 66]
    L.append(f"  {d['total']} 条关键结论：算出来 {len(d['by_kind']['computed'])} 条"
             f" ｜ 半算半填 {len(d['by_kind']['mixed'])} 条"
             f" ｜ 经验式 {len(d['by_kind']['empirical'])} 条"
             f" ｜ 作者声明 {len(d['by_kind']['declared'])} 条"
             f" ｜ 覆盖率 {d['coverage']:.0%}")
    L.append("")
    for kind in ("computed", "mixed", "empirical", "declared"):
        items = d["by_kind"][kind]
        if not items:
            continue
        L.append(f"【{KIND_CN[kind]}】")
        for r in items:
            L.append(f"  · {r['name']:<8} {_fmt(r):<18} {r['path']}")
            if r["note"]:
                L.append(f"      └ {r['note']}")
        L.append("")

    if d["deviations"]:
        L.append("【与基准的偏差】")
        L.append(f"  {'靶':<4}{'曲线':<10}{'参考':>10}{'模型':>10}  判定")
        for r in d["deviations"]:
            mark = "✓" if r.get("ok") else ("×" if r.get("ok") is False else "·")
            ref = r["reference"]
            mod = r["model"]
            L.append(f"  {mark} {r['target']:<4}{r['curve']:<10}"
                     f" {ref if isinstance(ref, str) else f'{ref:g}':>10}"
                     f" {mod if isinstance(mod, str) else f'{mod:g}':>10}  {r['unit']}")
        L.append("")

    L.append("【算得出来 / 算不出来】")
    L.append("  有模型：" + "；".join(d["domains"]["modeled"]))
    L.append("  经验式：" + "；".join(d["domains"]["empirical"]))
    L.append("  没建模：" + "；".join(d["domains"]["not_modeled"]))
    L.append("")
    L.append(f"  结论：{'声明可交' if d['ok'] else '覆盖率过低，别拿它当定量模型'}"
             "（覆盖率 = 算出来的 / 关键结论）")
    return "\n".join(L)


def to_markdown(d: dict) -> str:
    L = [f"## 适用域声明（{d['version']}）", ""]
    L.append(f"本世界共 **{d['total']}** 条关键定量结论：**算出来 {len(d['by_kind']['computed'])}**、"
             f"经验式 {len(d['by_kind']['empirical'])}、作者声明 {len(d['by_kind']['declared'])}，"
             f"覆盖率 **{d['coverage']:.0%}**。")
    L.append("")
    L.append("| 结论 | 值 | 来源 | 字段 |")
    L.append("|---|---|---|---|")
    for r in d["rows"]:
        L.append(f"| {r['name']} | {_fmt(r)} | {KIND_CN[r['kind']]} | `{r['path']}` |")
    L.append("")
    if d["deviations"]:
        L.append("| 靶 | 曲线 | 参考 | 模型 | 单位 | 判定 |")
        L.append("|---|---|---|---|---|---|")
        for r in d["deviations"]:
            mark = "✓" if r.get("ok") else ("×" if r.get("ok") is False else "·")
            ref = r["reference"] if isinstance(r["reference"], str) else f"{r['reference']:g}"
            mod = r["model"] if isinstance(r["model"], str) else f"{r['model']:g}"
            L.append(f"| {r['target']} | {r['curve']} | {ref} | {mod} | {r['unit']} | {mark} |")
        L.append("")
    L.append("**没建模**：" + "；".join(d["domains"]["not_modeled"]) + "。")
    return "\n".join(L)


def demo() -> dict:
    w = {
        "meta": {"id": "earth", "name": "地球", "version": "demo"},
        "cosmology": {"stars": [{"id": "SUN", "luminosity_solar": 1.0}],
                      "bodies": [{"id": "earth", "kind": "planet", "radius_km": 6371.0,
                                  "mass_earth": 1.0, "albedo": 0.306,
                                  "axial_tilt_deg": 23.44,
                                  "orbit": {"parent": "SUN", "a_au": 1.0},
                                  "atmosphere": {"surface_pressure_kpa": 101.325,
                                                 "composition": {"CO2": 0.00042},
                                                 "greenhouse_delta_k": 33.0}}]},
    }
    return run(w, bench=False)


if __name__ == "__main__":
    print(format_report(demo()))
