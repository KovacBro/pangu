"""
盘古 · 碳-硅酸盐循环（1.7）
============================
1.1.4 的大气成分是静态配比：氧不会变多，CO₂ 不会变少，星球没有「地球化学」。

这一层接上 Walker–Hays–Kasting 的负反馈：

    dCO₂/dt = V − W₀·(CO₂/CO₂₀)·exp((T − T₀)/13.7)

- 温度高 → 风化快 → CO₂ 被吃掉 → 温室减弱 → 温度回落（负反馈）
- 太阳变暗（早期地球约 −30%）→ 温度低 → 风化慢 → CO₂ 堆积 → 温度回升

这就是「暗淡年轻太阳悖论」的**一半**答案：地球 40 亿年没冻成雪球，靠它拦住下滑。
它的时间尺度是 10⁵–10⁶ 年——**文明尺度上不可见，地质尺度上是决定性的**。

必须说清另一半：本模块的辐射层是单波段灰体，温室上限只有 T_e 的约 20%
（`tau_total` 里水汽带 1.6 的饱和），所以 4 Ga 前太阳暗 30% 时，
纯 CO₂ 只能把 247 K 抬到 254 K，回不到 288 K。剩下的 ~34 K 得靠 CH₄ 与
更低的反照率——那是本模块**没有**建模的部分。把它当成「悖论已解决」是过度解读。
"""

from __future__ import annotations

import math

import radiation

CO2_0 = 420.0
# 参考态不写死 288 K，而是取辐射层在 420 ppm、1 L☉ 下的解（≈286.07 K）。
# 否则恒温器的「平衡态」和辐射层的「参考态」差 2 K，relax 会停在 470 ppm 而不是 420。
T0 = radiation.solve(CO2_0)["t_surface_k"]
WEATHER_TIMESCALE_YR = 2.0e5   # 风化响应时间
SOLAR_GROWTH_PER_GYR = 0.075   # 主序光度每 10 亿年约 +7.5%


def step_co2(co2, temp_k, dt_yr):
    """一步显式推进；返回新 CO₂（ppmv）。

    风化速率只看温度与 CO₂，**不直接看太阳常数**——太阳是透过温度间接进来的：
    太阳暗 → 温度低 → 风化慢 → CO₂ 堆起来。把 S 直接乘进风化项是常见的错接法。
    """
    w = (co2 / CO2_0) * math.exp((temp_k - T0) / 13.7)
    flux = (1.0 - w) / WEATHER_TIMESCALE_YR
    return max(1.0, co2 + flux * dt_yr * CO2_0)


def relax(co2_init=1680.0, years=5e6, dt=2000.0, solar_rel=1.0) -> dict:
    """从扰动状态跑回平衡，记录温度与 CO₂ 的轨迹。"""
    co2 = co2_init
    t = radiation.solve(co2, s0=radiation.S0_EARTH * solar_rel)["t_surface_k"]
    steps = int(years / dt)
    half = None
    log = []
    for i in range(steps):
        co2 = step_co2(co2, t, dt)
        t = radiation.solve(co2, s0=radiation.S0_EARTH * solar_rel)["t_surface_k"]
        if i % max(1, steps // 6) == 0:
            log.append((round(i * dt / 1e6, 2), round(co2, 1), round(t, 1)))
        if half is None and abs(co2 - CO2_0) < abs(co2_init - CO2_0) * 0.37:
            half = i * dt
    return {"co2_init": round(co2_init, 1), "co2_final": round(co2, 1),
            "t_final": round(t, 1), "relax_yr": half, "log": log}


def faint_young_sun(deficit=0.30, years=8e6) -> dict:
    """太阳暗 30% 的早期地球：CO₂ 堆起来，把温度从雪球边缘往回拉。

    返回里同时给「没有风化反馈」的对照温度：CO₂ 冻在 CO2_0 时一直是 t_frozen。
    两者之差就是恒温器的净贡献。
    """
    s0 = radiation.S0_EARTH * (1 - deficit)
    co2 = CO2_0
    t = radiation.solve(co2, s0=s0)["t_surface_k"]
    t_frozen = t
    dt = 5000.0
    for _ in range(int(years / dt)):
        co2 = step_co2(co2, t, dt)
        co2 = min(6e5, co2)
        t = radiation.solve(co2, s0=s0)["t_surface_k"]
    return {"t_start": round(t_frozen, 1), "t_end": round(t, 1),
            "co2_end": round(co2, 0), "warming": round(t - t_frozen, 1),
            "gap_to_ref": round(T0 - t, 1), "solar_rel": round(1 - deficit, 2)}


def demo() -> dict:
    r = relax()
    f = faint_young_sun()
    ok_relax = r["relax_yr"] is not None and 1e4 <= r["relax_yr"] <= 5e6
    # 判据是「CO₂ 堆起来 + 温度确实回升」，不是「一路回到 288 K」——
    # 灰体辐射层做不到后者，硬写这条判据等于逼模型说谎。
    ok_faint = f["co2_end"] > 4.0 * CO2_0 and f["warming"] > 3.0
    return {"relax": r, "faint": f, "ok": ok_relax and ok_faint,
            "detail": {"relax": ok_relax, "faint": ok_faint}}


def report(d: dict) -> str:
    r, f = d["relax"], d["faint"]
    L = ["盘古 · 碳-硅酸盐恒温器", "-" * 56]
    ry = f"{r['relax_yr'] / 1e3:.0f}" if r["relax_yr"] is not None else "未回落"
    L.append(f"  {'✓' if d['detail']['relax'] else '×'} 4×CO₂ 扰动："
             f"{r['co2_init']:.0f} → {r['co2_final']:.0f} ppm / {r['t_final']:.1f} K，"
             f"回落时标 {ry} 千年（地质尺度 10⁵–10⁶ 年）")
    L.append(f"  {'✓' if d['detail']['faint'] else '×'} 暗淡年轻太阳（−30%）："
             f"{f['t_start']:.1f} K → {f['co2_end']:.0f} ppm → {f['t_end']:.1f} K"
             f"（回升 {f['warming']:+.1f} K，离参考态还差 {f['gap_to_ref']:.1f} K）")
    if d["ok"]:
        L.append("  结论：恒温器拦住了雪球；补不满的那 30 多 K 要靠 CH₄ 与低反照率")
    else:
        L.append("  结论：反馈失灵")
    L.append("  口径：只算 CO₂-温度-风化一个回路；单波段灰体的温室上限约 T_e 的 20%，")
    L.append(f"        所以「纯 CO₂ 回不到参考态 {T0:.0f} K」是模型的天花板，不是调参失误。")
    return "\n".join(L)


if __name__ == "__main__":
    print(report(demo()))
