"""
盘古 · 辐射与温室（1.4）
========================
1.1.4 的温室是作者手填的一个 ΔT。这一层把它变成**算出来的**：

    T_s⁴ = T_e⁴ · (1 + τ)              （两流近似，τ 为总红外光学厚）
    τ = τ_H₂O(T_s) + τ_CO₂(c) + τ_other
    τ_H₂O ∝ exp(g·(T_s − 288))         （水汽随温度按指数增长：Clausius–Clapeyron 的线性化）
    τ_CO₂ ∝ log₂(c / 280)              （CO₂ 是饱和吸收，对数是标准形式）

三个已知量用来标定，全部是公开数：
  · 地球 1361 W/m²、α=0.306 → T_e = 255 K
  · 地球实际 T_s = 288 K → 温室 33 K
  · CO₂ 翻倍 → 2.5–4.0 K（IPCC AR6，最佳 3.0）

**这不是逐线辐射传输**：没有谱线、没有云、没有散射相函数。它是一条「带水汽反馈的
灰体两流」，用途是让「换一颗恒星 / 改一份大气」这件事**有响应**，而不是让温度精确到 0.1 K。
"""

from __future__ import annotations

import math

SIGMA = 5.670374419e-8   # W/m²/K⁴
S0_EARTH = 1361.0        # W/m²
ALBEDO_EARTH = 0.306
T_EARTH = 288.0

# 标定：420 ppm 时 τ = 0.631，且水汽反馈 g 使 2×CO₂ ≈ 3 K
TAU_W0 = 0.775           # 未饱和时的水汽光学厚系数
TAU_MAX = 1.6            # 水汽带饱和上限（线饱和；没有它，热世界会无限跑飞）
G_H2O = 0.0245           # 每 K 的光学厚增长（≈ 指数化后的水汽反馈）
A_CO2 = 0.0278           # 每翻倍 CO₂ 的红外光学厚增量
TAU_OTHER = 0.0


def t_effective(s0=S0_EARTH, albedo=ALBEDO_EARTH) -> float:
    return ((1.0 - albedo) * s0 / 4.0 / SIGMA) ** 0.25


def tau_total(t_surf, co2_ppm, t_ref=T_EARTH) -> dict:
    w = TAU_W0 * math.exp(max(-30.0, min(30.0, G_H2O * (t_surf - t_ref))))
    tau_w = TAU_MAX * (1.0 - math.exp(-w / TAU_MAX))
    tau_c = A_CO2 * math.log(max(1e-6, co2_ppm / 280.0), 2.0)
    return {"h2o": tau_w, "co2": tau_c, "total": tau_w + tau_c + TAU_OTHER}


def solve(co2_ppm=420.0, s0=S0_EARTH, albedo=ALBEDO_EARTH,
          t_ref=T_EARTH, iters=200) -> dict:
    """二分求根：T = T_e·(1+τ(T))^¼。

    迭代法在强反馈下会发散；二分法稳定，且「无解」本身有意义——那是失控温室。
    """
    t_e = t_effective(s0, albedo)

    def g(t):
        tau = tau_total(t, co2_ppm, t_ref)["total"]
        return t_e * (1.0 + tau) ** 0.25 - t

    # 从下往上扫第一个「由正转负」的过零点——那才是稳定平衡
    t = None
    prev = 50.0
    for step in range(0, 1500):
        cur = 50.0 + step
        if g(cur) <= 0.0:
            lo, hi = prev, cur
            for _ in range(iters):
                mid = 0.5 * (lo + hi)
                if g(mid) > 0:
                    lo = mid
                else:
                    hi = mid
            t = 0.5 * (lo + hi)
            break
        prev = cur
    if t is None:                       # 1500 K 处仍在增温：失控温室
        tau = tau_total(1500.0, co2_ppm, t_ref)
        return {"t_surface_k": 1500.0, "t_effective_k": round(t_e, 2),
                "greenhouse_k": round(1500.0 - t_e, 1), "tau": round(tau["total"], 3),
                "tau_h2o": round(tau["h2o"], 3), "tau_co2": round(tau["co2"], 3),
                "co2_ppm": co2_ppm, "albedo": albedo, "s0": s0, "runaway": True}
    tau = tau_total(t, co2_ppm, t_ref)
    return {"t_surface_k": round(t, 2), "t_effective_k": round(t_e, 2),
            "greenhouse_k": round(t - t_e, 2), "tau": round(tau["total"], 4),
            "tau_h2o": round(tau["h2o"], 4), "tau_co2": round(tau["co2"], 4),
            "co2_ppm": co2_ppm, "albedo": albedo, "s0": s0, "runaway": False}


def sensitivity(co2_ppm=420.0, factor=2.0, **kw) -> dict:
    """CO₂ 翻倍/减半的平衡温度响应（含水汽反馈）。"""
    a = solve(co2_ppm, **kw)
    b = solve(co2_ppm * factor, **kw)
    return {"t0": a["t_surface_k"], "t1": b["t_surface_k"],
            "dt": round(b["t_surface_k"] - a["t_surface_k"], 2),
            "factor": factor}


def demo() -> dict:
    earth = solve()
    dbl = sensitivity()
    mars = solve(co2_ppm=950000.0, s0=586.0, albedo=0.25)   # 火星：稀薄但 CO₂ 为主
    hot = solve(co2_ppm=420.0, s0=1361.0 * 1.47, albedo=0.30)  # 赫利孔量级
    ok_earth = abs(earth["greenhouse_k"] - 33.0) <= 2.0
    ok_2x = 1.0 < dbl["dt"] < 5.0
    return {"earth": earth, "double": dbl, "mars": mars, "hot": hot,
            "ok": ok_earth and ok_2x,
            "detail": {"earth": ok_earth, "double": ok_2x}}


def report(d: dict) -> str:
    e, x = d["earth"], d["double"]
    L = ["盘古 · 辐射与温室（带水汽反馈的灰体两流）", "-" * 56]
    L.append(f"  {'✓' if d['detail']['earth'] else '×'} 地球 T_e {e['t_effective_k']:.1f} K "
             f"→ T_s {e['t_surface_k']:.1f} K ｜ 温室 {e['greenhouse_k']:.1f} K（实测 33）")
    L.append(f"      τ = {e['tau']:.3f}（水汽 {e['tau_h2o']:.3f} + CO₂ {e['tau_co2']:.3f}）")
    L.append(f"  {'✓' if d['detail']['double'] else '×'} CO₂ 翻倍 → {x['dt']:+.2f} K"
             f"（AR6 2.5–4.0，最佳 3.0）")
    L.append(f"  · 火星量级（S=586、α=0.25、CO₂ 95%）→ {d['mars']['t_surface_k']:.0f} K")
    L.append(f"  · 1.47 L☉ 的赫利孔量级 → {d['hot']['t_surface_k']:.0f} K")
    L.append(f"  结论：{'温室能算了' if d['ok'] else '标定没对上'}")
    return "\n".join(L)


if __name__ == "__main__":
    print(report(demo()))
