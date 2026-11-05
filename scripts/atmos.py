"""
盘古 · 气候能量平衡与冰-反照率反馈（1.3 / 冰川反馈）
=====================================================
1.1.4 的温度场是「纬度余弦 + 高度 + 海陆」——一个**形状对、物理空**的插值。
这一层换成 Budyko–Sellers 一维能量平衡模型：

    C ∂T/∂t = S(x)·(1−α(T)) − (A + B·T) + D·∂/∂x[(1−x²)·∂T/∂x]

    x = sin(纬度)，S(x) = S₀/4·(1 − 0.482·P₂(x))
    α(T) = 0.30（T > −2 ℃）/ 0.62（有冰）
    A = 203.3 W/m²，B = 2.09 W/m²/℃  （OLR 线性化，Budyko 1969 标定）

它能复现三件 1.1.4 做不到的事：
  1. **冰线**（一年中纬度多高开始有永久冰盖）≈ 72°
  2. **极地放大**（全球 +1 K 时极地 +2~3 K）
  3. **雪球分岔**（太阳常数降约 2% 时，冰线会一路冲到赤道，不可逆）

仍然是简化：一维纬向平均、无海陆差异、无季节、无云。它的价值是**有反馈**——
1.1.4 的场里，冰不会因为变冷而变多。
"""

from __future__ import annotations

import math

S0 = 1361.0
A_OLR = 203.3
B_OLR = 2.09
D_TRANSPORT = 0.60
ALBEDO_OPEN = 0.30
ALBEDO_ICE = 0.62
T_ICE = -2.0          # ℃，低于它算有冰
C_HEAT = 4.0e7        # J/m²/K（有效热容，含海洋混合层）


def _insolation(x: float, s0: float = S0) -> float:
    p2 = 0.5 * (3.0 * x * x - 1.0)
    return s0 / 4.0 * (1.0 - 0.482 * p2)


def _albedo(t: float) -> float:
    return ALBEDO_ICE if t < T_ICE else ALBEDO_OPEN


def _solve_tridiag(a, b, c, d):
    """Thomas 算法：三对角求解（扩散项走隐式，任何步长都稳）。"""
    n = len(d)
    cp = [0.0] * n
    dp = [0.0] * n
    cp[0] = c[0] / b[0]
    dp[0] = d[0] / b[0]
    for i in range(1, n):
        m = b[i] - a[i] * cp[i - 1]
        cp[i] = c[i] / m
        dp[i] = (d[i] - a[i] * dp[i - 1]) / m
    x = [0.0] * n
    x[-1] = dp[-1]
    for i in range(n - 2, -1, -1):
        x[i] = dp[i] - cp[i] * x[i + 1]
    return x


def run(n=48, s0=S0, years=40, dt_days=5.0, t_init=15.0, albedo_ice=None) -> dict:
    """跑到准平衡。扩散项隐式（Thomas），局地项显式。"""
    alb_ice = ALBEDO_ICE if albedo_ice is None else albedo_ice
    xs = [-1.0 + 2.0 * (i + 0.5) / n for i in range(n)]
    dx = 2.0 / n
    T = [t_init] * n
    steps = int(years * 365.0 / dt_days)
    dt = dt_days * 86400.0
    coef = D_TRANSPORT * dt / (C_HEAT * dx * dx)

    for _ in range(steps):
        rhs = [0.0] * n
        for i in range(n):
            alb = alb_ice if T[i] < T_ICE else ALBEDO_OPEN
            solar = _insolation(xs[i], s0) * (1.0 - alb)
            olr = A_OLR + B_OLR * T[i]
            rhs[i] = T[i] + dt / C_HEAT * (solar - olr)
        # 构造 I - coef·L：L 是 d/dx[(1-x²)d/dx] 的中心差分
        a = [0.0] * n
        b = [1.0] * n
        c = [0.0] * n
        # 面心系数：a_{i±1/2} = 1 − x_face²，这样算子对称、守恒
        face_w = [(1.0 - (0.5 * (xs[i - 1] + xs[i])) ** 2) if i > 0 else 0.0
                  for i in range(n)]
        face_e = [(1.0 - (0.5 * (xs[i] + xs[i + 1])) ** 2) if i < n - 1 else 0.0
                  for i in range(n)]
        for i in range(n):
            aw, ae = face_w[i], face_e[i]
            b[i] += coef * (aw + ae)
            a[i] = -coef * aw
            c[i] = -coef * ae
        T = _solve_tridiag(a, b, c, rhs)

    # xs 从南极 (−1) 排到北极 (+1)：赤道在中点，极地取两端的平均
    t_eq = T[n // 2]
    t_pole = 0.5 * (sum(T[:3]) / 3.0 + sum(T[-3:]) / 3.0)
    weights = [math.sqrt(max(1e-12, 1.0 - x * x)) for x in xs]
    wsum = sum(weights)
    t_global = sum(T[i] * weights[i] for i in range(n)) / wsum
    # 冰线：从赤道往两侧找第一格低于 T_ICE 的纬度（两侧取更靠近赤道的那个）
    ice_line = 90.0
    for side in (range(n // 2, n), range(n // 2, -1, -1)):
        for i in side:
            if T[i] < T_ICE:
                lat = abs(math.degrees(math.asin(max(-1.0, min(1.0, xs[i])))))
                ice_line = min(ice_line, lat)
                break
    return {"n": n, "s0": s0, "t_global_c": round(t_global, 2),
            "t_equator_c": round(t_eq, 2), "t_pole_c": round(t_pole, 2),
            "ice_line_deg": round(ice_line, 1), "profile": [round(x, 2) for x in T]}


def polar_amplification() -> dict:
    a = run()
    b = run(s0=S0 * 1.02)
    d_glob = b["t_global_c"] - a["t_global_c"]
    d_pole = b["t_pole_c"] - a["t_pole_c"]
    return {"d_global": round(d_glob, 3), "d_pole": round(d_pole, 3),
            "ratio": round(d_pole / d_glob, 2) if abs(d_glob) > 1e-9 else 0.0}


def snowball_threshold() -> dict:
    """逐步降低太阳常数，找冰线冲到 0° 以下的临界值。"""
    last_ok = 1.0
    for pct in [0.99, 0.98, 0.97, 0.96, 0.95, 0.94]:
        r = run(s0=S0 * pct, years=40)
        if r["ice_line_deg"] <= 5.0:
            return {"threshold": pct, "last_ok": last_ok,
                    "ice_line": r["ice_line_deg"]}
        last_ok = pct
    return {"threshold": None, "last_ok": last_ok, "ice_line": 90.0}


def demo() -> dict:
    base = run()
    amp = polar_amplification()
    snow = snowball_threshold()
    ok_base = 8.0 <= base["t_global_c"] <= 20.0 and 55.0 <= base["ice_line_deg"] <= 80.0
    ok_amp = amp["ratio"] >= 1.5
    ok_snow = snow["threshold"] is not None and snow["threshold"] >= 0.90
    return {"base": base, "amp": amp, "snow": snow,
            "ok": ok_base and ok_amp and ok_snow,
            "detail": {"base": ok_base, "amp": ok_amp, "snow": ok_snow}}


def report(d: dict) -> str:
    b, a, s = d["base"], d["amp"], d["snow"]
    L = ["盘古 · 能量平衡与冰-反照率（Budyko–Sellers）", "-" * 56]
    L.append(f"  {'✓' if d['detail']['base'] else '×'} 全球均温 {b['t_global_c']:.1f} ℃ ｜ "
             f"赤道 {b['t_equator_c']:.1f} ｜ 极地 {b['t_pole_c']:.1f} ｜ "
             f"冰线 {b['ice_line_deg']:.0f}°（实测 ~72°）")
    L.append(f"  {'✓' if d['detail']['amp'] else '×'} 极地放大：全球 +{a['d_global']:.2f} K 时 "
             f"极地 +{a['d_pole']:.2f} K，比值 {a['ratio']:.2f}（实测 2–3）")
    if s["threshold"]:
        L.append(f"  {'✓' if d['detail']['snow'] else '×'} 雪球分岔：太阳常数降到 "
                 f"{s['threshold']:.0%} 时冰线到赤道（Budyko 给 ~2%）")
    else:
        L.append("  × 雪球分岔：没找到阈值")
    L.append(f"  结论：{'有反馈的气候' if d['ok'] else '有一项没过'}")
    return "\n".join(L)


if __name__ == "__main__":
    print(report(demo()))
