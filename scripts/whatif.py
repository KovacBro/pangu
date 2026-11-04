# -*- coding: utf-8 -*-
"""
盘古 · 反事实推演（1.1.3 大条 E）
==================================
「如果把这条设定改掉，这个世界会变成什么样？」

与 `sweep` 的分工
-----------------
- `sweep`：沿**一个数值**扫出连续谱，只回答「哪一步崩了」。
- `whatif`：任意多字段一起改（或按倍率缩放），回答「**世界变成什么样**」——
  派生量怎么动、哪些推论消失、哪些新推论出现、审查从哪一条开始崩、下游要重跑什么。

永远不写原世界：改动只发生在内存副本里；要给下游用，得显式 `--write <新文件>`。
"""

from __future__ import annotations

import copy
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import world_schema as ws  # noqa: E402
import world_tuning as wt  # noqa: E402
import entailment as en  # noqa: E402

# 改动落在哪一层 —— 决定这句话怎么说
LAYERS = [
    (("physics", "mathematics", "cosmology"), "地基",
     "动了律与天，preview / export / map / ca 全部要重跑"),
    (("chemistry", "biology"), "生态",
     "动了料与活，map 的群系与 ca 的规则可能要重算"),
    (("civilization", "history", "narrative"), "人事",
     "只动了人与史，改档案即可，物理层不受影响"),
    (("meta", "seed"), "表层", "只动了名字与种子，其余不动"),
]


def _first_planet(world: dict):
    bodies = [b for b in (ws._get(world, "cosmology", "bodies", default=[]) or [])
              if isinstance(b, dict)]
    ids = {b.get("id") for b in bodies}
    for b in bodies:
        if str(ws._get(b, "orbit", "parent", default="")) not in ids:
            return b
    return bodies[0] if bodies else None


_NUM_HEAD = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(.*)$")


def _split_num(v):
    """'4.004e-11 m3kg-1s-2' → (4.004e-11, ' m3kg-1s-2')；不是数值返回 None。

    world.json 里的常数常写成「数字 + 单位」的字符串，倍率缩放必须保住单位，
    否则缩放一次就把 'm3kg-1s-2' 弄丢了。
    """
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v), ""
    if isinstance(v, str):
        m = _NUM_HEAD.match(v)
        if m:
            return float(m.group(1)), m.group(2)
    return None


def _scale_one(world: dict, spec: str) -> dict:
    """`path=1.5` → 把该路径的当前数值乘以 1.5（字符串保留单位后缀）。"""
    path, raw = wt.parse_assignment(spec)
    ok, cur, why = ws.resolve_path(world, path)
    if not ok:
        return {"ok": False, "error": why}
    parts = _split_num(cur)
    if parts is None:
        return {"ok": False, "error": f"{path} 不是数值（当前 {json_type(cur)}），无法按倍率缩放"}
    try:
        k = float(wt.parse_value(raw))
    except (TypeError, ValueError):
        return {"ok": False, "error": f"倍率不是数字：{raw}"}

    base, suffix = parts
    scaled = base * k
    if suffix:
        new = f"{scaled:g}{suffix}"
    elif isinstance(cur, int) and float(scaled).is_integer():
        new = int(scaled)
    else:
        new = scaled
    r = wt.set_value(world, path, new, create=False)
    r["path"], r["old"], r["new"], r["factor"] = path, cur, new, k
    return r


def json_type(v) -> str:
    return {dict: "对象", list: "数组", str: "字符串", bool: "布尔",
            int: "整数", float: "小数", type(None): "null"}.get(type(v), type(v).__name__)


def simulate(world: dict, sets: list = (), scales: list = (),
             recalc: bool = False) -> dict:
    """在副本上改，返回一次完整的「会怎样」。"""
    before_rep = ws.validate(copy.deepcopy(world))
    w2 = copy.deepcopy(world)

    changes = []
    for spec in list(sets):
        path, raw = wt.parse_assignment(spec)
        val = wt.parse_value(raw)
        r = wt.set_value(w2, path, val, create=False)
        if not r["ok"]:
            return {"ok": False, "error": r["error"], "spec": spec}
        r["path"] = path
        r["new"] = val        # set_value 只回 old；报告层要 old → new
        changes.append(r)
    for spec in list(scales):
        r = _scale_one(w2, spec)
        if not r["ok"]:
            return {"ok": False, "error": r["error"], "spec": spec}
        changes.append(r)

    recalced = []
    if recalc:
        rr = wt.recalc_bodies(w2)
        if rr.get("ok"):
            recalced = rr["recalced"]

    after_rep = ws.validate(w2)

    ph_before = {r["id"]: r for r in en.derive(world)}
    ph_after = {r["id"]: r for r in en.derive(w2)}
    new = [ph_after[k] for k in ph_after if k not in ph_before]
    gone = [ph_before[k] for k in ph_before if k not in ph_after]
    kept = [ph_after[k] for k in ph_after if k in ph_before]

    before_fatal = {c.id for c in before_rep.checks if c.verdict == "fatal"}
    after_fatal = {c.id for c in after_rep.checks if c.verdict == "fatal"}
    new_fatal = [c for c in after_rep.checks
                 if c.verdict == "fatal" and c.id not in before_fatal]
    fixed = sorted(before_fatal - after_fatal)

    body = _first_planet(world) or {}
    body2 = _first_planet(w2) or {}
    d_before = ws.compute_derived(world)
    d_after = ws.compute_derived(w2)

    def _body_derived(d, bid):
        for b in d.get("bodies") or []:
            if b.get("id") == bid:
                return b
        return {}

    bd1 = _body_derived(d_before, body.get("id"))
    bd2 = _body_derived(d_after, body2.get("id"))
    wd1, wd2 = ws.weirdness(world)["score"], ws.weirdness(w2)["score"]

    touched = sorted({str(c["path"]).split(".")[0].split("[")[0] for c in changes})
    layer, note = "表层", "只动了名字与种子"
    for keys, name, msg in LAYERS:
        if set(touched) & set(keys):
            layer, note = name, msg
            break

    return {
        "ok": True,
        "world": ws._get(world, "meta", "name", default=""),
        "version": ws._get(world, "meta", "version", default=""),
        "changes": changes,
        "recalced": recalced,
        "layer": layer, "layer_note": note, "touched": touched,
        "before": {"score": before_rep.score, "fatal": before_rep.fatal,
                   "warn": before_rep.warn, "weirdness": wd1},
        "after": {"score": after_rep.score, "fatal": after_rep.fatal,
                  "warn": after_rep.warn, "weirdness": wd2},
        "derived": {
            "gravity_g": (bd1.get("gravity_g_calc"), bd2.get("gravity_g_calc")),
            "t_eq_k": (bd1.get("t_eq_k"), bd2.get("t_eq_k")),
            "escape_kms": (bd1.get("v_escape_km_s"), bd2.get("v_escape_km_s")),
        },
        "new_fatal": [{"id": c.id, "note": c.note} for c in new_fatal],
        "fixed": fixed,
        "phenomena": {
            "new": [{"id": r["id"], "name": r["name"], "claim": r["claim"]} for r in new],
            "gone": [{"id": r["id"], "name": r["name"], "claim": r["claim"]} for r in gone],
            "kept": [r["id"] for r in kept],
        },
        "downstream": wt.downstream_tasks([str(c["path"]) for c in changes]),
        "world_after": w2,
    }


def _fmt(v, digits: int = 2) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, (int, float)):
        if v != 0 and (abs(v) >= 1e5 or abs(v) < 1e-3):
            return f"{v:.3e}"
        return f"{v:.{digits}f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
    return str(v)


def format_report(res: dict, world_path: str = "<world>") -> str:
    if not res.get("ok"):
        return f"推演失败：{res.get('error')}"

    L = [f"【盘古 · 反事实推演】{res['world']} {res['version']}"]
    for c in res["changes"]:
        if "factor" in c:
            L.append(f"  假设：{c['path']} × {c['factor']:g}"
                     f"（{_fmt(c['old'])} → {_fmt(c['new'])}）")
        else:
            L.append(f"  假设：{c['path']} {_fmt(c['old'])} → {_fmt(c['new'])}")
    if res["recalced"]:
        L.append(f"  已按新参数重算密度/重力：{'、'.join(str(x) for x in res['recalced'])}")
    L.append("-" * 58)

    d = res["derived"]
    L.append(f"  地表重力 {_fmt(d['gravity_g'][0])} g → {_fmt(d['gravity_g'][1])} g"
             f" ｜ 平衡温度 {_fmt(d['t_eq_k'][0])} → {_fmt(d['t_eq_k'][1])} K"
             f" ｜ 反常识度 {res['before']['weirdness']} → {res['after']['weirdness']}")

    b, a = res["before"], res["after"]
    arrow = "→"
    L.append(f"  审查 {b['score']} {arrow} {a['score']}"
             f" ｜ fatal {b['fatal']} {arrow} {a['fatal']}"
             f" ｜ warn {b['warn']} {arrow} {a['warn']}")
    if res["new_fatal"]:
        for c in res["new_fatal"]:
            L.append(f"    ✗ {c['id']} {c['note']}")
        L.append("    → 这是最先崩的一环；先修它，再谈现象怎么变。")
    if res["fixed"]:
        L.append(f"    ✓ 反而修好了：{'、'.join(res['fixed'])}")

    ph = res["phenomena"]
    if ph["gone"]:
        L.append("")
        L.append(f"【世界少了 {len(ph['gone'])} 层】")
        for r in ph["gone"]:
            L.append(f"    - {r['id']} {r['name']}：{r['claim']}")
    if ph["new"]:
        L.append("")
        L.append(f"【世界多了 {len(ph['new'])} 层】")
        for r in ph["new"]:
            L.append(f"    + {r['id']} {r['name']}：{r['claim']}")
    if ph["kept"]:
        L.append("")
        L.append(f"【仍然成立】{len(ph['kept'])} 条：{'、'.join(ph['kept'])}")

    L.append("-" * 58)
    L.append(f"  这是一次「{res['layer']}」级改动：{res['layer_note']}。")
    if res["downstream"]:
        L.append("  若采纳这次改动，需要重跑：")
        for t in res["downstream"]:
            L.append(f"    {t['task']:<8} {str(t['cmd']).replace('<world>', world_path)}")
    L.append("  原世界未改动；要留下这个假设世界，加 --write out/xxx.json")
    return "\n".join(L)
