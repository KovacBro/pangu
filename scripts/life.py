"""
盘古 · 生命的动力学（1.8）
===========================
1.1.4 的 `ca_engine` 是「扩散 + 适应度」的元胞自动机：会动，但**不可解释**——
它能给你一张图，说不出为什么是这个物种数。

这一层给三条有标度、可复算的东西：

1. **中性模型（Hubbell）**：每个个体要么迁入、要么复制邻居。没有适应度，
   只有漂变与迁移，却能维持几十个物种共存。
2. **物种-面积关系**：S ∝ A^z。样地面积在恒定密度下就是个体数，所以用
   Ewens 抽样（第 k 个个体以 θ/(θ+k−1) 的概率是新物种）生成零和群落的
   稳态结构，再嵌套取样拟合 z。
3. **营养级传递**：Lindeman 10% 定律，四级食物链后顶端只剩千分之一。

两个必须说清的口径：

- 中性模型故意**没有适应度**。它给的是「物种数会是多少」，不是「哪个物种会赢」。
- **z 不是常数**。同一条曲线，取样窗口从 16× 换到 1024×，z 从 0.17 走到 0.32；
  格子模型（相关长度只有几格）量出来是 0.7 左右。实测的 0.15–0.35 是大景观尺度
  的平均值，和小样地的高 z 并不矛盾——把 z 当普适常数才是误读。
"""

from __future__ import annotations

import math
import random

THETA = 12.0     # 元群落多样性数 θ = 2·J_M·ν
J_MAX = 8192     # 局域群落的个体数（恒定密度下对应一块样地）


def neutral_grid(n=40, steps=120000, m=0.05, meta_species=40, seed=7) -> dict:
    """二维中性群落：迁移率 m，元群落 meta_species 个物种。

    每一步随机挑一个个体：以概率 m 换成元群落里的随机物种（迁入），
    否则复制四邻之一（繁殖）。没有适应度，物种数由 m 与 J 决定。
    """
    rng = random.Random(seed)
    cells = [rng.randrange(meta_species) for _ in range(n * n)]
    for _ in range(steps):
        i = rng.randrange(n * n)
        if rng.random() < m:
            cells[i] = rng.randrange(meta_species)
        else:
            y, x = divmod(i, n)
            dy, dx = rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
            cells[i] = cells[((y + dy) % n) * n + (x + dx) % n]
    return {"cells": cells, "n": n, "species_total": len(set(cells)), "migration": m}


def metacommunity(theta=THETA, n=J_MAX, seed=7) -> dict:
    """Ewens 抽样：一次生成 n 个个体的物种标签序列（零和群落的稳态）。

    第 k 个个体以 θ/(θ+k−1) 的概率是新物种，否则按已有丰度复制一个。
    这是中性模型解析解的直接实现，不需要假设物种丰度分布的**形状**。
    """
    rng = random.Random(seed)
    labels = []
    abundance = []
    for k in range(1, n + 1):
        if rng.random() < theta / (theta + k - 1.0):
            abundance.append(1)
            labels.append(len(abundance) - 1)
        else:
            j = rng.randrange(k - 1)
            labels.append(labels[j])
            abundance[labels[j]] += 1
    return {"labels": labels, "n": n, "theta": theta, "species_total": len(abundance)}


def species_area(model=None, points=8, window=256.0) -> dict:
    """恒定密度下面积 A ↔ 个体数 J；嵌套前缀取样，拟合 log S = z·log J + c。

    window 是最大个体数与最小个体数之比。拟合窗口必须报出来——
    离开窗口的 z 没有意义。
    """
    model = model or metacommunity()
    labels = model["labels"]
    n = model["n"]
    j_min = max(2, int(n / window))
    js = [int(round(j_min * (n / j_min) ** (i / (points - 1.0)))) for i in range(points)]

    seen = set()
    k = 0
    pts = []
    for j in js:
        while k < j:
            seen.add(labels[k])
            k += 1
        pts.append((j / n, len(seen)))          # (占世界比例, 物种数)

    xs = [math.log(a * n) for a, _ in pts]      # 面积 → 个体数
    ys = [math.log(s) for _, s in pts]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(len(xs)))
    den = sum((xs[i] - mx) ** 2 for i in range(len(xs))) or 1e-12
    z = num / den
    return {"points": pts, "j_min": js[0], "j_max": js[-1],
            "z": round(z, 3), "r2": round(_r2(xs, ys, z, mx, my), 3)}


def _r2(xs, ys, z, mx, my):
    ss = sum((ys[i] - my) ** 2 for i in range(len(ys))) or 1e-12
    res = sum((ys[i] - (my + z * (xs[i] - mx))) ** 2 for i in range(len(ys)))
    return 1.0 - res / ss


def trophic_chain(levels=4, transfer=0.10, npp=100.0) -> dict:
    """Lindeman 10% 定律：每升一级只剩 10%。"""
    chain = []
    v = npp
    for i in range(levels):
        chain.append((i + 1, round(v, 3)))
        v *= transfer
    return {"chain": chain, "top": chain[-1][1], "transfer": transfer}


def demo() -> dict:
    grid = neutral_grid()
    meta = metacommunity()
    sa = species_area(meta)
    spread = (species_area(meta, window=16.0)["z"],
              species_area(meta, window=1024.0)["z"])
    tr = trophic_chain()
    ok_z = 0.15 <= sa["z"] <= 0.40
    ok_sub = sa["z"] < 1.0
    ok_tr = abs(tr["chain"][2][1] / tr["chain"][1][1] - tr["transfer"]) < 1e-9
    return {"grid_total": grid["species_total"], "species_area": sa,
            "spread": spread, "trophic": tr,
            "ok": ok_z and ok_sub and ok_tr,
            "detail": {"z": ok_z, "sublinear": ok_sub, "trophic": ok_tr}}


def report(d: dict) -> str:
    sa = d["species_area"]
    tr = d["trophic"]
    L = ["盘古 · 生命的动力学", "-" * 56]
    L.append(f"  · 中性群落：40×40 格子、{d['grid_total']} 个物种共存"
             f"（没有适应度，只有漂移与迁移）")
    L.append(f"  {'✓' if d['detail']['z'] else '×'} 物种-面积：z = {sa['z']:.3f}"
             f"（个体数 {sa['j_min']}–{sa['j_max']}，R² {sa['r2']:.3f}；"
             f"实测大尺度 0.15–0.35）")
    L.append("      " + " ｜ ".join(f"{a:.3f}→{s}" for a, s in sa["points"][:4]))
    L.append(f"  {'✓' if d['detail']['trophic'] else '×'} 营养级 "
             + " → ".join(f"{v:.2f}" for _, v in tr["chain"]) + "（每级 10%）")
    L.append(f"  结论：{'有标度的生态' if d['ok'] else '有一项没过'}")
    sp = d["spread"]
    L.append(f"  口径：中性模型故意没有适应度；窗口 16× → z {sp[0]:.2f}、"
             f"1024× → z {sp[1]:.2f}，z 不是普适常数。")
    return "\n".join(L)


if __name__ == "__main__":
    print(report(demo()))
