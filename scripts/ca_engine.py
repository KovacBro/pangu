# -*- coding: utf-8 -*-
"""
盘古 · 世界原生元胞自动机（World-Native CA）
==========================================
不做通用玩具模型。CA 的每个零件都从 world.json 编译：

    网格   ← grid，格距由天体半径推
    状态   ← states（必须由作者声明，对应 trophic_levels / chemistry 的真实生态位）
    规则   ← rules[]，每条必须挂 source 点路径，可被 resolve_path 追溯到设定
    时间   ← clock.hours_per_step，由 calendar.day_hours 推
    强迫   ← forcing[]，天文钟驱动：双星辐照 / 潮汐 / 合日脉冲 / 季节

编译失败 = 规则不自洽。编译器不降级、不兜底、不内置任何规则名，
只报出哪几条规则互相矛盾，并要求重新设计。

对外接口：
    compile_evolution(evo, world) -> Program
    run(prog, steps, seed, snapshot_steps) -> Stats
    summarize(prog, stats) -> dict
    check_evolution(evo, world) -> dict
"""

from __future__ import annotations

import math
import random
import re
import zlib
from dataclasses import dataclass, field
from typing import Any

import world_schema as ws

# ── 硬上限（防止一格一格跑到天荒地老）──────────────────────────────
MAX_SIDE = 512
MAX_STEPS = 5000
MAX_RADIUS = 2
MAX_RULES = 64
MAX_STATES = 24

SHAPE_MOORE = "moore"
SHAPE_VN = "von-neumann"
TOPOLOGIES = ("lon-closed", "torus", "open")
FORCING_KINDS = ("insolation", "tidal", "pulse", "seasonal")


# ════════════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════════════

@dataclass
class StateDef:
    id: str
    name: str
    kind: str = "other"          # substrate | producer | consumer | hazard | water | other
    color: str = "#888888"
    source: str = ""
    initial_share: float = 0.0
    index: int = -1


@dataclass
class ForcingDef:
    id: str
    name: str
    kind: str = "insolation"
    period_days: float = 0.0
    phase_deg: float = 0.0
    amp: float = 1.0
    source: str = ""


@dataclass
class RuleDef:
    id: str
    src: int
    dst: int
    prob: float
    when: dict
    forcing: str
    gain: float
    source: str
    cost: float
    retrograde: bool
    radius: int
    shape: str
    map_gain: float = 0.0


@dataclass
class Program:
    grid: dict = field(default_factory=dict)
    clock: dict = field(default_factory=dict)
    states: list = field(default_factory=list)
    forcing: list = field(default_factory=list)
    rules: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    initial: dict = field(default_factory=dict)   # state_index -> share
    map: dict = field(default_factory=dict)       # 地图耦合：字段 + 配置

    @property
    def ok(self) -> bool:
        return not self.errors

    def state_ids(self) -> dict:
        return {s.index: s.id for s in self.states}


@dataclass
class Stats:
    steps: int = 0
    series: dict = field(default_factory=dict)     # state_id -> [density]
    steady: dict = field(default_factory=dict)
    cycle_steps: int = 0
    collapse_prob: float = 0.0
    collapsed: bool = False
    energy_spent: float = 0.0
    snapshots: dict = field(default_factory=dict)  # step -> list of state_index
    primary: str = ""
    final_hash: str = ""
    max_drawdown: float = 0.0
    resilience: float = 0.0
    final_grid: list = field(default_factory=list)


# ════════════════════════════════════════════════════════════════════
# 小工具
# ════════════════════════════════════════════════════════════════════

def _f(v: Any, default: float = 0.0) -> float:
    return ws._num(v, default)


def _parse_count(expr: Any, value: int) -> bool:
    """阈值表达式：2 / '==1' / '>=2' / '<3' / '2..4'。"""
    if isinstance(expr, bool):
        return False
    if isinstance(expr, (int, float)):
        return value == int(expr)
    s = str(expr or "").strip()
    m = re.match(r"^(\d+)\s*\.\.\s*(\d+)$", s)
    if m:
        return int(m.group(1)) <= value <= int(m.group(2))
    m = re.match(r"^(>=|<=|==|>|<)\s*(\d+)$", s)
    if m:
        op, k = m.group(1), int(m.group(2))
        return {">=": value >= k, "<=": value <= k,
                "==": value == k, ">": value > k, "<": value < k}[op]
    if re.match(r"^\d+$", s):
        return value == int(s)
    return False


def neighbor_capacity(radius: int, shape: str) -> int:
    r = max(1, int(radius))
    if shape == SHAPE_VN:
        return 2 * r * (r + 1)
    return (2 * r + 1) ** 2 - 1


def _forcing_value(f: ForcingDef, t_hours: float) -> float:
    """天文钟：某项强迫在 t 时刻的强度。"""
    if f.period_days <= 0:
        return f.amp
    ph = (t_hours / (f.period_days * 24.0) + f.phase_deg / 360.0) % 1.0
    if f.kind == "pulse":
        return f.amp if ph >= 0.93 else 0.0
    # insolation / tidal / seasonal：一个周期一次峰
    return f.amp * (0.5 - 0.5 * math.cos(2.0 * math.pi * ph))


# ════════════════════════════════════════════════════════════════════
# 编译
# ════════════════════════════════════════════════════════════════════

def compile_evolution(evo: Any, world: dict) -> Program:
    """
    把 biology.evolution 编译成可运行的 Program。

    所有矛盾都进 Program.errors —— 有 error 就不许跑，要求重设计规则。
    """
    prog = Program()
    if not isinstance(evo, dict):
        prog.errors.append("biology.evolution 缺失或不是对象：没有可编译的模型")
        return prog

    _compile_grid(evo, prog)
    _compile_clock(evo, prog, world)
    _compile_states(evo, prog, world)
    _compile_forcing(evo, prog, world)
    _compile_rules(evo, prog, world)
    _compile_map_coupling(evo, prog, world)
    _diagnose(prog, world)
    return prog


def _compile_grid(evo: dict, prog: Program) -> None:
    g = evo.get("grid")
    if not isinstance(g, dict):
        prog.errors.append("grid 缺失：必须声明 nx / ny（该世界的空间分辨率）")
        return
    nx = int(_f(g.get("nx"), 0))
    ny = int(_f(g.get("ny"), 0))
    if nx <= 0 or ny <= 0:
        prog.errors.append(f"grid 尺寸非法：nx={nx} ny={ny}")
        return
    if nx > MAX_SIDE or ny > MAX_SIDE:
        prog.errors.append(f"grid {nx}×{ny} 超过上限 {MAX_SIDE}×{MAX_SIDE}")
        return
    topo = str(g.get("topology") or "lon-closed")
    if topo not in TOPOLOGIES:
        prog.warnings.append(f"未知 topology「{topo}」，按 lon-closed 处理")
        topo = "lon-closed"
    prog.grid = {
        "nx": nx, "ny": ny,
        "cell_km": _f(g.get("cell_km"), 0.0),
        "topology": topo,
        "area_weighted": bool(g.get("area_weighted")),
    }
    if prog.grid["area_weighted"] and topo != "lon-closed":
        prog.warnings.append(
            "area_weighted 只在 lon-closed（经纬网格）下有意义，当前拓扑不会按 cos(lat) 加权")


def _compile_clock(evo: dict, prog: Program, world: dict) -> None:
    c = evo.get("clock")
    # 缺省：用历法日长反推（一步 = 一天 / 40）
    if not isinstance(c, dict):
        day_h = _f(ws._get(world, "cosmology", "calendar", "day_hours"), 0.0)
        c = {"hours_per_step": day_h / 40.0 if day_h else 0.5}
        prog.warnings.append("clock 缺失，按一天 40 步折算")
    hps = _f(c.get("hours_per_step"), 0.0)
    if hps <= 0:
        prog.errors.append("clock.hours_per_step 必须为正数——一步是多长的时间里没有意义")
        hps = 0.0
    prog.clock = {
        "hours_per_step": hps,
        "steps_per_day": _f(c.get("steps_per_day"), (24.0 / hps) if hps else 0.0),
    }


def _compile_states(evo: dict, prog: Program, world: dict) -> None:
    raw = evo.get("states")
    if not isinstance(raw, list) or not raw:
        prog.errors.append(
            "states 为空：状态集必须由作者声明（对应 trophic_levels / chemistry 里真实存在的生态位）")
        return
    if len(raw) > MAX_STATES:
        prog.errors.append(f"状态数 {len(raw)} 超过上限 {MAX_STATES}")
        return

    seen = {}
    for i, x in enumerate(raw):
        if not isinstance(x, dict):
            prog.errors.append(f"states[{i}] 不是对象")
            continue
        sid = str(x.get("id") or "").strip()
        if not sid:
            prog.errors.append(f"states[{i}] 缺 id")
            continue
        if sid in seen:
            prog.errors.append(f"状态 id「{sid}」重复定义")
            continue
        seen[sid] = i
        sd = StateDef(
            id=sid,
            name=str(x.get("name") or sid),
            kind=str(x.get("kind") or "other"),
            color=str(x.get("color") or "#888888"),
            source=str(x.get("source") or ""),
            initial_share=max(0.0, _f(x.get("initial_share"), 0.0)),
            index=i,
        )
        prog.states.append(sd)

    # 初始分布：states[].initial_share 优先，其次 evo.initial
    shares = {s.index: s.initial_share for s in prog.states}
    init = evo.get("initial")
    if isinstance(init, dict):
        for k, v in init.items():
            idx = seen.get(str(k))
            if idx is None:
                prog.errors.append(f"initial 里的状态「{k}」未在 states 中定义")
                continue
            shares[idx] = max(0.0, _f(v, 0.0))

    total = sum(shares.values())
    if total <= 0:
        prog.errors.append("初始分布为空：states[].initial_share 与 initial 都没有给出正数")
        return
    if abs(total - 1.0) > 0.02:
        prog.warnings.append(f"初始份额合计 {total:.2f}，已归一化")
    prog.initial = {k: v / total for k, v in shares.items() if v > 0}


def _compile_forcing(evo: dict, prog: Program, world: dict) -> None:
    raw = evo.get("forcing") or []
    if not isinstance(raw, list):
        prog.errors.append("forcing 必须是数组")
        return
    for i, x in enumerate(raw):
        if not isinstance(x, dict):
            prog.errors.append(f"forcing[{i}] 不是对象")
            continue
        fid = str(x.get("id") or f"F{i + 1}")
        kind = str(x.get("kind") or "insolation")
        if kind not in FORCING_KINDS:
            prog.warnings.append(f"未知强迫类型「{kind}」，按 insolation 处理")
            kind = "insolation"
        prog.forcing.append(ForcingDef(
            id=fid,
            name=str(x.get("name") or fid),
            kind=kind,
            period_days=_f(x.get("period_days"), 0.0),
            phase_deg=_f(x.get("phase_deg"), 0.0),
            amp=_f(x.get("amp"), 1.0),
            source=str(x.get("source") or ""),
        ))


def _compile_rules(evo: dict, prog: Program, world: dict) -> None:
    raw = evo.get("rules")
    if not isinstance(raw, list) or not raw:
        prog.errors.append("rules 为空：没有规则就没有演化")
        return
    if len(raw) > MAX_RULES:
        prog.errors.append(f"规则数 {len(raw)} 超过上限 {MAX_RULES}")
        return

    by_id = {s.id: s.index for s in prog.states}
    forcing_ids = {f.id for f in prog.forcing}

    for i, x in enumerate(raw):
        if not isinstance(x, dict):
            prog.errors.append(f"rules[{i}] 不是对象")
            continue
        rid = str(x.get("id") or f"R{i + 1}")
        fro = str(x.get("from") or "").strip()
        to = str(x.get("to") or "").strip()
        if fro not in by_id:
            prog.errors.append(f"{rid}: from「{fro}」未在 states 中定义")
            continue
        if to not in by_id:
            prog.errors.append(f"{rid}: to「{to}」未在 states 中定义")
            continue

        when = x.get("when") if isinstance(x.get("when"), dict) else {}
        when = _normalize_when(when, by_id, prog, rid)

        fid = str(x.get("forcing") or "")
        if fid and fid not in forcing_ids:
            prog.errors.append(f"{rid}: forcing「{fid}」未在 forcing 中定义")
            fid = ""

        nb = when.get("neighbors") if isinstance(when.get("neighbors"), dict) else {}
        radius = int(_f(nb.get("radius"), 1))
        shape = str(nb.get("shape") or SHAPE_MOORE)
        if shape not in (SHAPE_MOORE, SHAPE_VN):
            prog.warnings.append(f"{rid}: 未知邻居形状「{shape}」，按 moore 处理")
            shape = SHAPE_MOORE
        if radius < 1 or radius > MAX_RADIUS:
            prog.errors.append(f"{rid}: 邻居半径 {radius} 超出 1–{MAX_RADIUS}")
            radius = 1

        cost_block = x.get("cost")
        cost = 0.0
        if isinstance(cost_block, dict):
            cost = _f(cost_block.get("value"), 0.0)
        elif cost_block is not None:
            cost = _f(cost_block, 0.0)

        prog.rules.append(RuleDef(
            id=rid,
            src=by_id[fro],
            dst=by_id[to],
            prob=max(0.0, min(1.0, _f(x.get("prob"), 0.0))),
            when=when,
            forcing=fid,
            gain=_f(x.get("forcing_gain"), 0.0),
            source=str(x.get("source") or ""),
            cost=cost,
            retrograde=bool(x.get("retrograde")),
            radius=radius,
            shape=shape,
            map_gain=max(0.0, _f(x.get("map_gain"), 0.0)),
        ))


def _main_body(world: dict) -> dict:
    bodies = ws._get(world, "cosmology", "bodies", default=[]) or []
    for b in bodies:
        if isinstance(b, dict) and str(b.get("kind") or "") == "planet":
            return b
    for b in bodies:
        if isinstance(b, dict):
            return b
    return {}


def _decode_coarse(coarse: dict) -> dict:
    digits = {c: i for i, c in enumerate("0123456789abcdefghijklmnopqrstuvwxyz")}
    nx, ny = int(_f(coarse.get("nx"), 0)), int(_f(coarse.get("ny"), 0))
    if nx <= 0 or ny <= 0:
        return {}
    out = {}
    for k in ("habitat", "temperature", "elevation"):
        s = str(coarse.get(k) or "")
        if len(s) != nx * ny:
            continue
        out[k] = [digits.get(c, 0) / 36.0 for c in s]
    oc = str(coarse.get("ocean") or "")
    if len(oc) == nx * ny:
        out["ocean"] = [1.0 if c == "1" else 0.0 for c in oc]
    out["nx"], out["ny"] = nx, ny
    return out


def _sample_field(field: dict, key: str, tx: int, ty: int) -> list:
    """把 72×36 的粗场双线性重采样到 CA 网格。经度环绕。"""
    nx, ny = int(field.get("nx") or 0), int(field.get("ny") or 0)
    arr = field.get(key)
    if not arr or nx <= 0 or ny <= 0:
        return [0.0] * (tx * ty)
    out = [0.0] * (tx * ty)
    for y in range(ty):
        sy = (y + 0.5) * ny / ty - 0.5
        y0 = max(0, min(ny - 1, int(math.floor(sy))))
        fy = sy - y0
        y1 = min(ny - 1, y0 + 1)
        for x in range(tx):
            sx = (x + 0.5) * nx / tx - 0.5
            x0 = int(math.floor(sx)) % nx
            fx = sx - math.floor(sx)
            x1 = (x0 + 1) % nx
            a = arr[y0 * nx + x0] * (1 - fx) + arr[y0 * nx + x1] * fx
            b = arr[y1 * nx + x0] * (1 - fx) + arr[y1 * nx + x1] * fx
            out[y * tx + x] = a * (1 - fy) + b * fy
    return out


def _compile_map_coupling(evo: dict, prog: Program, world: dict) -> None:
    mc = evo.get("map_coupling")
    if not isinstance(mc, dict):
        return
    if not prog.states or not prog.rules or not prog.grid:
        return
    body = _main_body(world)
    pm = body.get("planet_map") if isinstance(body.get("planet_map"), dict) else {}
    coarse = pm.get("coarse") if isinstance(pm.get("coarse"), dict) else {}
    if not coarse:
        prog.errors.append(
            "map_coupling 已开启，但 world.json 没有 planet_map.coarse——"
            "先跑 pangu.py map --run --write --yes，不然地图耦合是空转")
        return
    field = _decode_coarse(coarse)
    if not field:
        prog.errors.append("planet_map.coarse 无法解析（长度或 base36 不合法）")
        return
    fname = str(mc.get("field") or "habitat")
    if fname not in field:
        prog.errors.append(f"map_coupling.field「{fname}」不在 coarse 场里")
        fname = "habitat"
    if fname not in field:
        return
    nx, ny = prog.grid["nx"], prog.grid["ny"]
    sampled = _sample_field(field, fname, nx, ny)
    prog.map = {
        "field": fname,
        "cfg": {
            "initial_from_map": bool(mc.get("initial_from_map", True)),
            "initial_bias": max(0.0, min(1.0, _f(mc.get("initial_bias"), 0.8))),
            "growth_gain": max(0.0, _f(mc.get("growth_gain"), 0.0)),
        },
        "fields": {fname: sampled},
        "source_res": [field["nx"], field["ny"]],
    }
    # 指定要耦合的规则；不写就只耦合生产者规则
    ids = mc.get("rules")
    by_id = {r.id: r for r in prog.rules}
    if isinstance(ids, list) and ids:
        miss = [str(i) for i in ids if str(i) not in by_id]
        if miss:
            prog.errors.append("map_coupling.rules 引用了不存在的规则：" + "、".join(miss))
        for i in ids:
            r = by_id.get(str(i))
            if r and r.map_gain <= 0:
                r.map_gain = max(0.0, _f(mc.get("growth_gain"), 0.8))
    elif prog.map["cfg"]["growth_gain"] > 0:
        for r in prog.rules:
            if any(s.index == r.dst and s.kind in ("producer", "consumer")
                   for s in prog.states):
                r.map_gain = prog.map["cfg"]["growth_gain"]


def _normalize_when(when: dict, by_id: dict, prog: Program, rid: str) -> dict:
    """把 neighbors.of（状态 id）换成 of_index，便于运行期计数。"""
    if not when:
        return {}
    out = {}
    for key, val in when.items():
        if key == "neighbors" and isinstance(val, dict):
            nb = dict(val)
            of = str(nb.get("of") or "").strip()
            if of:
                if of not in by_id:
                    prog.errors.append(f"{rid}: neighbors.of「{of}」未在 states 中定义")
                else:
                    nb["of_index"] = by_id[of]
            out["neighbors"] = nb
        elif key in ("all_of", "any_of", "none_of") and isinstance(val, list):
            out[key] = [_normalize_when(v, by_id, prog, rid)
                        for v in val if isinstance(v, dict)]
        elif key in ("forcing_above", "forcing_below") and isinstance(val, dict):
            out[key] = dict(val)
        elif key == "neighbors":
            pass
    return out


# ════════════════════════════════════════════════════════════════════
# 冲突诊断（编译失败 = 规则不自洽）
# ════════════════════════════════════════════════════════════════════

def _diagnose(prog: Program, world: dict) -> None:
    if not prog.states or not prog.rules:
        return

    # 1) 规则溯源：每条规则必须能在 world.json 里找到出处
    for r in prog.rules:
        if not r.source:
            prog.errors.append(f"{r.id}: 缺 source —— 规则必须说明它出自哪条设定")
        elif not ws.resolve_path(world, r.source)[0]:
            why = ws.resolve_path(world, r.source)[2]
            prog.errors.append(f"{r.id}: source「{r.source}」无法解析（{why}）")

    # 2) 邻居阈值越界
    for r in prog.rules:
        nb = r.when.get("neighbors") if isinstance(r.when.get("neighbors"), dict) else None
        if not nb:
            continue
        cap = neighbor_capacity(r.radius, r.shape)
        if not _threshold_reachable(nb.get("count"), cap):
            prog.errors.append(
                f"{r.id}: 邻居计数阈值 {nb.get('count')} 不可能满足"
                f"（{r.shape} 半径 {r.radius} 最多 {cap} 个邻居）")

    # 3) 概率溢出：同一源状态、同为无条件规则，概率和 > 1 是自相矛盾
    free = {}
    for r in prog.rules:
        if not r.when:
            free.setdefault(r.src, []).append(r)
    for src, rs in free.items():
        total = sum(r.prob for r in rs)
        if total > 1.0 + 1e-9:
            prog.errors.append(
                f"状态「{_sid(prog, src)}」的无条件规则概率合计 {total:.2f} > 1："
                f"这些规则在抢同一个格子（{'、'.join(r.id for r in rs)}），必须重新分配概率")

    # 4) 双向振荡：A→B 与 B→A 都是无条件高概率，格子会在两态间抖动
    pair = {}
    for r in prog.rules:
        if not r.when and r.src != r.dst and r.prob >= 0.5:
            pair[(r.src, r.dst)] = r
    for (a, b), r in pair.items():
        back = pair.get((b, a))
        if back and r.prob + back.prob > 0.95:
            prog.errors.append(
                f"{r.id} 与 {back.id} 构成无冷却的双向振荡"
                f"（{_sid(prog, a)}⇄{_sid(prog, b)}，概率 {r.prob:.2f}+{back.prob:.2f}）："
                f"至少一条要加 when 条件（如邻居阈值）或降低概率")

    # 5) 悬空状态：既不是任何规则的源，也不是任何规则的目标
    touched = set()
    for r in prog.rules:
        touched.add(r.src)
        touched.add(r.dst)
    for s in prog.states:
        if s.index not in touched:
            prog.errors.append(
                f"状态「{s.id}」悬空：没有任何规则读它或写它——这个生态位是死设定")

    # 6) 生态入口：必须有规则能产生生产者
    producers = [s.index for s in prog.states if s.kind == "producer"]
    if not producers:
        prog.errors.append("没有 kind=producer 的状态：生态没有能量入口（谁把无机变成有机？）")
    else:
        made = {r.dst for r in prog.rules}
        if not any(p in made for p in producers):
            prog.warnings.append("生产者状态只能靠初始分布出现——没有任何规则能重新长出生产者")

    # 7) 三律：逆行律与代价律必须落到规则上
    if not any(r.retrograde for r in prog.rules):
        prog.errors.append(
            "没有一条规则标 retrograde: true —— 逆行律没落到演化机制上。"
            "挑一条与地球直觉相反的转移（比如「光照太强反而抑制生长」）并标注")
    if not any(r.cost > 0 for r in prog.rules):
        prog.errors.append(
            "没有一条规则标了 cost —— 代价律没落到演化机制上。"
            "每个转移都要消耗该世界的能量货币（biology.energy_currency）")

    # 8) 强迫项周期与历法对不上
    cal = ws._get(world, "cosmology", "calendar", default={}) or {}
    month_d = _f(cal.get("month_days"), 0.0)
    day_h = _f(cal.get("day_hours"), 0.0)
    for f in prog.forcing:
        if f.period_days <= 0:
            prog.warnings.append(f"强迫项「{f.id}」没给周期，将视为常数")
            continue
        if not f.source:
            prog.warnings.append(f"强迫项「{f.id}」缺 source，无法溯源")
            continue
        if not ws.resolve_path(world, f.source)[0]:
            prog.errors.append(
                f"强迫项「{f.id}」的 source「{f.source}」无法解析")
        if month_d and abs(f.period_days - month_d) / month_d < 0.02:
            prog.warnings.append(
                f"强迫项「{f.id}」周期 {f.period_days:g}d 恰等于历法月长——"
                f"这是「每 {month_d:g} 天一次的灾变」的合法来源")
        if day_h and f.period_days * 24.0 < day_h * 0.99:
            prog.warnings.append(
                f"强迫项「{f.id}」周期 {f.period_days * 24.0:.1f}h 短于一天 {day_h:g}h，"
                f"时间步可能采样不到峰值")

    # 9) 概率为 0 / 永远接不到的规则
    for r in prog.rules:
        if r.prob <= 0:
            prog.warnings.append(f"{r.id}: prob=0，这条规则永远不会触发")
    incoming = {r.dst for r in prog.rules}
    initial_ids = set(prog.initial)
    for s in prog.states:
        if s.index not in incoming and s.index not in initial_ids:
            prog.warnings.append(f"状态「{s.id}」只能靠初始分布出现，没有任何规则能重新产生它")

    # 10) 地图耦合落点
    if prog.map:
        n = prog.grid.get("nx", 0) * prog.grid.get("ny", 0)
        for k, arr in prog.map.get("fields", {}).items():
            if len(arr) != n:
                prog.errors.append(f"地图场「{k}」长度 {len(arr)} ≠ 网格 {n}")
        coupled = [r.id for r in prog.rules if r.map_gain > 0]
        if not coupled:
            prog.warnings.append("开启 map_coupling 但没有任何规则的 map_gain > 0——"
                                 "地图只影响初始分布，不影响生长")
        else:
            prog.warnings.append("地图耦合已启用：" + "、".join(coupled))


def _sid(prog: Program, idx: int) -> str:
    for s in prog.states:
        if s.index == idx:
            return s.id
    return str(idx)


def _threshold_reachable(expr: Any, cap: int) -> bool:
    """阈值是否在 [0, cap] 内可达。"""
    if isinstance(expr, (int, float)) and not isinstance(expr, bool):
        return 0 <= int(expr) <= cap
    s = str(expr or "").strip()
    m = re.match(r"^(\d+)\s*\.\.\s*(\d+)$", s)
    if m:
        return int(m.group(1)) <= cap
    m = re.match(r"^(>=|<=|==|>|<)\s*(\d+)$", s)
    if m:
        op, k = m.group(1), int(m.group(2))
        return {"<=": k >= 0, "==": 0 <= k <= cap, ">=": k <= cap,
                "<": k <= cap + 1, ">": k < cap}[op]
    return False


# ════════════════════════════════════════════════════════════════════
# 运行
# ════════════════════════════════════════════════════════════════════

def _build_neighbors(nx: int, ny: int, radius: int, shape: str, topo: str) -> list:
    wrap_x = topo in ("lon-closed", "torus")
    wrap_y = topo == "torus"
    offs = []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            if shape == SHAPE_VN and abs(dx) + abs(dy) > radius:
                continue
            offs.append((dx, dy))
    table = []
    for y in range(ny):
        for x in range(nx):
            lst = []
            for dx, dy in offs:
                xx, yy = x + dx, y + dy
                if wrap_x:
                    xx %= nx
                elif xx < 0 or xx >= nx:
                    continue
                if wrap_y:
                    yy %= ny
                elif yy < 0 or yy >= ny:
                    continue
                lst.append(yy * nx + xx)
            table.append(lst)
    return table


def _initial_grid(prog: Program, rnd: random.Random) -> list:
    n = prog.grid["nx"] * prog.grid["ny"]
    items = sorted(prog.initial.items())
    total = sum(v for _, v in items) or 1.0
    cuts, acc = [], 0.0
    for idx, share in items:
        acc += share / total
        cuts.append((acc, idx))
    grid = [0] * n
    if not prog.map or not prog.map.get("cfg", {}).get("initial_from_map"):
        for i in range(n):
            u = rnd.random()
            for c, idx in cuts:
                if u <= c:
                    grid[i] = idx
                    break
            else:
                grid[i] = cuts[-1][1]
        return grid

    # 地图耦合：有宜居度的地方更容易先长出生产/消费者，裸岩留在贫瘠处
    field = prog.map["fields"].get(prog.map["field"]) or []
    bias = prog.map["cfg"].get("initial_bias", 0.8)
    kind = {s.index: s.kind for s in prog.states}
    for i in range(n):
        h = field[i] if i < len(field) else 0.5
        h = max(0.0, min(1.0, h))
        weights = []
        for state_idx, _share in items:
            base = prog.initial[state_idx]
            k = kind.get(state_idx, "other")
            if k in ("producer", "consumer"):
                factor = (0.12 + 0.88 * h) ** max(0.05, bias)
            elif k == "substrate":
                factor = (1.05 - 0.85 * h) ** max(0.05, bias)
            else:
                factor = 0.55 + 0.45 * h
            weights.append(max(1e-9, base * factor))
        s = sum(weights)
        u = rnd.random() * s
        acc2 = 0.0
        for (c, idx), w in zip(cuts, weights):
            acc2 += w
            if u <= acc2:
                grid[i] = idx
                break
        else:
            grid[i] = items[-1][1]
    return grid


def run(prog: Program, steps: int = None, seed: int = None,
        snapshot_steps=(), max_side_snapshot: int = 0) -> Stats:
    """同步更新跑演化。同 seed 同参数必须逐格一致。"""
    if not prog.ok:
        raise ValueError("模型未通过编译：" + "；".join(prog.errors[:3]))

    nx, ny = prog.grid["nx"], prog.grid["ny"]
    n = nx * ny
    total = int(_f(steps, _f(prog.clock.get("steps"), 400))) if steps is not None else 400
    total = max(1, min(int(total), MAX_STEPS))
    rnd = random.Random(7 if seed is None else int(seed))

    # 每条规则用自己的邻居半径/形状：1.1.0 用全局最大半径建表，
    # 半径 1 的规则会偷看到半径 2 的邻居——这是错的，1.1.1 修掉。
    combos = {(r.radius, r.shape) for r in prog.rules}
    neigh_by = {c: _build_neighbors(nx, ny, c[0], c[1], prog.grid["topology"])
                for c in combos}

    by_src = {}
    for r in prog.rules:
        by_src.setdefault(r.src, []).append(r)
    for k in by_src:
        by_src[k].sort(key=lambda r: (0 if r.when else 1, -r.prob))

    # 经纬网格按 cos(lat) 加权：极区格子小，不该和赤道一格同权
    cell_w = [1.0] * n
    if prog.grid.get("area_weighted"):
        row_w = []
        for y in range(ny):
            la = math.radians(90.0 - (y + 0.5) * 180.0 / ny)
            row_w.append(max(0.02, math.cos(la)))
        sw = sum(row_w) or 1.0
        cell_w = [row_w[y] / sw for y in range(ny) for _ in range(nx)]
    wsum = sum(cell_w) or 1.0

    ids = prog.state_ids()
    cur = _initial_grid(prog, rnd)
    hps = prog.clock.get("hours_per_step") or 0.5
    snaps = sorted({int(s) for s in snapshot_steps})
    stats = Stats(steps=total)
    stats.series = {sid: [] for sid in ids.values()}
    snapshots = {}
    spent = 0.0
    map_field = (prog.map.get("fields", {}).get(prog.map.get("field"))
                 if prog.map else None)

    def _record(grid):
        counts = [0.0] * (max(ids) + 1)
        for i, v in enumerate(grid):
            counts[v] += cell_w[i]
        for idx, sid in ids.items():
            stats.series[sid].append(counts[idx] / wsum)

    def _snap(step):
        if step not in snaps:
            return
        scale = 1
        if max_side_snapshot and nx > max_side_snapshot:
            scale = max(1, nx // max_side_snapshot)
        snapshots[step] = (list(grid_now), scale)

    if 0 in snaps:
        grid_now = cur
        _snap(0)
    _record(cur)

    for t in range(1, total + 1):
        t_hours = t * hps
        fvals = {f.id: _forcing_value(f, t_hours) for f in prog.forcing}
        new = cur[:]
        for idx in range(n):
            sv = cur[idx]
            rs = by_src.get(sv)
            if not rs:
                continue
            cnt_cache = {}
            for r in rs:
                if r.when:
                    key = (r.radius, r.shape)
                    cnt = cnt_cache.get(key)
                    if cnt is None:
                        cnt = {}
                        for j in neigh_by[key][idx]:
                            sj = cur[j]
                            cnt[sj] = cnt.get(sj, 0) + 1
                        cnt_cache[key] = cnt
                    if not _when_ok(r.when, cnt, fvals):
                        continue
                p = r.prob
                if r.forcing:
                    p *= (fvals.get(r.forcing, 0.0) ** r.gain) if r.gain else fvals.get(r.forcing, 1.0)
                if r.map_gain and map_field:
                    hh = map_field[idx]
                    p *= ((0.10 + 0.90 * hh) ** r.map_gain)
                if p >= 1.0 or rnd.random() < p:
                    new[idx] = r.dst
                    if r.cost:
                        spent += r.cost
                    break
        cur = new
        _record(cur)
        if t in snaps:
            grid_now = cur
            _snap(t)

    stats.energy_spent = spent
    stats.final_hash = "%08x" % (zlib.crc32(bytes(cur)) & 0xFFFFFFFF)
    stats.final_grid = cur
    stats.snapshots = snapshots
    _finish(prog, stats)
    return stats


def _when_ok(when: dict, cnt: dict, fvals: dict) -> bool:
    if not when:
        return True
    if "all_of" in when and not all(_when_ok(x, cnt, fvals) for x in when["all_of"]):
        return False
    if "any_of" in when and not any(_when_ok(x, cnt, fvals) for x in when["any_of"]):
        return False
    if "none_of" in when and any(_when_ok(x, cnt, fvals) for x in when["none_of"]):
        return False
    nb = when.get("neighbors")
    if isinstance(nb, dict):
        v = cnt.get(int(nb.get("of_index", -1)), 0) if cnt else 0
        if not _parse_count(nb.get("count", ">=1"), v):
            return False
    fa = when.get("forcing_above")
    if isinstance(fa, dict):
        if fvals.get(fa.get("id"), 0.0) < _f(fa.get("value"), 0.0):
            return False
    fb = when.get("forcing_below")
    if isinstance(fb, dict):
        if fvals.get(fb.get("id"), 0.0) > _f(fb.get("value"), 0.0):
            return False
    return True


def _finish(prog: Program, stats: Stats) -> None:
    primary = _primary_state(prog)
    stats.primary = primary
    tail = max(4, stats.steps // 5)

    for sid, ser in stats.series.items():
        seg = ser[-tail:]
        stats.steady[sid] = sum(seg) / len(seg) if seg else 0.0

    ser = stats.series.get(primary) or []
    stats.cycle_steps = _cycle_steps(ser)

    head = ser[:max(1, stats.steps // 10)]
    init_d = sum(head) / len(head) if head else 0.0
    end_d = stats.steady.get(primary, 0.0)
    stats.collapsed = bool(init_d > 0.02 and end_d < init_d * 0.2)
    stats.collapse_prob = _collapse_prob(ser, init_d)
    stats.max_drawdown = _max_drawdown(ser)
    stats.resilience = _resilience(ser)


def _max_drawdown(series) -> float:
    """从历史峰值到之后谷底的最大相对跌幅。"""
    if not series:
        return 0.0
    peak = series[0]
    worst = 0.0
    for v in series:
        peak = max(peak, v)
        if peak > 0:
            worst = max(worst, (peak - v) / peak)
    return round(worst, 3)


def _resilience(series, window: int = 80) -> float:
    """
    生态韧性：跌掉两成之后，在 window 步内回到原峰值 80% 的事件比例。
    低于初值但稳在新平台不算“恢复”，所以用局部峰值当基准。
    """
    if len(series) < 20:
        return 0.0
    peak = series[0]
    events = recovered = 0
    i = 0
    while i < len(series):
        v = series[i]
        if v >= peak:
            peak = v
            i += 1
            continue
        if peak > 0 and v < peak * 0.8:
            events += 1
            target = peak * 0.8
            j = i + 1
            while j < min(len(series), i + window):
                if series[j] >= target:
                    recovered += 1
                    break
                j += 1
            i = j + 1
            peak = max(series[max(0, i - 1)], 0.0)
        else:
            i += 1
    return round(recovered / events, 3) if events else 0.0


def _primary_state(prog: Program) -> str:
    for s in prog.states:
        if s.kind == "producer":
            return s.id
    for s in prog.states:
        if s.kind not in ("substrate",):
            return s.id
    return prog.states[0].id if prog.states else ""


def _cycle_steps(series, window: int = 4) -> int:
    if len(series) < window * 3:
        return 0
    peaks = []
    for i in range(window, len(series) - window):
        seg = series[i - window:i + window + 1]
        if series[i] >= max(seg):
            mean = sum(seg) / len(seg)
            if series[i] > mean * 1.01:
                if not peaks or i - peaks[-1] > window:
                    peaks.append(i)
    if len(peaks) < 2:
        return 0
    gaps = sorted(peaks[i + 1] - peaks[i] for i in range(len(peaks) - 1))
    return int(gaps[len(gaps) // 2])


def _collapse_prob(series, init_d: float) -> float:
    """
    危险事件里真正走向「不可逆灭绝」的比例。

    注意：低于初值但稳在新平台，不算塌缩——那只是换了个稳态。
    只有跌破初值 10% 且回不来，才算这个世界死了。
    """
    if init_d <= 0.01:
        return 0.0
    danger, recover, fatal = init_d * 0.5, init_d * 0.8, init_d * 0.1
    events = deaths = 0
    i = 0
    while i < len(series):
        if series[i] < danger:
            events += 1
            low = series[i]
            j = i
            while j < len(series) and series[j] < recover:
                low = min(low, series[j])
                j += 1
            if low < fatal:
                deaths += 1
            i = j + 1
        else:
            i += 1
    return round(deaths / events, 3) if events else 0.0


# ════════════════════════════════════════════════════════════════════
# 摘要与复算
# ════════════════════════════════════════════════════════════════════

def summarize(prog: Program, stats: Stats) -> dict:
    return {
        "steady_density": round(stats.steady.get(stats.primary, 0.0), 3),
        "cycle_steps": int(stats.cycle_steps),
        "collapse_prob": stats.collapse_prob,
        "measured_at_step": stats.steps,
        "primary_state": stats.primary,
        "state_density": {k: round(v, 3) for k, v in stats.steady.items()},
        "energy_spent": round(stats.energy_spent, 1),
        "max_drawdown": stats.max_drawdown,
        "resilience": stats.resilience,
        "area_weighted": bool(prog.grid.get("area_weighted")),
        "map_coupled": bool(prog.map),
        "final_hash": stats.final_hash,
    }


def check_evolution(evo: dict, world: dict, steps=None, seed=None) -> dict:
    """
    复算比对：用 world.json 里的参数重跑一遍，和 summary 对账。
    同 seed 同结果 —— 抄来的数字在这里会被打回。
    steps / seed 可被命令行覆盖，用于验证「换 seed 就该对不上」。
    """
    prog = compile_evolution(evo, world)
    out = {"ok": False, "errors": list(prog.errors), "warnings": list(prog.warnings),
           "declared": {}, "actual": {}, "diffs": [], "seed": None, "steps": None}
    if not prog.ok:
        return out

    steps = int(_f(steps if steps is not None else evo.get("steps"), 400))
    seed = int(_f(seed if seed is not None else evo.get("seed"), 7))
    out["seed"], out["steps"] = seed, steps
    stats = run(prog, steps=steps, seed=seed)
    actual = summarize(prog, stats)
    declared = evo.get("summary") if isinstance(evo.get("summary"), dict) else {}

    out["actual"] = actual
    out["declared"] = declared
    diffs = []
    # 容差压到浮点级：Python 端同 seed 是逐格确定的，有任何差异都说明数字不是跑出来的。
    # （文档里的 5% 是浏览器 JS 与 Python 之间允许的偏差，不适用于本机复算。）
    for key, tol in (("steady_density", 0.005), ("cycle_steps", 0.02),
                     ("collapse_prob", 0.02), ("energy_spent", 0.01)):
        if key not in declared:
            diffs.append(f"{key} 未声明")
            continue
        a, d = _f(actual.get(key), 0.0), _f(declared.get(key), 0.0)
        base = max(abs(a), abs(d), 1e-9)
        if abs(a - d) / base > tol:
            diffs.append(f"{key}: 声明 {d:g} ≠ 复算 {a:g}（容差 {tol:.1%}）")
    if "final_hash" in declared:
        if str(declared.get("final_hash")) != str(actual.get("final_hash")):
            diffs.append(f"final_hash: 声明 {declared.get('final_hash')} ≠ "
                         f"复算 {actual.get('final_hash')}（逐格不一致）")
    out["diffs"] = diffs
    out["ok"] = not diffs
    return out


# ════════════════════════════════════════════════════════════════════
# 出图
# ════════════════════════════════════════════════════════════════════

def render_snapshot(prog: Program, cells, scale: int = 1) -> tuple:
    """把一格一像素的状态图渲染成 (w, h, pixels)。"""
    import png_writer as pw
    nx, ny = prog.grid["nx"], prog.grid["ny"]
    palette = [pw.hex_to_rgb(s.color) for s in prog.states]
    by_index = {s.index: palette[i] if i < len(palette) else (128, 128, 128)
                for i, s in enumerate(prog.states)}
    scale = max(1, int(scale))
    w, h = nx * scale, ny * scale
    px = bytearray(w * h * 3)
    for y in range(ny):
        for x in range(nx):
            r, g, b = by_index.get(cells[y * nx + x], (40, 40, 40))
            for dy in range(scale):
                base = ((y * scale + dy) * w + x * scale) * 3
                for dx in range(scale):
                    o = base + dx * 3
                    px[o], px[o + 1], px[o + 2] = r, g, b
    return w, h, px
