# -*- coding: utf-8 -*-
"""
盘古 · 交付体检（1.1.3 大条 D，1.1.4 加 D9，1.1.5 加 D10/D11）
================================================================
一条命令跑完十一项体检，给出「能不能交」的单一结论。

设计约束
--------
- **只读**：不写 world.json、不出图、不回写任何东西。
- **不重复实现**：能调引擎就调引擎（自洽走 world_schema，地图走 mapgen，
  演化走 ca_engine，推论走 entailment），本模块只负责「编排 + 判定 + 排序」。
- **单项失败不中断**：某一项抛异常就记成 skip 并附原因，其余照常跑完。
- **结论唯一**：hard 项全过 = 可交付；soft 项（反常识度、选项卡）只提示，不拦。
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import world_schema as ws  # noqa: E402
import entailment as en  # noqa: E402
import options_lib as ol  # noqa: E402

HARD = "hard"   # 不过就不许交付
SOFT = "soft"   # 不拦，但提示
SKIP = "skip"   # 这段还没写 / 还没跑

WEIRD_BAND = getattr(ws, "WEIRD_BAND", (40, 70))


def _item(iid, name, level, ok, brief, cmd="", hint=""):
    return {"id": iid, "name": name, "level": level, "ok": ok,
            "brief": brief, "cmd": cmd, "hint": hint}


def _slice_item(world: dict, rep) -> dict:
    sl = ws._get(world, "narrative", "slice", default=None)
    cmd = "slice <world> --prompt"
    if not isinstance(sl, dict) or not str(sl.get("text") or "").strip():
        return _item("D3", "切片", HARD, False, "未定义 narrative.slice.text", cmd,
                     "写一段 180–260 字的「居民的一天」，附 cites 与 status: ok")
    text = str(sl.get("text") or "")
    n = ws._count_cjk(text)
    status = str(sl.get("status") or "draft")
    by_id = {c.id: c for c in rep.checks}
    bad = [cid for cid in ("N04", "N05", "N06")
           if (by_id.get(cid) is not None
               and by_id[cid].verdict in ("warn", "fatal"))]
    ok = (180 <= n <= 260) and status == "ok" and not bad
    brief = f"{n} 字 ｜ status={status}"
    if bad:
        brief += f" ｜ 不过：{'、'.join(bad)}"
    return _item("D3", "切片", HARD, ok, brief, cmd,
                 "字数 180–260、status=ok、至少两条 sky_phenomena、时序要对上历法")


def _redteam_item(world: dict) -> dict:
    rows = [r for r in (ws._get(world, "consistency", "redteam", default=[]) or [])
            if isinstance(r, dict)]
    cmd = "redteam <world> --check"
    if not rows:
        return _item("D4", "红队", HARD, False, "还没有质疑", "redteam <world> --write",
                     "先让敌对物理学家提 5 个问题，再逐条结案")
    opens = [r for r in rows if str(r.get("verdict") or "open") == "open"]
    bad_target = [r for r in rows if not ws.resolve_path(world, r.get("target"))[0]]
    ok = len(rows) >= 5 and not opens and not bad_target
    brief = f"{len(rows)} 条 ｜ 未结 {len(opens)} ｜ 靶点失效 {len(bad_target)}"
    return _item("D4", "红队", HARD, ok, brief, cmd,
                 "未结案的质疑就是没还的债；5 条是下限，不是指标")


def _map_item(world: dict, fast: bool) -> dict:
    _ok, pm, _why = ws.resolve_path(world, "cosmology.bodies[0].planet_map")
    if not _ok or not isinstance(pm, dict) or not pm.get("hash"):
        return _item("D5", "地图", SKIP, None, "还没有地图哈希（未跑过 map）",
                     "map <world> --run --write --yes",
                     "地图不是装饰：海平面是水量解出来的，群系来自设定")
    if fast:
        return _item("D5", "地图", SKIP, None,
                     f"hash {str(pm.get('hash'))[:8]}（--fast 未复算）", "map <world> --check")
    try:
        import mapgen
        got = mapgen.check(world)
    except Exception as e:  # noqa: BLE001
        return _item("D5", "地图", SKIP, None, f"复算失败：{type(e).__name__}", "map <world> --check")
    bad = [c for c in got.get("checks") or [] if not c.get("ok")]
    ok = bool(got.get("ok")) and not bad
    brief = f"hash {str(got.get('hash_a'))[:8]} ｜ 体检 {len(got.get('checks') or [])} 项"
    if bad or got.get("diffs"):
        brief += f" ｜ 异常 {len(bad) + len(got.get('diffs') or [])}"
    return _item("D5", "地图", HARD, ok, brief, "map <world> --check",
                 "同 seed 复算不一致 = 地图被手改过，或换了 seed 没重跑")


def _ca_item(world: dict, fast: bool) -> dict:
    evo = ws._get(world, "biology", "evolution", default=None)
    if not isinstance(evo, dict):
        return _item("D6", "演化", SKIP, None, "没有声明 biology.evolution", "ca <world>",
                     "生态不是摆设：规则必须带 source 指回设定")
    if not isinstance(evo.get("summary"), dict):
        return _item("D6", "演化", SKIP, None, "还没有 summary（未真跑过）",
                     "ca <world> --run --write --yes")
    if fast:
        return _item("D6", "演化", SKIP, None, "有 summary（--fast 未复算）", "ca <world> --check")
    try:
        import ca_engine as ca
        res = ca.check_evolution(evo, world)
    except Exception as e:  # noqa: BLE001
        return _item("D6", "演化", SKIP, None, f"复算失败：{type(e).__name__}", "ca <world> --check")
    diffs = res.get("diffs") or []
    return _item("D6", "演化", HARD, not diffs,
                 f"复算一致" if not diffs else f"{len(diffs)} 处与声明不符",
                 "ca <world> --check",
                 "summary 里的数字必须是跑出来的，改参数就重跑 --write")


def _entail_item(world: dict) -> dict:
    rows = en.derive(world)
    marks = en.existing_marks(world)
    stale = en.stale_marks(world, rows)
    if not marks:
        return _item("D7", "推论", SOFT, True,
                     f"命中 {len(rows)} 条，未回写", "entail <world> --write --yes",
                     "天象最好由设定推出来，而不是编出来")
    ok = not stale
    brief = f"已回写 {len(marks)} 条 ｜ 失效 {len(stale)} 条"
    return _item("D7", "推论", HARD, ok, brief, "entail <world> --check",
                 "改了设定但旧天象还在——它会继续冒充事实")


def _cards_item(world: dict) -> dict:
    cards, _ = ol.load_cards(os.path.dirname(HERE))
    choices = ((ws._get(world, "seed", "brief", default={}) or {}).get("choices") or [])
    choices = [c for c in choices if isinstance(c, dict)]
    if not choices:
        return _item("D8", "选项卡", SOFT, True, "未采纳任何卡（可选）",
                     "options --axe 1", "先答几问再动笔，比边写边想省事")
    conflicts = ws.card_conflicts(choices)
    rest = ol.uncovered(cards, choices)
    ok = not conflicts
    brief = f"{len(choices)} 张卡 ｜ 未答 {len(rest)}/{len(cards)}"
    if conflicts:
        brief += " ｜ 互斥 " + "；".join(conflicts)
    return _item("D8", "选项卡", HARD if conflicts else SOFT, ok, brief,
                 "options <world> --check", "互斥的卡会让世界两头下注")


def _bench_item(fast: bool = False) -> dict:
    """D9 基准：引擎能不能对地球对上表。与世界无关，软门槛。"""
    if fast:
        return _item("D9", "基准", SKIP, None, "引擎基准未复算（--fast）",
                     "benchmark earth", "跑一次才知道引擎离地球有多远")
    try:
        import benchmark
        b = benchmark.run()
    except Exception as e:  # noqa: BLE001 —— 基准挂了不该拖垮交付体检
        return _item("D9", "基准", SOFT, False, f"跑不起来：{type(e).__name__}",
                     "benchmark earth", "基准都跑不动，说明引擎有回归")
    t = next((r for r in b["rows"] if r["id"] == "B01"), {})
    return _item("D9", "基准", SOFT, bool(b["ok"]),
                 f"{b['passed']}/{b['total']} 条对表 ｜ 纬向温度 RMSE {t.get('got', '?')} K",
                 "benchmark earth",
                 "对不上地球的模型，只能叫美术")


def _ledger_item(world: dict) -> dict:
    """D10 守恒：账本配不平，说明某条声明与模型打架。"""
    try:
        import conservation
        d = conservation.ledger(world)
    except Exception as e:  # noqa: BLE001
        return _item("D10", "守恒", SOFT, False, f"跑不起来：{type(e).__name__}",
                     "ledger <world>", "账本挂了，说明引擎有回归")
    if not d["scored"]:
        return _item("D10", "守恒", SKIP, None, "可算的账不足（缺半径/大气/水量）",
                     "ledger <world>", "地图与大气补齐之后才有账可算")
    bad = [r for r in d["rows"] if r["status"] == "warn"]
    brief = f"{d['scored']} 本账 ｜ 不平 {len(bad)}"
    if bad:
        brief += " ｜ " + "、".join(f"{r['id']} {r['residual']:+.0%}" for r in bad[:3])
    if d.get("explained"):
        brief += f"（{'、'.join(d['explained'])} 为声明压过模型）"
    return _item("D10", "守恒", SOFT, not d.get("unexplained"), brief, "ledger <world>",
                 "常见的不平是「声明温室与大气成分打架」——改写法，或改成成分算出来的值")


def _certify_item(world: dict, fast: bool) -> dict:
    """D11 适用域：多少结论是算出来的。"""
    if fast:
        return _item("D11", "适用域", SKIP, None, "--fast 未评估",
                     "certify <world>", "覆盖率是「这世界能不能当定量模型」的粗判")
    try:
        import certify
        d = certify.run(world, bench=False)
    except Exception as e:  # noqa: BLE001
        return _item("D11", "适用域", SOFT, False, f"跑不起来：{type(e).__name__}",
                     "certify <world>", "适用域挂了，说明推演层有回归")
    bk = d["by_kind"]
    return _item("D11", "适用域", SOFT, d["ok"],
                 f"覆盖率 {d['coverage']:.0%} ｜ 算 {len(bk['computed'])}"
                 f" / 半算 {len(bk['mixed'])} / 声明 {len(bk['declared'])}",
                 "certify <world>",
                 "覆盖率低于 30% 时，这个世界的数字大多还是「拍的」，别当模型用")


def run(world: dict, path: str = "", fast: bool = False) -> dict:
    """跑完九项体检。返回 {items, ok, hard_fail, soft_warn, conclusion, ...}。"""
    rep = ws.validate(world)
    wd = ws.weirdness(world)
    items = [_item("D1", "自洽", HARD, rep.fatal == 0,
                   f"{rep.score}/100 ｜ fatal {rep.fatal} ｜ warn {rep.warn}",
                   "validate <world> --strict", "有致命项就是「这个世界会崩」")]
    lo, hi = WEIRD_BAND
    items.append(_item("D2", "反常识度", SOFT, lo <= wd["score"] <= hi,
                       f"{wd['score']}/100（推荐 {lo}–{hi}）{wd['label']}",
                       "axioms --roll 3 / options --roll 2",
                       "低于 40 是地球换皮，高于 70 读者会放弃"))
    items.append(_slice_item(world, rep))
    items.append(_redteam_item(world))
    items.append(_map_item(world, fast))
    items.append(_ca_item(world, fast))
    items.append(_entail_item(world))
    items.append(_cards_item(world))
    items.append(_bench_item(fast))
    items.append(_ledger_item(world))
    items.append(_certify_item(world, fast))

    hard_fail = [i for i in items if i["level"] == HARD and i["ok"] is False]
    soft_warn = [i for i in items if i["level"] == SOFT and i["ok"] is False]
    skipped = [i for i in items if i["level"] == SKIP]
    return {
        "world": ws._get(world, "meta", "name", default=""),
        "id": ws._get(world, "meta", "id", default=""),
        "version": ws._get(world, "meta", "version", default=""),
        "path": path,
        "score": rep.score, "fatal": rep.fatal, "warn": rep.warn,
        "weirdness": wd["score"],
        "items": items,
        "hard_fail": [i["id"] for i in hard_fail],
        "soft_warn": [i["id"] for i in soft_warn],
        "skipped": [i["id"] for i in skipped],
        "ok": not hard_fail,
        "conclusion": ("可交付" if not hard_fail else f"不可交付（{len(hard_fail)} 项硬门槛未过）"),
    }


def format_report(res: dict) -> str:
    L = []
    L.append(f"【盘古 · 交付体检】{res['world'] or '世界'} {res['version']}"
             f" ｜ {res['score']}/100 ｜ fatal {res['fatal']}")
    L.append("-" * 58)
    for it in res["items"]:
        icon = ("✓" if it["ok"] else ("✗" if it["level"] == HARD else "!")) \
            if it["ok"] is not None else "·"
        L.append(f"  {icon} {it['id']} {it['name']}  {it['brief']}")
    L.append("-" * 58)
    hard = [i for i in res["items"] if i["id"] in res["hard_fail"]]
    soft = [i for i in res["items"] if i["id"] in res["soft_warn"]]
    if hard:
        L.append("【先修这些，按顺序】")
        for n, it in enumerate(hard, 1):
            L.append(f"  {n}. {it['id']} {it['name']}：{it['hint']}")
            if it["cmd"]:
                L.append(f"     {it['cmd']}")
    if soft:
        L.append("【可以更好】")
        for it in soft:
            L.append(f"  · {it['id']} {it['name']}：{it['hint']}")
    if res["skipped"]:
        L.append("【还没跑】" + "、".join(
            f"{i['id']} {i['name']}" for i in res["items"] if i["id"] in res["skipped"]))
    L.append("-" * 58)
    L.append(f"  结论：{res['conclusion']}")
    return "\n".join(L)
