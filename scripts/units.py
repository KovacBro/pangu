"""
盘古 · 量纲与取值域（1.1.5）
============================
1.1.4 之前，单位靠字段名后缀（`_km` / `_au` / `_kpa`）的一种约定，没有任何东西检查
「你把 10⁹ 写进了一个温度字段」。这一层把它变成可执行的规则：

- **量纲**：由后缀判定（`_k` → 温度，`_km` → 长度，`_au` → 长度，…）
- **硬域**：物理上不可能的取值 → `patch` 直接拒绝
- **软域**：可疑但可能（如 1.5 g 的行星）→ 只警告，不拦

口径：这一层不做单位换算（不把 km 换成 m），只做「这个数配不配这个字段」。
换算需要单位类型系统，属 1.10 的重构；此处只堵住最贵的一类错。
"""

from __future__ import annotations

from typing import Tuple

# 后缀 → (量纲, 硬下界, 硬上界, 软下界, 软上界)
# 顺序有意义：长后缀在前（_kpa 先于 _k，_km 先于 _m，_hours 先于 _s）
RULES = [
    ("_kpa", "pressure", 1e-6, 1e7, 1.0, 2e4),
    ("_km3", "volume", 1e-3, 1e18, 1e0, 1e14),
    ("_gcc", "density", 1e-3, 1e6, 0.05, 60.0),
    ("_hours", "time", 1e-6, 1e9, 0.05, 1e6),
    ("_days", "time", 1e-6, 1e12, 1e-2, 1e9),
    ("_gyr", "time", 1e-6, 1e6, 1e-3, 1e4),
    ("_km", "length", 1e-3, 1e6, 1.0, 2e5),
    ("_au", "length", 1e-6, 1e5, 1e-4, 1e4),
    ("_kg", "mass", 1e-15, 1e32, 1e-6, 1e28),
    ("_ms", "speed", 1e-6, 1e8, 1e-3, 1e5),
    ("_deg", "angle", -1e5, 1e5, -360.0, 360.0),
    ("_earth", "ratio", 1e-12, 1e12, 1e-4, 1e4),
    ("_solar", "ratio", 1e-12, 1e12, 1e-4, 1e4),
    ("_k", "temperature", 1.0, 1e5, 30.0, 2e4),
    ("_g", "accel", 1e-9, 1e8, 1e-3, 1e3),
    ("_m", "length", 1e-6, 1e12, 1e-3, 1e8),
    ("_s", "time", 1e-9, 1e12, 1e-6, 1e10),
]

DIM_CN = {
    "temperature": "温度", "pressure": "压强", "length": "长度", "time": "时间",
    "mass": "质量", "speed": "速度", "angle": "角度", "ratio": "比值",
    "density": "密度", "volume": "体积", "accel": "加速度", "unknown": "未知",
}


def dim_of(field: str) -> str:
    """由字段名后缀判定量纲；认不出来就返回 unknown（不拦）。"""
    name = str(field or "")
    for suffix, dim, *_ in RULES:
        if name.endswith(suffix):
            return dim
    return "unknown"


def _rule(field: str):
    name = str(field or "")
    for suffix, dim, hard_lo, hard_hi, soft_lo, soft_hi in RULES:
        if name.endswith(suffix):
            return suffix, dim, hard_lo, hard_hi, soft_lo, soft_hi
    return None


def check(field: str, value) -> Tuple[str, str]:
    """返回 (status, message)，status ∈ ok / soft / hard。

    hard = 物理上不可能，调用方应当拒绝写入；soft = 可疑，只提示。
    """
    rule = _rule(field)
    if rule is None:
        return "ok", ""
    suffix, dim, hard_lo, hard_hi, soft_lo, soft_hi = rule
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "soft", f"{field} 不是数（{value!r}），量纲 {DIM_CN[dim]}"
    if v != v or v in (float("inf"), float("-inf")):
        return "hard", f"{field} 不是有限数"
    if v < hard_lo or v > hard_hi:
        return "hard", (f"{field} = {v:g} 超出物理硬域 "
                        f"[{hard_lo:g}, {hard_hi:g}]（{DIM_CN[dim]}）")
    if v < soft_lo or v > soft_hi:
        return "soft", (f"{field} = {v:g} 超常见范围 "
                        f"[{soft_lo:g}, {soft_hi:g}]（{DIM_CN[dim]}）")
    return "ok", ""


def demo() -> dict:
    """自检：几张应当被拦的卡。"""
    cases = [
        ("cosmology.bodies[0].surface_temperature_k", 1e9, "hard"),
        ("cosmology.bodies[0].radius_km", 6371.0, "ok"),
        ("cosmology.bodies[0].radius_km", 1e7, "hard"),
        ("cosmology.bodies[0].mass_earth", 30.0, "ok"),
        ("cosmology.bodies[0].axial_tilt_deg", 18.2, "ok"),
        ("atmosphere.surface_pressure_kpa", 118.0, "ok"),
        ("atmosphere.surface_pressure_kpa", 1e9, "hard"),
        ("physics.constants[0].world_value", 3.6e-11, "ok"),   # 无后缀，不拦
        ("cosmology.bodies[0].gravity_g", 1.76, "ok"),
        ("cosmology.bodies[0].albedo", 0.3, "ok"),
    ]
    rows = []
    bad = 0
    for path, val, want in cases:
        got, msg = check(path.rsplit(".", 1)[-1], val)
        ok = got == want
        if not ok:
            bad += 1
        rows.append({"path": path, "value": val, "want": want, "got": got, "ok": ok,
                     "msg": msg})
    return {"rows": rows, "bad": bad, "ok": bad == 0}


def report(d: dict) -> str:
    L = ["盘古 · 量纲与取值域", "-" * 56]
    for r in d["rows"]:
        mark = "✓" if r["ok"] else "×"
        L.append(f"  {mark} {r['path']:<48} {r['value']:<10g} → {r['got']}")
        if r["msg"]:
            L.append(f"      {r['msg']}")
    tail = "全部按预期" if d["ok"] else f"{d['bad']} 条不符预期"
    L.append("  结论：" + tail)
    return "\n".join(L)


if __name__ == "__main__":
    print(report(demo()))
