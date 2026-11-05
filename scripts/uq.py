"""
盘古 · 误差传播（1.1.5）
========================
1.1.4 给出的是**点值**：「重力 1.76 g」「均温 288 K」。可输入本身有区间——
反照率 0.3±0.05、半径 ±1%、CO₂ ±20%——点值会给人一种它精确到小数点后一位的错觉。

这一层用中心差分把输入区间推到输出：

    σ_out = sqrt( Σ_i (∂f/∂x_i · σ_i)² )

口径（写死，不假装）：
- 输入区间是**假定**，不是测量：默认值写在 `DEFAULT_RANGES`，世界可用
  `meta.uncertainty` 覆盖。所以输出的是「模型对这个假设的敏感度」，
  不是「真值的置信区间」。
- 只做一阶线性传播；强非线性处（雪球分岔、失控温室）会低估，这两处另有基准抓。
- 相关项没有协方差，按独立处理——这是**乐观**估计，报告里要写出来。
"""

from __future__ import annotations

import copy
import json
import math

import world_schema as ws

# 输入区间（1σ 量级的假定）
DEFAULT_RANGES = {
    "albedo": 0.05,        # 绝对
    "solar": 0.01,         # 相对
    "radius": 0.01,        # 相对
    "mass": 0.01,          # 相对
    "pressure": 0.02,      # 相对
    "co2": 0.20,           # 相对
    "tilt": 0.5,           # 绝对（度）
}

LABELS = {
    "albedo": "反照率 ±0.05",
    "solar": "光度 ±1%",
    "radius": "半径 ±1%",
    "mass": "质量 ±1%",
    "pressure": "气压 ±2%",
    "co2": "CO₂ ±20%",
    "tilt": "倾角 ±0.5°",
}


def _body(world):
    for b in (ws._get(world, "cosmology", "bodies", default=[]) or []):
        if isinstance(b, dict) and (ws._num(b.get("radius_km"), 0)
                                    or ws._num(b.get("radius_earth"), 0)):
            return b
    return None


def _scale_stars(w, k):
    for s in (ws._get(w, "cosmology", "stars", default=[]) or []):
        if isinstance(s, dict) and ws._num(s.get("luminosity_solar"), 0):
            s["luminosity_solar"] = ws._num(s["luminosity_solar"]) * k


def _perturb(world, key, delta):
    """按相对/绝对方式扰动一个输入；返回新世界（深拷贝）。"""
    w = copy.deepcopy(world)
    b = _body(w)
    if b is None:
        return w
    if key == "albedo":
        b["albedo"] = max(0.0, ws._num(b.get("albedo"), 0.3) + delta)
    elif key == "solar":
        _scale_stars(w, 1.0 + delta)
    elif key == "radius":
        for f in ("radius_km", "radius_earth"):
            if ws._num(b.get(f), 0):
                b[f] = ws._num(b[f]) * (1.0 + delta)
    elif key == "mass":
        if ws._num(b.get("mass_earth"), 0):
            b["mass_earth"] = ws._num(b["mass_earth"]) * (1.0 + delta)
    elif key == "pressure":
        atm = b.get("atmosphere")
        if isinstance(atm, dict) and ws._num(atm.get("surface_pressure_kpa"), 0):
            atm["surface_pressure_kpa"] = ws._num(atm["surface_pressure_kpa"]) * (1.0 + delta)
    elif key == "co2":
        atm = b.get("atmosphere")
        comp = (atm or {}).get("composition") if isinstance(atm, dict) else None
        if isinstance(comp, dict) and ws._num(comp.get("CO2"), 0):
            comp["CO2"] = ws._num(comp["CO2"]) * (1.0 + delta)
    elif key == "tilt":
        if ws._num(b.get("axial_tilt_deg"), 0):
            b["axial_tilt_deg"] = ws._num(b["axial_tilt_deg"]) + delta
    return w


OUTPUTS = [
    ("U01", "平衡温度", "t_eq_k", "K"),
    ("U02", "地表温度", "t_surface_k", "K"),
    ("U03", "重力", "gravity_g_calc", "g"),
    ("U04", "逃逸速度", "v_escape_km_s", "km/s"),
    ("U05", "密度", "density_gcc_calc", "g/cm³"),
]


def _read(world, bid):
    der = ws.compute_derived(world)
    body = next((b for b in der.get("bodies") or [] if b.get("id") == bid), None)
    out = {}
    if body:
        for _, _, key, _ in OUTPUTS:
            out[key] = ws._num(body.get(key), 0.0)
    return out


def propagate(world: dict, ranges: dict = None) -> dict:
    """对每个输出量做一阶误差传播。"""
    rng = dict(DEFAULT_RANGES)
    rng.update({k: v for k, v in ((ws._get(world, "meta", "uncertainty", default={}) or {}).items())
                if k in rng})
    body = _body(world)
    if body is None:
        return {"rows": [], "ok": False, "note": "没有天体，无法传播"}
    bid = body.get("id")

    base = _read(world, bid)
    sens = {key: {} for _, _, key, _ in OUTPUTS}
    for key, sigma in rng.items():
        if key in ("pressure", "co2", "tilt"):
            # 这三个只影响温度链，跳过不相关的输出
            pass
        hi = _read(_perturb(world, key, sigma), bid)
        lo = _read(_perturb(world, key, -sigma), bid)
        for _, _, out_key, _ in OUTPUTS:
            d = (ws._num(hi.get(out_key), 0) - ws._num(lo.get(out_key), 0)) / 2.0
            if d:
                sens[out_key][key] = d

    rows = []
    for iid, name, key, unit in OUTPUTS:
        val = base.get(key, 0.0)
        pm = math.sqrt(sum(v * v for v in sens[key].values()))
        drivers = sorted(sens[key].items(), key=lambda kv: -abs(kv[1]))[:3]
        rows.append({
            "id": iid, "name": name, "value": round(val, 3),
            "pm": round(pm, 3), "unit": unit,
            "rel": round(pm / val, 4) if val else 0.0,
            "drivers": [{"input": k, "label": LABELS.get(k, k),
                         "d": round(v, 3)} for k, v in drivers],
        })
    return {"id": bid, "rows": rows, "ranges": rng,
            "ok": all(r["pm"] >= 0 for r in rows) and bool(rows),
            "note": "一阶线性、输入独立；强非线性处会低估"}


def _round_pair(v, pm):
    """把 ± 修到两位有效数字，点值按同一小数位截。"""
    if not pm:
        return v, 0.0
    e = math.floor(math.log10(abs(pm)))
    dec = max(0, -e + 1)
    return round(v, dec), round(pm, dec)


def format_value(row) -> str:
    if not row["pm"]:
        return f"{row['value']:g} {row['unit']}"
    v, pm = _round_pair(row["value"], row["pm"])
    return f"{v} ± {pm} {row['unit']}"


def report(d: dict) -> str:
    L = ["盘古 · 误差传播（%s）" % (d.get("id") or "世界"), "-" * 60]
    if not d.get("rows"):
        L.append("  · " + d.get("note", "无数据"))
        return "\n".join(L)
    for r in d["rows"]:
        L.append(f"  · {r['id']} {r['name']:<6} {format_value(r):<22}"
                 f"（相对 {r['rel']:.1%}）")
        if r["drivers"]:
            L.append("      └ 主要来自 " + "、".join(
                f"{x['label']} → {x['d']:+g}" for x in r["drivers"]))
    L.append("-" * 60)
    L.append("  口径：输入区间是假定，不是测量；一阶线性、按独立处理，是乐观估计。")
    return "\n".join(L)


def _earth():
    return {
        "meta": {"id": "earth", "name": "地球"},
        "cosmology": {"stars": [{"id": "SUN", "luminosity_solar": 1.0}],
                      "bodies": [{"id": "earth", "kind": "planet",
                                  "radius_km": 6371.0, "mass_earth": 1.0,
                                  "albedo": 0.306, "axial_tilt_deg": 23.44,
                                  "orbit": {"parent": "SUN", "a_au": 1.0},
                                  "atmosphere": {"surface_pressure_kpa": 101.325,
                                                 "composition": {"CO2": 0.00042}}}]},
    }


def demo() -> dict:
    return propagate(_earth())


if __name__ == "__main__":
    print(report(demo()))
