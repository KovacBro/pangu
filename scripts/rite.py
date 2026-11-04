# -*- coding: utf-8 -*-
"""
盘古 · 七斧状态机
=================
1.1.3 新增：把 `SKILL.md` 里的「七斧表」从文档变成可执行的判定。

    plan       读 world.json → 当前在第几斧、还缺什么、这一斧要问什么、下一步跑什么
    brief_line 一行式结论（validate --brief 用）

设计约束：
  · 纯函数：不读盘、不写盘、不猜内容，只报告「已有什么 / 还缺什么」
  · 判定标准写死在 AXES 与 _missing()，与 SKILL.md 的七斧表一一对应；
    改流程先改表，再改这里，两边不允许漂移
  · 斧 6（启智）可选：纯生态世界填 `civilization.exists = false` 即视为已过
  · 斧位只由**字段完备度**决定，不看分数——分数是斧 7 的事
"""

from __future__ import annotations

import re
from typing import Any

import world_schema as ws


# ════════════════════════════════════════════════════════════════════
# 七斧表（与 SKILL.md 同源）
# ════════════════════════════════════════════════════════════════════

AXES = [
    {
        "n": 1, "id": "chaos", "cn": "混沌", "verb": "定调",
        "writes": ["meta", "seed"],
        "asks": [
            "这世界里最怪的一幕是什么？（一个画面，不是设定）",
            "你希望它给人什么感觉？（三个形容词就够）",
            "有没有绝对不能出现的东西？",
        ],
        "searches": ["<核心意象> concept art description",
                     "<核心意象> scientific feasibility"],
        "hint": "悖论必须是可证伪的陈述句：「三倍地球半径，却仍有固体地表」，不是「充满奇迹」。",
    },
    {
        "n": 2, "id": "dichotomy", "cn": "分判", "verb": "定天",
        "writes": ["cosmology"],
        "asks": [
            "天上有什么？几颗？有没有「天」？",
            "这里的人靠什么知道「过了一年」？",
            "有没有一颗跟着走的月亮或环？（潮汐的账要还）",
        ],
        "searches": ["circumbinary planet habitable zone",
                     "maximum radius rocky planet",
                     "tidal heating rogue planet"],
        "hint": "答不出「怎么计时」的世界，通常是没想清楚轨道。",
    },
    {
        "n": 3, "id": "nomos", "cn": "立律", "verb": "定法",
        "writes": ["physics", "mathematics"],
        "asks": [
            "哪条守恒律被打破了？（或者哪条常数被改了）",
            "为了扛住这个改动，世界付出了什么可量化的代价？",
            "居民的数学会因此缺哪一块？",
        ],
        "searches": ["physics with different gravitational constant consequences",
                     "variable speed of light cosmology",
                     "second law of thermodynamics violation local"],
        "hint": "每条常数改动必须填 why（为什么改）与代价；没有代价列的改动一律删掉。",
    },
    {
        "n": 4, "id": "materia", "cn": "炼质", "verb": "定料",
        "writes": ["chemistry"],
        "asks": [
            "最硬的物质是什么做的？它怎么形成？",
            "这里最常见的液体是什么？（水？还是别的）",
            "有没有一种地球上不存在、这里却遍地都是的材料？",
        ],
        "searches": ["silicon based life chemistry possibility",
                     "superheavy elements island of stability",
                     "room temperature liquid metal"],
        "hint": "文明的建筑与工具，由「这世界最不缺的东西」决定，不由愿望决定。",
    },
    {
        "n": 5, "id": "genesis", "cn": "化生", "verb": "定活",
        "writes": ["biology"],
        "asks": [
            "生物靠吃什么活着？能量怎么变成可用的？",
            "遗传靠什么载体？",
            "生物的代谢废物，出现在大气成分里了吗？",
        ],
        "searches": ["alternative biochemistry solvents",
                     "non DNA genetic information storage",
                     "chemoautotroph ecosystem without sunlight"],
        "hint": "能量流必须闭环：辐照 → 生产者 → 消费者 → 分解者 → 无机物。",
    },
    {
        "n": 6, "id": "anima", "cn": "启智", "verb": "定人",
        "writes": ["civilization"], "optional": True,
        "asks": [
            "他们怎么计时？历法对得上天象吗？",
            "他们的技术跳过了哪个阶段？为什么？",
            "有什么事情，在他们的物理条件下「绝对做不到」？",
        ],
        "searches": ["timekeeping without sun",
                     "civilization without wheel",
                     "astronomy on a binary star"],
        "hint": "文明的形状，由它做不到的事定义，不由它做到的事定义。纯生态世界填 exists=false 跳过。",
    },
    {
        "n": 7, "id": "cosmogony", "cn": "演界", "verb": "定史",
        "writes": ["history", "consistency", "narrative"],
        "asks": [
            "这世界会怎么灭亡？",
            "最想让读者看见的一幕是什么？",
            "如果我是一个住在这里的物理学家，我会觉得哪条不对？",
        ],
        "searches": ["<世界核心机制> failure mode", "<核心意象> visual reference"],
        "hint": "有 fatal 不许交付；先修设定或改代价，再补历史与名场面。",
    },
]

AXE_BY_N = {a["n"]: a for a in AXES}

# 斧 → 公理库领域（`axioms --axe N` 用）
AXE_AXIOM_DOMAINS = {
    1: None,                                  # 混沌：全库
    2: {"cosmos", "math"},
    3: {"physics"},
    4: {"chemistry"},
    5: {"biology"},
    6: {"civilization"},
    7: None,                                  # 演界：全库
}


# ════════════════════════════════════════════════════════════════════
# 小工具
# ════════════════════════════════════════════════════════════════════

def _text(v: Any) -> str:
    return str(v or "").strip()


def _ok(v: Any) -> bool:
    if isinstance(v, str):
        return bool(v.strip())
    if isinstance(v, (list, tuple, dict)):
        return bool(v)
    return v is not None


def _num(v: Any, default: float = 0.0) -> float:
    return ws._num(v, default)


def _dict(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _list(v: Any) -> list:
    return v if isinstance(v, list) else []


# ════════════════════════════════════════════════════════════════════
# 每一斧的「收斧条件」
# ════════════════════════════════════════════════════════════════════

def _missing(world: dict, n: int, rep=None) -> list:
    """返回该斧还缺什么（空列表 = 已收斧）。不猜内容，只报缺口。"""
    cos = _dict(world.get("cosmology"))
    phys = _dict(world.get("physics"))
    chem = _dict(world.get("chemistry"))
    bio = _dict(world.get("biology"))
    civ = world.get("civilization")
    hist = _dict(world.get("history"))
    nar = _dict(world.get("narrative"))
    meta = _dict(world.get("meta"))
    seed = _dict(world.get("seed"))

    if n == 1:
        miss = []
        if not _ok(meta.get("name")):
            miss.append("meta.name（世界叫什么）")
        if not _ok(seed.get("core_paradox")):
            miss.append("seed.core_paradox（一句话悖论：哪条常识是反的）")
        if not _ok(seed.get("resolution")):
            miss.append("seed.resolution（凭什么可能：代价写在哪）")
        if len(_list(meta.get("aesthetic"))) < 2:
            miss.append("meta.aesthetic（2–5 个气质形容词，驱动配色与文风）")
        return miss

    if n == 2:
        miss = []
        stars = _list(cos.get("stars"))
        has_stars = cos.get("has_stars")
        if has_stars is None:
            miss.append("cosmology.has_stars（有恒星吗）")
        elif has_stars and not stars:
            miss.append("cosmology.stars（声明有恒星却没写恒星）")
        elif has_stars is False and not _ok(cos.get("energy_source")):
            miss.append("cosmology.energy_source（无恒星世界必须给替代能源）")
        bodies = [b for b in _list(cos.get("bodies")) if isinstance(b, dict)]
        if not bodies:
            miss.append("cosmology.bodies（至少一颗主角天体）")
        else:
            b0 = bodies[0]
            for f, why in (("radius_km", "真实半径"), ("mass_earth", "质量"),
                           ("orbit.a_au", "轨道半长轴")):
                okp, val, _ = ws.resolve_path(b0, f)
                if not okp or _num(val, 0) <= 0:
                    miss.append(f"cosmology.bodies[0].{f}（{why}）")
        cal = _dict(cos.get("calendar"))
        if _num(cal.get("day_hours"), 0) <= 0:
            miss.append("cosmology.calendar.day_hours（一天多长）")
        if _num(cal.get("year_days"), 0) <= 0:
            miss.append("cosmology.calendar.year_days（一年多长）")
        if not _list(cos.get("sky_phenomena")):
            miss.append("cosmology.sky_phenomena（3–6 条抬头能看见的异常）")
        return miss

    if n == 3:
        miss = []
        consts = [c for c in _list(phys.get("constants")) if isinstance(c, dict)]
        if not consts:
            miss.append("physics.constants（至少一条常数，含 world_value 与 why）")
        else:
            changed = [c for c in consts
                       if abs(_num(c.get("world_value"), 0)
                              / (_num(c.get("earth_value"), 1) or 1) - 1) > 1e-3]
            if not changed:
                miss.append("physics.constants（改过的常数为 0——这是地球换皮）")
            for c in consts:
                if _ok(c.get("world_value")) and not _ok(c.get("why")):
                    miss.append(f"physics.constants[{c.get('symbol', '?')}].why（为什么改）")
        if not _list(phys.get("laws")) and not _list(phys.get("new_interactions")):
            miss.append("physics.laws 或 new_interactions（至少一条新法则 / 新相互作用）")
        if not _dict(world.get("mathematics")):
            miss.append("mathematics（可选：居民的数学缺哪一块）")
        return miss

    if n == 4:
        miss = []
        if not chem:
            return ["chemistry（物质层整段未开）"]
        if not _ok(chem.get("periodic_status")):
            miss.append("chemistry.periodic_status（元素表是否与地球一致）")
        if not _dict(chem.get("solvent")) and not _ok(chem.get("solvent")):
            miss.append("chemistry.solvent（最常见的液体是什么）")
        if not _ok(chem.get("key_bonds")):
            miss.append("chemistry.key_bonds（靠什么结合）")
        if not _list(chem.get("signature_materials")):
            miss.append("chemistry.signature_materials（至少一种标志性材料）")
        return miss

    if n == 5:
        miss = []
        if not bio:
            return ["biology（生命层整段未开）"]
        ec = bio.get("energy_currency")
        if not _ok(ec.get("name") if isinstance(ec, dict)
                   else (ec if isinstance(ec, str) else "")):
            miss.append("biology.energy_currency（能量货币叫什么）")
        gc = bio.get("genetic_carrier")
        if not _ok(gc.get("name") if isinstance(gc, dict)
                   else (gc if isinstance(gc, str) else "")):
            miss.append("biology.genetic_carrier（遗传载体是什么）")
        tl = [t for t in _list(bio.get("trophic_levels")) if isinstance(t, dict)]
        if len(tl) < 2:
            miss.append("biology.trophic_levels（至少两层营养级）")
        else:
            s = sum(_num(t.get("share"), 0) for t in tl)
            if not (0.9 <= s <= 1.1):
                miss.append(f"biology.trophic_levels.share 合计 {s:.2f}（应≈1）")
        if not _dict(bio.get("biochemistry")):
            miss.append("biology.biochemistry（可选：碳基/硅基、主元素、溶剂、体成分）")
        return miss

    if n == 6:
        if civ is None:
            return ["civilization（可选：纯生态世界写 {\"exists\": false} 跳过）"]
        if not isinstance(civ, dict):
            return ["civilization（应为对象）"]
        if civ.get("exists") is False:
            return []
        miss = []
        if not _ok(civ.get("timekeeping")):
            miss.append("civilization.timekeeping（怎么知道过了一年，必须引用 calendar）")
        if not _ok(civ.get("tech_path")):
            miss.append("civilization.tech_path（技术树的另类路径）")
        if not _ok(civ.get("taboo")):
            miss.append("civilization.taboo（因物理代价形成的禁忌）")
        return miss

    if n == 7:
        miss = []
        if rep is None:
            rep = ws.validate(_copy_shallow(world))
        if rep.fatal:
            bad = [c.id for c in rep.checks if c.verdict == "fatal"]
            miss.append(f"validate 仍有 {rep.fatal} 项 fatal：" + "、".join(bad[:4]))
        if not [e for e in _list(hist.get("eras")) if isinstance(e, dict)]:
            miss.append("history.eras（至少三个纪元：起源 / 灾变 / 当下）")
        for k, why in (("three_seconds", "三秒印象"), ("setpiece", "名场面"), ("hook", "钩子")):
            if not _ok(nar.get(k)):
                miss.append(f"narrative.{k}（{why}）")
        return miss

    return []


def _copy_shallow(world: dict) -> dict:
    """validate 会就地写 consistency.score，这里给一份浅拷贝即可（不修改调用方数据）。"""
    import copy
    return copy.deepcopy(world)


# ════════════════════════════════════════════════════════════════════
# 交付门槛（与斧位分开：斧位讲「写到哪」，门槛讲「能不能交」）
# ════════════════════════════════════════════════════════════════════

def gates(world: dict, rep=None) -> list:
    if rep is None:
        rep = ws.validate(_copy_shallow(world))
    d = rep.derived or {}
    wd = d.get("weirdness") or {}
    lo, hi = wd.get("band", ws.WEIRD_BAND)
    nar = _dict(world.get("narrative"))
    sl = _dict(nar.get("slice"))
    rt = [r for r in _list(_dict(world.get("consistency")).get("redteam"))
          if isinstance(r, dict)]
    bodies = [b for b in _list(_dict(world.get("cosmology")).get("bodies"))
              if isinstance(b, dict)]
    pm = _dict(bodies[0].get("planet_map")) if bodies else {}
    choices = [c for c in _list(_dict(_dict(world.get("seed")).get("brief")).get("choices"))
               if isinstance(c, dict)]
    conflicts = (ws.card_conflicts(choices)
                 + ws.card_world_mismatch(choices, world))

    out = [
        {"id": "G1", "name": "自洽", "ok": rep.fatal == 0,
         "note": f"fatal {rep.fatal} ｜ 评分 {rep.score}",
         "cmd": "validate <world> --strict"},
        {"id": "G2", "name": "反常识度在推荐带", "ok": bool(wd) and lo <= wd.get("score", 0) <= hi,
         "note": f"{wd.get('score', '—')}/100（推荐 {lo}–{hi}）",
         "cmd": "validate <world>"},
        {"id": "G3", "name": "第一人称切片已定稿",
         "ok": bool(_text(sl.get("text"))) and _text(sl.get("status")) == "ok",
         "note": "narrative.slice.text + status=ok" if not sl else
                 f"status={sl.get('status', 'draft')}",
         "cmd": "slice <world> --strict"},
        {"id": "G4", "name": "红队全部结案",
         "ok": bool(rt) and all(_text(r.get("verdict")) not in ("", "open") for r in rt),
         "note": f"{len(rt)} 条，{sum(1 for r in rt if _text(r.get('verdict')) in ('', 'open'))} 条未结",
         "cmd": "redteam <world> --check"},
        {"id": "G5", "name": "行星地图可复算",
         "ok": bool(pm.get("hash")),
         "note": f"hash {pm.get('hash', '—')}",
         "cmd": "map <world> --check"},
        {"id": "G6", "name": "创作简报无互斥冲突",
         "ok": not conflicts,
         "note": ("；".join(conflicts[:3]) if conflicts
                  else (f"{len(choices)} 张卡已采纳" if choices else "未采纳任何选项卡")),
         "cmd": "options <world> --check"},
    ]
    return out


# ════════════════════════════════════════════════════════════════════
# 斧位判定
# ════════════════════════════════════════════════════════════════════

def axe_states(world: dict, rep=None) -> list:
    """
    逐斧判定，返回 [{n,cn,verb,state,missing,optional}]。

    state ∈ done | current | todo | skipped（可选斧未开且不阻塞）
    第一支未收斧的斧标 current；其后的斧标 todo。
    """
    if rep is None:
        rep = ws.validate(_copy_shallow(world))
    rows = []
    current_taken = False
    for a in AXES:
        miss = _missing(world, a["n"], rep)
        if not miss:
            state = "done"
        elif current_taken:
            state = "todo"
        elif a.get("optional"):
            state = "skipped"      # 可选斧未开：不阻塞，也不抢斧位
        else:
            state = "current"
            current_taken = True
        rows.append({"n": a["n"], "cn": a["cn"], "verb": a["verb"],
                     "state": state, "missing": miss,
                     "optional": bool(a.get("optional"))})
    if not current_taken:
        # 全收斧：斧位停在 7，交给门槛
        for r in rows:
            if r["n"] == 7:
                r["state"] = "current"
    return rows


def current_axe(rows: list) -> int:
    for r in rows:
        if r["state"] == "current":
            return r["n"]
    return 7


# ════════════════════════════════════════════════════════════════════
# 下一步命令
# ════════════════════════════════════════════════════════════════════

def next_commands(world: dict, rows: list, rep=None, world_path: str = "<world>") -> list:
    """
    按斧位给出**有序**的下一步命令。第一条永远是当前最该跑的那条。

    命令里的 `<world>` 会被替换成实际路径；rd 指针（<rd>）= 技能目录。
    """
    n = current_axe(rows)
    w = world_path
    out = []

    gs = gates(world, rep)
    cur = next((r for r in rows if r["n"] == n), None)
    if n == 7 and cur is not None and not cur["missing"] and all(g["ok"] for g in gs):
        # 七斧收齐、门槛全过：只剩出成品
        return [{"cmd": f'preview "{w}"', "why": "3D 页与生物视角"},
                {"cmd": f'export "{w}" --md 世界档案.md --json-out 审查报告.json',
                 "why": "档案 + 审查报告，交付物齐了"}]

    if n == 1:
        out.append({"cmd": f'patch "{w}" --set "seed.core_paradox=<一句话悖论>"',
                    "why": "先把「哪条常识是反的」写成可证伪的陈述句"})
        out.append({"cmd": "options --axe 1 --roll 2",
                    "why": "想不出画面时，抽两张选项卡当起点"})
    elif n == 2:
        out.append({"cmd": "options --axe 2 --roll 3",
                    "why": "天上有什么 / 怎么计时，这一斧的选项最多"})
        out.append({"cmd": f'patch "{w}" --set "cosmology.calendar.day_hours=..." --create',
                    "why": "历法必须能被轨道算出来，不能凭感觉填"})
        out.append({"cmd": f'validate "{w}" --brief',
                    "why": "补完一段就复检，别攒着"})
    elif n == 3:
        out.append({"cmd": "axioms --axe 3 --roll 3",
                    "why": "立律斧的积木全在物理域"})
        out.append({"cmd": f'patch "{w}" --set "physics.constants[0].why=<为什么改>"',
                    "why": "没有 why 的常数改动会被 L02 判成免费奇观"})
        out.append({"cmd": f'sweep "{w}" --list',
                    "why": "改完常数，看邻近值在哪崩——临界点本身就是素材"})
    elif n == 4:
        out.append({"cmd": "options --axe 4 --roll 3",
                    "why": "溶剂 / 键合 / 最硬的物质 / 有没有新元素"})
        out.append({"cmd": f'patch "{w}" --set "chemistry.solvent={{...}}" --create',
                    "why": "溶剂决定生命形态，也决定河流的黏度"})
    elif n == 5:
        out.append({"cmd": "options --axe 5 --roll 3",
                    "why": "能量货币 / 遗传载体 / 基座 / 色素"})
        out.append({"cmd": f'ca "{w}"',
                    "why": "把营养级编译成元胞自动机，看看它跑不跑得起来"})
    elif n == 6:
        out.append({"cmd": "options --axe 6 --roll 2",
                    "why": "计时 / 技术断点 / 社会形态 / 禁忌来源"})
        out.append({"cmd": f'patch "{w}" --set "civilization.exists=false"',
                    "why": "不想写文明就这样跳过，别让它卡住斧 7"})
    else:
        out.append({"cmd": f'entail "{w}"',
                    "why": "从已定设定推出「必然会出现什么」，再补 sky_phenomena"})
        out.append({"cmd": f'map "{w}" --run --write --yes',
                    "why": "地形 → 海平面 → 气候 → 河网 → 群系，一次出齐"})
        out.append({"cmd": f'slice "{w}" --strict',
                    "why": "两百字验尸：设定有没有落到人的感官层"})
        out.append({"cmd": f'redteam "{w}" --check',
                    "why": "让敌对物理学家提问，未结案不许交付"})
        out.append({"cmd": f'export "{w}" --md 世界档案.md --json-out 审查报告.json',
                    "why": "最后再出档案与 3D 页"})

    # 门槛补齐项追加在后面（不抢第一条）
    gs = gates(world, rep)
    for g in gs:
        if g["ok"]:
            continue
        cmd = g["cmd"].replace("<world>", w)
        if any(c["cmd"] == cmd for c in out):
            continue
        out.append({"cmd": cmd, "why": f"门槛 {g['id']} {g['name']} 未过：{g['note']}"})
    return out


# ════════════════════════════════════════════════════════════════════
# 汇总
# ════════════════════════════════════════════════════════════════════

def plan_report(world: dict, world_path: str = "<world>", rep=None) -> dict:
    if rep is None:
        rep = ws.validate(_copy_shallow(world))
    rows = axe_states(world, rep)
    n = current_axe(rows)
    axe = AXE_BY_N.get(n, AXES[-1])
    cur = next((r for r in rows if r["n"] == n), rows[-1])
    meta = _dict(world.get("meta"))
    return {
        "world": _text(meta.get("name")) or "未命名",
        "version": _text(meta.get("version")) or "—",
        "axe": n,
        "axe_name": axe["cn"],
        "axe_verb": axe["verb"],
        "score": rep.score,
        "fatal": rep.fatal,
        "warn": rep.warn,
        "states": rows,
        "missing": cur["missing"],
        "asks": axe["asks"],
        "searches": axe["searches"],
        "hint": axe["hint"],
        "writes": axe["writes"],
        "commands": next_commands(world, rows, rep, world_path),
        "gates": gates(world, rep),
        "eye": eye_hints(world),
    }


def eye_hints(world: dict) -> list:
    """1.1.4 抬头软提示：不进 G1–G6，避免 6/6 口径变化。"""
    cos = _dict(world.get("cosmology"))
    out = []
    if not _dict(cos.get("surface")).get("observer"):
        out.append("没有观测点 cosmology.surface.observer——sky 按赤道（0°,0°）算")
    if not _dict(cos.get("starfield")):
        out.append("没有登记星表 cosmology.starfield——sky 按 seed 生成默认 2000 颗，标「未登记」")
    if not _list_ok(cos.get("stars")) and cos.get("has_stars"):
        out.append("has_stars 为真但 stars 为空——抬头看不见任何光源")
    if out:
        out.append("补齐后跑一次 sky <world.json>，档案的第一屏就会变成星图")
    return out


def _list_ok(v) -> bool:
    return isinstance(v, list) and any(isinstance(x, dict) for x in v)


def brief_line(world: dict, world_path: str = "<world>", rep=None) -> str:
    """一行式结论：给 agent 的循环里用，省上下文。"""
    p = plan_report(world, world_path, rep)
    first = p["commands"][0]["cmd"] if p["commands"] else "—"
    miss = f"缺 {len(p['missing'])} 项" if p["missing"] else "本斧已收"
    return (f"{p['world']} v{p['version']} ｜ {p['score']}/100 ｜ "
            f"fatal {p['fatal']} ｜ 斧{p['axe']} {p['axe_name']}（{miss}）｜ "
            f"下一步：{first}")


def format_plan(p: dict, verbose: bool = True) -> str:
    """人读版：进度条 + 卡点 + 要问的问题 + 下一步命令。"""
    icon = {"done": "✓", "current": "▶", "todo": "·", "skipped": "…"}
    bar = "  ".join(f"{icon.get(r['state'], '?')}{r['n']} {r['cn']}" for r in p["states"])
    L = [
        f"【盘古 · 七斧进度】{p['world']} v{p['version']} ｜ "
        f"{p['score']}/100 ｜ fatal {p['fatal']}",
        "  " + bar,
        f"  当前：斧{p['axe']} {p['axe_name']}（{p['axe_verb']}）"
        f"  →  写 {('、'.join(p['writes']))}",
    ]
    if p["missing"]:
        L.append("")
        L.append("【还缺】")
        for m in p["missing"]:
            L.append(f"  · {m}")
    else:
        L.append("  ✓ 七斧已收齐（剩下的是交付门槛与出成品）"
                 if p["axe"] == 7 else "  ✓ 本斧已收（缺口为空）")

    if verbose:
        L.append("")
        L.append("【这一斧要回答】")
        for i, q in enumerate(p["asks"], 1):
            L.append(f"  {i}. {q}")
        if p["hint"]:
            L.append(f"  ↳ {p['hint']}")
        if p["searches"]:
            L.append("")
            L.append("【检索（锚定 / 证伪 / 取反）】")
            for s in p["searches"]:
                L.append(f"  {s}")

        gs = p["gates"]
        L.append("")
        L.append("【交付门槛】" + f" {sum(1 for g in gs if g['ok'])}/{len(gs)} 已过")
        for g in gs:
            L.append(f"  {'✓' if g['ok'] else '!'} {g['id']} {g['name']}｜{g['note']}")

    if p["commands"]:
        L.append("")
        L.append("【下一步】")
        for i, c in enumerate(p["commands"][:6], 1):
            L.append(f"  {i}. {c['cmd']}")
            L.append(f"     └ {c['why']}")

    if verbose and p.get("eye"):
        L.append("")
        L.append("【抬头（软提示，不计入门槛）】")
        for e in p["eye"]:
            L.append(f"  · {e}")
    return "\n".join(L)


def format_axe(world: dict, n: int, world_path: str = "<world>", rep=None) -> str:
    """只看一斧的细账（plan --axe N）：缺口、提问、检索、以及这一斧怎么收。"""
    if rep is None:
        rep = ws.validate(_copy_shallow(world))
    rows = axe_states(world, rep)
    row = next((r for r in rows if r["n"] == n), None)
    a = AXE_BY_N.get(n)
    if row is None or a is None:
        return f"没有斧 {n}（1–7）"
    state = {"done": "✓ 已收", "current": "▶ 当前", "todo": "· 未到",
             "skipped": "… 跳过（可选）"}.get(row["state"], "?")
    L = [f"【斧 {n} {a['cn']}（{a['verb']}）】{state} ｜ 写 "
         f"{'、'.join(a['writes'])}"]
    if row["missing"]:
        L.append("【还缺】")
        for m in row["missing"]:
            L.append(f"  · {m}")
    else:
        L.append("【还缺】无——这一斧可以收了")
    L.append("【要回答】")
    for i, q in enumerate(a["asks"], 1):
        L.append(f"  {i}. {q}")
    L.append(f"  ↳ {a['hint']}")
    L.append("【检索（锚定 / 证伪 / 取反）】")
    for s in a["searches"]:
        L.append(f"  {s}")
    if row["state"] == "current":
        L.append("【这一斧怎么收】")
        for c in next_commands(world, rows, rep, world_path)[:3]:
            L.append(f"  {c['cmd']}")
            L.append(f"     └ {c['why']}")
    elif row["state"] in ("todo", "skipped"):
        L.append(f"【提示】还没到这一斧；先跑 plan \"{world_path}\" 看当前卡在哪")
    else:
        L.append("【提示】这一斧已收，别回头改——改了下游要重跑")
    return "\n".join(L)
