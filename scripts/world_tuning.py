# -*- coding: utf-8 -*-
"""
盘古 · 调参层
=============
1.1.2 新增：给「改设定」这件最高频的事一套可验证的工具，而不是让 agent 手改 JSON。

    patch   定点读写 world.json 的任意字段（改 / 增 / 查），自动升版本、记修订
    sweep   沿一个数值参数扫出连续谱，找出「世界在哪里崩」
    diff    对比两个版本的 world.json，给出派生量变化与下游重跑清单

设计约束：
  · 只操作 dict/list 的标量叶子，不做 schema 迁移；world.json 仍是单一数据源
  · 每个函数都不写盘，写盘由 CLI 负责（便于 --dry-run 与原子替换）
  · 路径文法与 ws.resolve_path 共用（切片 cites / 红队 target / CA source 同源）
"""

from __future__ import annotations

import copy
import datetime as _dt
import json
import re

import world_schema as ws


# ════════════════════════════════════════════════════════════════════
# 值解析与定点写入
# ════════════════════════════════════════════════════════════════════

def parse_assignment(text: str) -> tuple:
    """把 'physics.constants[0].world_value=4.0e-11' 拆成 (path, raw_value)。"""
    if "=" not in str(text):
        raise ValueError(f"缺少 '='：{text}")
    path, raw = str(text).split("=", 1)
    path = path.strip()
    if not path:
        raise ValueError(f"路径为空：{text}")
    return path, raw


def parse_value(raw: str):
    """按 JSON 解析值；失败则当字符串。这样 4.0e-11 / true / [1,2] / "文本" 都能写。"""
    s = str(raw).strip()
    if s == "":
        return ""
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return str(raw)


def set_value(root: dict, path: str, value, create: bool = False) -> dict:
    """
    按点路径写入。返回 {ok, error, existed, old}。

    create=False 时，路径中任一段不存在即失败（防止手滑写出孤儿字段）；
    create=True 时，缺失的中间对象/数组会被建出来，数组只允许在末尾追加。
    """
    try:
        tokens = ws.parse_path(path)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    if not tokens:
        return {"ok": False, "error": "路径无有效段"}

    cur = root
    walked = []
    for i, tok in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]
        nxt_desc = "数组" if isinstance(nxt, int) else "对象"
        if isinstance(tok, int):
            if not isinstance(cur, list):
                return {"ok": False, "error": f"{'.'.join(str(x) for x in walked) or '根'} 不是数组，无法取下标 [{tok}]"}
            if tok > len(cur):
                return {"ok": False, "error": f"{'.'.join(str(x) for x in walked)}[{tok}] 越界（长度 {len(cur)}）"}
            if tok == len(cur):
                if not create:
                    return {"ok": False, "error": f"{'.'.join(str(x) for x in walked)}[{tok}] 不存在（加 --create 追加）"}
                cur.append([] if isinstance(nxt, int) else {})
            cur = cur[tok]
            walked.append(f"[{tok}]")
        else:
            if not isinstance(cur, dict):
                return {"ok": False, "error": f"{'.'.join(str(x) for x in walked)} 不是对象，无法取字段 {tok}"}
            if tok not in cur:
                if not create:
                    return {"ok": False, "error": f"字段不存在：{'.'.join(str(x) for x in walked + [tok])}（加 --create 新建）"}
                cur[tok] = [] if isinstance(nxt, int) else {}
            cur = cur[tok]
            walked.append(tok)

    last = tokens[-1]
    label = ".".join(str(x) for x in walked)
    if isinstance(last, int):
        if not isinstance(cur, list):
            return {"ok": False, "error": f"{label} 不是数组，无法取下标 [{last}]"}
        if last > len(cur):
            return {"ok": False, "error": f"{label}[{last}] 越界（长度 {len(cur)}）"}
        if last == len(cur):
            if not create:
                return {"ok": False, "error": f"{label}[{last}] 不存在（加 --create 追加）"}
            cur.append(value)
            return {"ok": True, "error": "", "existed": False, "old": None}
        old = cur[last]
        cur[last] = value
        return {"ok": True, "error": "", "existed": True, "old": old}

    if not isinstance(cur, dict):
        return {"ok": False, "error": f"{label} 不是对象，无法取字段 {last}"}
    existed = last in cur
    if not existed and not create:
        return {"ok": False, "error": f"字段不存在：{label + '.' if label else ''}{last}（加 --create 新建）"}
    old = cur.get(last)
    cur[last] = value
    return {"ok": True, "error": "", "existed": existed, "old": old}


def bump_version(version: str) -> str:
    """
    世界版本推进：补丁位非零时升补丁位（1.1.1 → 1.1.2），否则升次版本（1.0 → 1.1）。

    SKILL 的规则是「每次改设定 +0.1」；三段的版本号把这件事落到补丁位，
    避免一个标点改动就把世界升成 2.0。
    """
    nums = [int(x) for x in re.findall(r"\d+", str(version or ""))]
    if not nums:
        return "1.0"
    if len(nums) >= 3 and nums[2] != 0:
        nums[2] += 1
        return ".".join(str(x) for x in nums[:3])
    if len(nums) >= 2:
        nums[1] += 1
        return ".".join(str(x) for x in nums[:2])
    return f"{nums[0] + 1}.0"


def record_revision(world: dict, change: str, version: str = None,
                    fields: list = None) -> dict:
    """在 history.revisions[] 追加一条修订记录，返回该条。"""
    meta = world.setdefault("meta", {})
    hist = world.setdefault("history", {})
    if not isinstance(hist, dict):
        hist = {"eras": [], "revisions": []}
        world["history"] = hist
    revs = hist.setdefault("revisions", [])
    if not isinstance(revs, list):
        revs = []
        hist["revisions"] = revs
    old = str(meta.get("version") or "")
    new = version or bump_version(old)
    meta["version"] = new
    entry = {
        "version": new,
        "date": _dt.date.today().isoformat(),
        "change": change,
    }
    if fields:
        entry["fields"] = list(fields)[:40]
    revs.append(entry)
    return entry


def apply_patches(world: dict, assignments: list, create: bool = False,
                  note: str = "", bump: bool = True, version: str = None) -> dict:
    """
    批量应用 '路径=值'。成功返回 {ok, changes, revision}，失败返回 {ok:False, error}。

    注意：本函数会就地修改 world；调用方在失败时不要写盘。
    """
    changes = []
    for spec in assignments:
        try:
            path, raw = parse_assignment(spec)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        value = parse_value(raw)
        res = set_value(world, path, value, create=create)
        if not res["ok"]:
            return {"ok": False, "error": f"{path}：{res['error']}"}
        changes.append({"path": path, "old": res["old"], "new": value,
                        "existed": res["existed"]})

    if not changes:
        return {"ok": False, "error": "没有可应用的改动"}

    entry = None
    if bump or version:
        fields = [c["path"] for c in changes]
        text = note.strip() or "patch：" + "、".join(f"{c['path']}={_brief(c['new'])}"
                                                     for c in changes[:6])
        entry = record_revision(world, text, version=version, fields=fields)
    return {"ok": True, "changes": changes, "revision": entry}


# ════════════════════════════════════════════════════════════════════
# 参数扫描
# ════════════════════════════════════════════════════════════════════

# --list 展示的「值得扫的参数」：数值型且会改动物理结论的那些。
_SCAN_FIELDS = (
    ("mass_earth", "质量"),
    ("radius_earth", "半径"),
    ("albedo", "反照率"),
    ("axial_tilt_deg", "转轴倾角"),
    ("rotation_hours", "自转周期"),
    ("orbit.a_au", "轨道半长轴"),
    ("orbit.eccentricity", "偏心率"),
    ("atmosphere.greenhouse_delta_k", "温室补偿"),
)


def scan_targets(world: dict) -> list:
    """列出可扫描的数值路径，供 sweep --list 使用。"""
    out = []
    phys = world.get("physics") or {}
    for i, c in enumerate(phys.get("constants") or []):
        if not isinstance(c, dict):
            continue
        v = ws._parse_first(c.get("world_value"))
        if v is None:
            continue
        out.append({"path": f"physics.constants[{i}].world_value",
                    "label": f"常数 {c.get('symbol', '?')}", "value": v})

    cos = world.get("cosmology") or {}
    for i, b in enumerate(cos.get("bodies") or []):
        if not isinstance(b, dict):
            continue
        for field, label in _SCAN_FIELDS:
            ok, val, _ = ws.resolve_path(b, field)
            num = ws._parse_first(val) if ok else None
            if num is not None:
                out.append({"path": f"cosmology.bodies[{i}].{field}",
                            "label": f"{b.get('name', f'天体{i}')} · {label}", "value": num})
    for i, s in enumerate(cos.get("stars") or []):
        if not isinstance(s, dict):
            continue
        for field, label in (("luminosity_solar", "光度"), ("mass_solar", "质量")):
            v = ws._parse_first(s.get(field))
            if v is not None:
                out.append({"path": f"cosmology.stars[{i}].{field}",
                            "label": f"{s.get('name', f'恒星{i}')} · {label}", "value": v})
    return out


def sweep_values(cur: float, lo: float = None, hi: float = None,
                 steps: int = 7) -> list:
    """生成扫描序列：给定上下界用线性，否则以当前值为中心 ±20%。"""
    steps = max(3, min(31, int(steps)))
    if lo is None and hi is None:
        lo, hi = cur * 0.8, cur * 1.2
    elif lo is None:
        lo = cur - (hi - cur)
    elif hi is None:
        hi = cur + (cur - lo)
    if lo > hi:
        lo, hi = hi, lo
    if steps == 1:
        return [cur]
    return [lo + (hi - lo) * i / (steps - 1) for i in range(steps)]


def recalc_bodies(world: dict) -> dict:
    """
    重算所有天体的三个「声明量」，让它们与质量 / 半径 / G' 自洽：
        density_gcc = M × 5.514 / R³
        gravity_g   = M / R² × (G'/G)
        radius_km   = R × 6371

    只动地球对照值（密度 / 重力 / 半径），不改动物理设定本身。
    扫 G 时必须全体重算：G 一变，连卫星的声明重力也会失配。
    """
    cos = world.get("cosmology") or {}
    bodies = [b for b in (cos.get("bodies") or []) if isinstance(b, dict)]
    if not bodies:
        return {"ok": False, "error": "cosmology.bodies 为空"}
    gr = ws.g_ratio(world)
    done = []
    for i, b in enumerate(bodies):
        r_e = (ws._num(b.get("radius_earth"), 0)
               or ws._num(b.get("radius_km"), 0) / ws.EARTH_RADIUS_KM)
        m_e = ws._num(b.get("mass_earth"), 0)
        if r_e <= 0 or m_e <= 0:
            continue
        b["density_gcc"] = round(m_e * ws.EARTH_DENSITY_GCC / (r_e ** 3), 3)
        b["gravity_g"] = round(m_e / (r_e ** 2) * gr, 3)
        b["radius_km"] = round(r_e * ws.EARTH_RADIUS_KM, 1)
        done.append(b.get("id", i))
    if not done:
        return {"ok": False, "error": "所有天体都缺 mass_earth / radius_earth，无法重算"}
    return {"ok": True, "recalced": done}


def sweep_world(world: dict, path: str, values: list, body_index: int = 0,
                recalc: bool = False) -> dict:
    """
    逐值改一份副本并完整校验，返回连续谱。

    判定「崩」的标准写死在这里，避免主观：
      · fatal 数比基线多，或
      · 总分比基线低 3 分以上

    recalc=True 时，每次改完会先重算该天体的密度 / 表面重力 / 半径 km，
    让扫描探索**物理自洽**的邻近世界；否则 mass_earth 一动，声明值 P01 就报不一致，
    整条曲线全是 fatal，看不出真正的临界点。
    """
    base_world = copy.deepcopy(world)
    base = ws.validate(base_world)

    rows = []
    for v in values:
        w = copy.deepcopy(world)
        res = set_value(w, path, v)
        if not res["ok"]:
            return {"ok": False, "error": res["error"]}
        if recalc:
            rr = recalc_bodies(w)
            if not rr["ok"]:
                return rr
        rep = ws.validate(w)
        bodies = rep.derived.get("bodies") or []
        b = bodies[body_index] if 0 <= body_index < len(bodies) else {}
        broken = rep.fatal > base.fatal or rep.score <= base.score - 3
        rows.append({
            "value": v,
            "score": rep.score,
            "fatal": rep.fatal,
            "warn": rep.warn,
            "fatal_ids": [c.id for c in rep.checks if c.verdict == "fatal"],
            "gravity_g": b.get("gravity_g_calc"),
            "v_escape_km_s": b.get("v_escape_km_s"),
            "t_surface_k": b.get("t_surface_k"),
            "density_gcc": b.get("density_gcc_calc"),
            "broken": broken,
        })

    base_row = {"score": base.score, "fatal": base.fatal, "warn": base.warn}
    safe = [r["value"] for r in rows if not r["broken"]]
    critical = next((r for r in rows if r["broken"]), None)
    return {
        "ok": True, "path": path, "baseline": base_row, "rows": rows,
        "recalc": bool(recalc),
        "safe_window": [min(safe), max(safe)] if safe else None,
        "critical": critical,
    }


# ════════════════════════════════════════════════════════════════════
# 版本对比
# ════════════════════════════════════════════════════════════════════

_OPAQUE_KEYS = {"coarse"}
_MAX_LIST = 40


def _brief(v, maxlen: int = 72) -> str:
    if isinstance(v, dict):
        return f"<对象 {len(v)} 键>"
    if isinstance(v, list):
        return f"<数组 {len(v)} 项>"
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= maxlen else s[:maxlen] + "…"


def diff_worlds(a: dict, b: dict, limit: int = 200) -> dict:
    """
    深度对比两份 world.json。

    · 长度一致的短数组逐项比（physics.constants / trophic_levels 这类要看清）
    · 长数组与大块数据（planet_map.coarse）整体比，只报规模变化
    · 最多记录 limit 条，超出置 truncated
    """
    changes, added, removed = [], [], []
    truncated = [False]

    def push(bucket, item):
        if len(changes) + len(added) + len(removed) >= limit:
            truncated[0] = True
            return
        bucket.append(item)

    def walk(x, y, path):
        if len(changes) + len(added) + len(removed) >= limit:
            truncated[0] = True
            return
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(set(x) | set(y), key=str):
                if k in _OPAQUE_KEYS:
                    if x.get(k) != y.get(k):
                        push(changes, {"path": f"{path}.{k}" if path else str(k),
                                       "old": _brief(x.get(k)), "new": _brief(y.get(k))})
                    continue
                p = f"{path}.{k}" if path else str(k)
                if k not in x:
                    push(added, {"path": p, "new": _brief(y[k])})
                elif k not in y:
                    push(removed, {"path": p, "old": _brief(x[k])})
                else:
                    walk(x[k], y[k], p)
            return
        if isinstance(x, list) and isinstance(y, list):
            if len(x) == len(y) and len(x) <= _MAX_LIST:
                for i in range(len(x)):
                    walk(x[i], y[i], f"{path}[{i}]")
                return
            # 长度不同但都是短对象数组（如 history.revisions）：逐项比 + 报增删
            if (max(len(x), len(y)) <= _MAX_LIST
                    and all(isinstance(i, dict) for i in x + y)):
                for i in range(min(len(x), len(y))):
                    walk(x[i], y[i], f"{path}[{i}]")
                for i in range(min(len(x), len(y)), len(y)):
                    push(added, {"path": f"{path}[{i}]", "new": _brief(y[i])})
                for i in range(min(len(x), len(y)), len(x)):
                    push(removed, {"path": f"{path}[{i}]", "old": _brief(x[i])})
                return
            if x != y:
                push(changes, {"path": path, "old": _brief(x), "new": _brief(y)})
            return
        if x != y:
            push(changes, {"path": path, "old": x, "new": y})

    walk(a, b, "")

    ra = ws.validate(copy.deepcopy(a))
    rb = ws.validate(copy.deepcopy(b))
    da, db = ra.derived, rb.derived
    body_a = (da.get("bodies") or [{}])[0]
    body_b = (db.get("bodies") or [{}])[0]

    def delta(label, x, y):
        if x != y:
            return {"label": label, "from": x, "to": y}
        return None

    derived = [d for d in (
        delta("评分", ra.score, rb.score),
        delta("致命项", ra.fatal, rb.fatal),
        delta("告警项", ra.warn, rb.warn),
        delta("反常识度", (da.get("weirdness") or {}).get("score"),
              (db.get("weirdness") or {}).get("score")),
        delta("表面重力 g", body_a.get("gravity_g_calc"), body_b.get("gravity_g_calc")),
        delta("密度 g/cc", body_a.get("density_gcc_calc"), body_b.get("density_gcc_calc")),
        delta("逃逸速度 km/s", body_a.get("v_escape_km_s"), body_b.get("v_escape_km_s")),
        delta("表面温度 K", body_a.get("t_surface_k"), body_b.get("t_surface_k")),
        delta("G'/G", da.get("g_ratio"), db.get("g_ratio")),
        delta("系统总光度 L☉", da.get("total_luminosity"), db.get("total_luminosity")),
    ) if d]

    fa = {c.id for c in ra.checks if c.verdict == "fatal"}
    fb = {c.id for c in rb.checks if c.verdict == "fatal"}
    wa = {c.id for c in ra.checks if c.verdict == "warn"}
    wb = {c.id for c in rb.checks if c.verdict == "warn"}

    paths = ([c["path"] for c in changes] + [c["path"] for c in added]
             + [c["path"] for c in removed])
    return {
        "ok": True,
        "version": {"from": (a.get("meta") or {}).get("version"),
                    "to": (b.get("meta") or {}).get("version")},
        "changes": changes, "added": added, "removed": removed,
        "truncated": truncated[0],
        "derived": derived,
        "new_fatal": sorted(fb - fa), "fixed": sorted(fa - fb),
        "new_warn": sorted(wb - wa),
        "downstream": downstream_tasks(paths),
    }


def downstream_tasks(paths: list) -> list:
    """按改动面推断必须重跑的派生产物。顺序 = 推荐的执行顺序。"""
    joined = " ".join(paths)
    tasks = [{"task": "export", "cmd": "export <world> --md 世界档案.md --json-out 审查报告.json",
              "why": "任何改动都要重出档案与审查报告"},
             {"task": "preview", "cmd": "preview <world>",
              "why": "3D 页内嵌整份 world.json"}]
    if re.search(r"biomes|planet_map|radius_earth|radius_km|rotation_hours|"
                 r"axial_tilt_deg|albedo|greenhouse_delta_k|orbit\.a_au", joined):
        tasks.append({"task": "map", "cmd": "map <world> --run --write --yes",
                      "why": "地形/气候/群系参数变了，地图与 CA 粗场要重推"})
    if re.search(r"biology\.(evolution|trophic_levels)", joined):
        tasks.append({"task": "ca", "cmd": "ca <world> --run --check",
                      "why": "生态规则或营养级变了，演化结论要重新复算"})
    if re.search(r"cosmology\.calendar|sky_phenomena|rotation_hours", joined):
        tasks.append({"task": "slice", "cmd": "slice <world>",
                      "why": "历法/天象变了，第一人称切片要重写并复检"})
    if re.search(r"physics|cosmology", joined):
        tasks.append({"task": "redteam", "cmd": "redteam <world> --check",
                      "why": "物理与宇宙层变了，旧质疑可能已不成立"})
    return tasks
