"""
盘古 · 连续介质内核（1.2）
==========================
1.1.4 的场是「经验式插值」：温度 = 纬度余弦 + 高度 + 海陆。它没有方程，
所以任何「为什么是这个值」都只能回答「因为公式这么写」。

这一层给三种最基本的方程，全部有限体积 / 显式推进，纯标准库：

    ∂T/∂t = α ∇²T          热传导（对解析解）
    ∂u/∂t + c ∂u/∂x = 0    线性平流（看收敛阶）
    ∂h/∂t + ∂(hu)/∂x = 0   线性浅水（看能量守恒）

它们不直接进 `mapgen`——1.2 的意义是**先把数值地基验对**，否则 1.3 的三维环流
只是把经验式换成更贵的经验式。
"""

from __future__ import annotations

import math


# ── 热传导：一维 FTCS ────────────────────────────────────────────────
def heat_1d(nx=64, alpha=0.01, t_end=0.5, cfl=0.2) -> dict:
    """∂T/∂t = α ∂²T/∂x²，边界固定 0，初值 sin(πx)。

    解析解：T(x,t) = sin(πx)·exp(−α π² t)。误差按 L∞ 归一化到初值幅度。
    """
    dx = 1.0 / (nx - 1)
    dt = cfl * dx * dx / alpha
    steps = int(t_end / dt) + 1
    dt = t_end / steps

    T = [math.sin(math.pi * i * dx) for i in range(nx)]
    T[0] = T[-1] = 0.0
    r = alpha * dt / (dx * dx)

    for _ in range(steps):
        new = T[:]
        for i in range(1, nx - 1):
            new[i] = T[i] + r * (T[i - 1] - 2.0 * T[i] + T[i + 1])
        T = new

    decay = math.exp(-alpha * math.pi ** 2 * t_end)
    err = max(abs(T[i] - math.sin(math.pi * i * dx) * decay) for i in range(nx))
    return {"nx": nx, "steps": steps, "r": round(r, 4),
            "l_inf": round(err, 6), "decay": round(decay, 6)}


# ── 平流：一阶迎风 ───────────────────────────────────────────────────
def advect_1d(nx=100, c=1.0, t_end=0.5, cfl=0.5, width=0.08) -> dict:
    """线性平流，周期性边界，高斯初值。返回 L1 误差（用于看收敛阶）。"""
    dx = 1.0 / nx
    dt = cfl * dx / abs(c)
    steps = int(round(t_end / dt))
    dt = t_end / steps

    x = [(i + 0.5) * dx for i in range(nx)]
    u0 = [math.exp(-((xi - 0.3) / width) ** 2) for xi in x]
    u = u0[:]

    coeff = c * dt / dx
    for _ in range(steps):
        new = u[:]
        for i in range(nx):
            im = (i - 1) % nx
            new[i] = u[i] - coeff * (u[i] - u[im])
        u = new

    # 解析：整体平移 c·t（周期域上取最短弧距）
    shift = c * t_end
    l1 = 0.0
    for i in range(nx):
        d = abs(x[i] - 0.3 - shift) % 1.0
        d = min(d, 1.0 - d)
        l1 += abs(u[i] - math.exp(-(d / width) ** 2))
    l1 *= dx
    return {"nx": nx, "steps": steps, "l1": round(l1, 6), "cfl": cfl}


def advect_order() -> dict:
    """两次加密网格，估收敛阶。一阶迎风应给出 ≈1。"""
    a = advect_1d(nx=120)
    b = advect_1d(nx=240)
    order = math.log(a["l1"] / b["l1"], 2) if b["l1"] > 0 else 0.0
    return {"l1_60": a["l1"], "l1_120": b["l1"], "order": round(order, 3)}


# ── 浅水：一维线性（两重力波）────────────────────────────────────────
def shallow_1d(nx=128, c=1.0, t_end=2.0, cfl=0.4) -> dict:
    """线性浅水 ∂u/∂t = −c²∂h/∂x，∂h/∂t = −∂u/∂x（交错网格），看能量守恒。"""
    dx = 1.0 / nx
    dt = cfl * dx / c
    steps = int(t_end / dt)
    dt = t_end / steps

    h = [math.exp(-((i * dx - 0.5) / 0.08) ** 2) for i in range(nx)]
    u = [0.0] * nx

    def energy():
        return sum(h[i] * h[i] for i in range(nx)) * dx

    e0 = energy()
    coeff = c * c * dt / dx
    c2 = dt / dx
    for _ in range(steps):
        un = u[:]
        for i in range(nx):
            un[i] = u[i] - coeff * (h[(i + 1) % nx] - h[i])
        hn = h[:]
        for i in range(nx):
            hn[i] = h[i] - c2 * (un[i] - un[(i - 1) % nx])
        u, h = un, hn

    e1 = energy()
    return {"steps": steps, "e0": round(e0, 6), "e1": round(e1, 6),
            "drift": round(abs(e1 - e0) / max(1e-12, e0), 6)}


def demo() -> dict:
    heat = [heat_1d(nx=n) for n in (48, 96)]
    adv = advect_order()
    sw = shallow_1d()
    ok_heat = max(x["l_inf"] for x in heat) < 1e-2
    ok_order = adv["order"] > 0.8
    ok_sw = sw["drift"] < 0.02
    return {"heat": heat, "advect": adv, "shallow": sw,
            "ok": ok_heat and ok_order and ok_sw,
            "detail": {"heat": ok_heat, "advect": ok_order, "shallow": ok_sw}}


def report(d: dict) -> str:
    L = ["盘古 · 连续介质内核（PDE）", "-" * 56]
    for h in d["heat"]:
        L.append(f"  {'✓' if h['l_inf'] < 1e-2 else '×'} 热传导 nx={h['nx']:<4} "
                 f"L∞ 误差 {h['l_inf']:.2e}（衰减到 {h['decay']:.3f}）")
    a = d["advect"]
    L.append(f"  {'✓' if a['order'] > 0.8 else '×'} 平流收敛阶 {a['order']:.2f}"
             f"（60→120 格，L1 {a['l1_60']:.4f} → {a['l1_120']:.4f}）")
    s = d["shallow"]
    L.append(f"  {'✓' if s['drift'] < 0.02 else '×'} 浅水能量漂移 {s['drift']:.2%}"
             f"（{s['steps']} 步）")
    L.append(f"  结论：{'数值地基可用' if d['ok'] else '有一项没过'}")
    return "\n".join(L)


if __name__ == "__main__":
    print(report(demo()))
