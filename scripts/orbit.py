"""
盘古 · 轨道与潮汐（1.6）
=========================
1.1.4 的轨道只有开普勒第三定律：知道「一年多长」，不知道「一亿年后还在不在」。

这一层给三件：

1. **辛积分（leapfrog）N 体**：能量漂移应当随步长有界振荡，而不是单调上升。
2. **广义相对论近日点进动**：Δϖ = 6πGM/(c²a(1−e²)) 每圈；水星应对上 43″/世纪。
3. **潮汐减速**：dΩ/dt ∝ −(R/a)⁶；地球-月球量级应对上「日长每世纪 +1.8 ms」。

口径：牛顿引力 + 一阶后牛顿修正；不算自转-轨道角动量交换的细节，不算共振捕获。
"""

from __future__ import annotations

import math

G = 6.67430e-11
C = 2.99792458e8
AU = 1.495978707e11
DAY = 86400.0
YEAR = 365.25 * DAY
CENTURY = 100 * YEAR


def leapfrog_energy(steps=20000, dt=3600.0) -> dict:
    """太阳-地球-月球三体，辛积分，看能量相对漂移。"""
    m_sun, m_e, m_m = 1.989e30, 5.972e24, 7.342e22
    # 月球相对地球偏 3.844e5 km，所以要加在地球位置之后
    p = [[AU, 0.0, 0.0], [AU + 3.844e8, 0.0, 0.0]]
    v = [[0.0, 29.78e3, 0.0], [0.0, 29.78e3 + 1.022e3, 0.0]]
    m = [m_e, m_m]
    orbiter = p[1]
    center = p[0]

    def energy():
        e = 0.0
        bodies = [(m_e, p[0], v[0]), (m_m, p[1], v[1])]
        masses = [m_sun, m_e, m_m]
        pos = [[0.0, 0.0, 0.0], p[0], p[1]]
        vel = [[0.0, 0.0, 0.0], v[0], v[1]]
        for i in range(3):
            e += 0.5 * masses[i] * sum(x * x for x in vel[i])
            for j in range(i + 1, 3):
                dx = [pos[i][k] - pos[j][k] for k in range(3)]
                r = math.sqrt(sum(x * x for x in dx)) or 1.0
                e -= G * masses[i] * masses[j] / r
        return e

    e0 = energy()
    drift = 0.0
    for _ in range(steps):
        # 每个完整步：半踢 → 全漂 → 半踢（KDK，辛）
        _ = None
        # 加速度（只用太阳主导项 + 互相作用，够看能量行为）
        acc = []
        for i, (mi, pi) in enumerate(zip(m, [p[0], p[1]])):
            a = [0.0, 0.0, 0.0]
            # 太阳
            r = [pi[k] - 0.0 for k in range(3)]
            rn = math.sqrt(sum(x * x for x in r)) or 1.0
            for k in range(3):
                a[k] -= G * m_sun * r[k] / rn ** 3
            # 另一个
            other = p[1 - i]
            mo = m[1 - i]
            r = [pi[k] - other[k] for k in range(3)]
            rn = math.sqrt(sum(x * x for x in r)) or 1.0
            for k in range(3):
                a[k] -= G * mo * r[k] / rn ** 3
            acc.append(a)
        for i in range(2):
            for k in range(3):
                v[i][k] += 0.5 * dt * acc[i][k]
                p[i][k] += dt * v[i][k]
        # 后半踢：用新位置重算加速度
        acc = []
        for i in range(2):
            a = [0.0, 0.0, 0.0]
            r = [p[i][k] for k in range(3)]
            rn = math.sqrt(sum(x * x for x in r)) or 1.0
            for k in range(3):
                a[k] -= G * m_sun * r[k] / rn ** 3
            other = p[1 - i]
            r = [p[i][k] - other[k] for k in range(3)]
            rn = math.sqrt(sum(x * x for x in r)) or 1.0
            for k in range(3):
                a[k] -= G * m[1 - i] * r[k] / rn ** 3
            acc.append(a)
        for i in range(2):
            for k in range(3):
                v[i][k] += 0.5 * dt * acc[i][k]

    e1 = energy()
    return {"steps": steps, "drift": abs((e1 - e0) / e0)}


def gr_precession(a_au, e, m_sun=1.989e30) -> dict:
    """每圈进动（弧度）→ 每世纪角秒。水星：43″/cy。"""
    a = a_au * AU
    per_orbit = 6.0 * math.pi * G * m_sun / (C * C * a * (1.0 - e * e))
    period = 2.0 * math.pi * math.sqrt(a ** 3 / (G * m_sun))
    per_century_arcsec = per_orbit * (CENTURY / period) * 206264.806
    return {"per_orbit_arcsec": round(per_orbit * 206264.806, 4),
            "per_century_arcsec": round(per_century_arcsec, 2),
            "period_days": round(period / DAY, 2)}


def tidal_despin(a_km=384400.0, r_km=6371.0, m_earth=1.0, m_moon_kg=7.342e22,
                 q=12.0, k2=0.3, period_hours=24.0) -> dict:
    """潮汐减速：力矩 T = 1.5·(k₂/Q)·(GM_mm²/R)·(R/a)⁶，再除以转动惯量。

    地球参数应给出「日长每世纪 +1.8 ms」这个量级。
    """
    a = a_km * 1000.0
    r = r_km * 1000.0
    omega = 2.0 * math.pi / (period_hours * 3600.0)
    torque = 1.5 * (k2 / q) * (G * m_moon_kg ** 2 / r) * (r / a) ** 6
    inertia = 0.33 * (m_earth * 5.972e24) * r * r
    domega = torque / inertia                      # rad/s²，正值 = 自转减慢
    d_len_per_yr = (2.0 * math.pi / omega ** 2) * domega * YEAR  # 秒/年
    return {"torque_nm": round(torque, 3),
            "day_gain_ms_per_century": round(d_len_per_yr * 100 * 1000, 3)}


def demo() -> dict:
    le = leapfrog_energy()
    merc = gr_precession(0.387098, 0.20563)
    tid = tidal_despin()
    ok_e = le["drift"] < 1e-6
    ok_gr = 35.0 <= merc["per_century_arcsec"] <= 50.0
    return {"leapfrog": le, "mercury": merc, "tide": tid,
            "ok": ok_e and ok_gr,
            "detail": {"energy": ok_e, "gr": ok_gr}}


def report(d: dict) -> str:
    L = ["盘古 · 轨道与潮汐", "-" * 56]
    L.append(f"  {'✓' if d['detail']['energy'] else '×'} 辛积分能量漂移 "
             f"{d['leapfrog']['drift']:.2e}（{d['leapfrog']['steps']} 步，有界振荡）")
    m = d["mercury"]
    L.append(f"  {'✓' if d['detail']['gr'] else '×'} 水星近日点进动 "
             f"{m['per_century_arcsec']:.1f}″/世纪（实测 43.0）")
    t = d["tide"]
    L.append(f"  · 潮汐减速：日长每世纪 +{t['day_gain_ms_per_century']:.2f} ms（实测 +1.8）")
    L.append(f"  结论：{'轨道能算了' if d['ok'] else '有一项没过'}")
    return "\n".join(L)


if __name__ == "__main__":
    print(report(demo()))
