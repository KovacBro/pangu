"""
盘古 · 固体地球（1.5）
=======================
1.1.4 的板块是 Voronoi 静态快照：有「形」，没有「动力学」，也没有「史」。

这一层给三条**能对表**的东西，全部来自边界层理论（Turcotte & Schubert）：

1. **瑞利数临界值**：自由-自由边界 Ra_c = 27π⁴/4 ≈ 657.5；刚-刚边界 1707.8。
   先扫波数求 Ra_c(k) = (k²+π²)³/k² 的最小值，确认这个数不是背下来的。
2. **板块速度**：v ≈ κ/d · (Ra/Ra_c)^(2/3)，地球量级应落在 1–10 cm/yr。
3. **地幔热流**：q = k·ΔT/d，与观测 60–90 mW/m² 对表。

**这不是二维对流求解**：没有流场、没有俯冲带、没有威尔逊旋回。它给的是**标度**，
用来回答「这颗行星的板块动得快不快、地热够不够」，而不是「这块大陆什么时候裂开」。
"""

from __future__ import annotations

import math

KAPPA = 1e-6          # m²/s，地幔热扩散率
K_COND = 3.0          # W/m/K，热导率
RA_CRIT_FREE = 27.0 * math.pi ** 4 / 4.0
RA_CRIT_RIGID = 1707.762
D_MANTLE = 2.9e6      # m，地幔厚度
DT_MANTLE = 1500.0    # K，上下边界温差


def rayleigh_critical() -> dict:
    """扫波数找 Ra_c(k) 的最小值（自由-自由）。"""
    best_k, best_ra = 0.0, 1e18
    k = 0.05
    while k < 10.0:
        ra = (k * k + math.pi ** 2) ** 3 / (k * k)
        if ra < best_ra:
            best_ra, best_k = ra, k
        k += 0.001
    return {"k": round(best_k, 4), "ra_critical": round(best_ra, 2),
            "exact_free": round(RA_CRIT_FREE, 2),
            "exact_rigid": RA_CRIT_RIGID,
            "error": round(abs(best_ra - RA_CRIT_FREE) / RA_CRIT_FREE, 5)}


def rayleigh_number(alpha=3e-5, g=9.81, dt=DT_MANTLE, d=D_MANTLE,
                    kappa=KAPPA, nu=1e17) -> float:
    """Ra = α g ΔT d³ / (κ ν)。α 热膨胀，ν 运动黏度。"""
    return alpha * g * dt * d ** 3 / (kappa * nu)


def plate_speed(ra=None, kappa=KAPPA, d=D_MANTLE) -> dict:
    """v ≈ κ/d · (Ra/Ra_c)^(2/3)（边界层标度，Turcotte & Schubert §4）。"""
    ra = rayleigh_number() if ra is None else ra
    ratio = max(1e-9, ra / RA_CRIT_RIGID)
    v = kappa / d * ratio ** (2.0 / 3.0)
    return {"ra": round(ra, 1), "ra_over_rc": round(ratio, 3),
            "speed_cm_yr": round(v * 100.0 * 3.15576e7, 3)}


def nusselt(ra=None) -> float:
    """Nu ≈ (Ra/Ra_c)^(1/3)：对流把热输运放大的倍数。"""
    ra = rayleigh_number() if ra is None else ra
    return max(1.0, (ra / RA_CRIT_RIGID) ** (1.0 / 3.0))


def heat_flux(dt=DT_MANTLE, d=D_MANTLE, k=K_COND, ra=None) -> float:
    """q = k·ΔT/δ，边界层厚度 δ = d/Nu。"""
    nu = nusselt(ra)
    return k * dt / (d / nu) * 1000.0   # mW/m²


def demo() -> dict:
    rc = rayleigh_critical()
    v = plate_speed()
    q = heat_flux()
    ok_rc = rc["error"] < 0.01
    ok_v = 0.5 <= v["speed_cm_yr"] <= 15.0
    ok_q = 40.0 <= q <= 120.0
    return {"rc": rc, "velocity": v, "flux_mw_m2": round(q, 1),
            "ok": ok_rc and ok_v and ok_q,
            "detail": {"rc": ok_rc, "v": ok_v, "q": ok_q}}


def report(d: dict) -> str:
    rc, v = d["rc"], d["velocity"]
    L = ["盘古 · 固体地球标度", "-" * 56]
    L.append(f"  {'✓' if d['detail']['rc'] else '×'} 临界瑞利数：扫描得 {rc['ra_critical']:.1f}"
             f"（精确 {rc['exact_free']:.1f}，刚-刚 {rc['exact_rigid']:.0f}）")
    L.append(f"  {'✓' if d['detail']['v'] else '×'} 板块速度：Ra = {v['ra']:.1e}"
             f"（{v['ra_over_rc']:.1f}×Ra_c）→ {v['speed_cm_yr']:.1f} cm/yr（实测 1–10）")
    L.append(f"  {'✓' if d['detail']['q'] else '×'} 地幔热流 {d['flux_mw_m2']:.0f} mW/m²"
             f"（实测 60–90）")
    L.append(f"  结论：{'标度对得上' if d['ok'] else '有一项偏了'}")
    L.append("  口径：边界层标度，不是二维对流求解；没有俯冲带与威尔逊旋回。")
    return "\n".join(L)


if __name__ == "__main__":
    print(report(demo()))
