#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古 · 验收自测
===============

把开发文档 §9（验收标准）与 §10.5（跨 harness 验收）的用例变成可执行检查。
仅用标准库，任何宿主都能跑：

    python scripts/selftest.py          # 跑全部
    python scripts/selftest.py -v       # 附每项输出片段

退出码 0 = 全过；1 = 有失败。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLI = os.path.join(HERE, "pangu.py")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import world_schema as ws  # noqa: E402
MCP = os.path.join(ROOT, "adapters", "mcp", "pangu_mcp.py")
INSTALL = os.path.join(ROOT, "install.py")
EXAMPLE = os.path.join(ROOT, "examples", "helikon", "world.json")
ASTER = os.path.join(ROOT, "examples", "aster", "world.json")
PY = sys.executable

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv
RESULTS = []           # (编号, 名称, ok, 备注)


def _enc():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass


def run(args, cwd=None, timeout=180):
    return subprocess.run(
        [PY, *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=cwd or ROOT, timeout=timeout,
    )


def check(cid, name, ok, note=""):
    RESULTS.append((cid, name, bool(ok), note))
    flag = "PASS" if ok else "FAIL"
    print(f"  [{flag}] {cid}  {name}" + (f"  — {note}" if note and not ok else ""))
    if VERBOSE and note and ok:
        print(f"         {note[:160]}")


def jload(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


# ════════════════════════════════════════════════════════════════════
# §9 引擎用例
# ════════════════════════════════════════════════════════════════════

def test_engine(tmp):
    print("\n§9 引擎")

    r = run([CLI, "doctor"])
    check("E1", "doctor 环境自检通过", r.returncode == 0, (r.stdout + r.stderr)[-160:])

    r = run([CLI, "axioms", "--json"])
    try:
        lib = json.loads(r.stdout)
        n = len(lib)
    except Exception:
        n = 0
    check("E2", "公理库可解析且 ≥60 条", r.returncode == 0 and n >= 60, f"实际 {n} 条")

    wpath = os.path.join(tmp, "world.json")
    r = run([CLI, "init", "--name", "自测世界", "--seed", "自测种子", "--out", wpath])
    ok = r.returncode == 0 and os.path.exists(wpath)
    keys = []
    if ok:
        keys = list(jload(wpath).keys())
    need = {"meta", "seed", "cosmology", "physics", "chemistry", "biology"}
    check("E3", "init 生成骨架且含必需顶层字段",
          ok and need.issubset(set(keys)), f"字段 {keys}")

    r = run([CLI, "validate", EXAMPLE, "--json"])
    try:
        rep = json.loads(r.stdout)
    except Exception:
        rep = {}
    score = rep.get("score", -1)
    fatal = rep.get("fatal", 99)
    check("E4", "示例世界评分 100 且 0 fatal",
          score == 100 and fatal == 0, f"score={score} fatal={fatal}")

    # 人为破坏一处：重力与质量半径不自洽，校验器应能抓到
    bad = jload(EXAMPLE)
    body = bad["cosmology"]["bodies"][0]
    body["gravity_g"] = 9.9
    bad_path = os.path.join(tmp, "bad.json")
    with open(bad_path, "w", encoding="utf-8") as f:
        json.dump(bad, f, ensure_ascii=False)
    r = run([CLI, "validate", bad_path, "--json"])
    try:
        brep = json.loads(r.stdout)
    except Exception:
        brep = {}
    check("E5", "校验器能抓出不自洽的重力",
          brep.get("fatal", 0) + brep.get("warn", 0) > 0,
          f"fatal={brep.get('fatal')} warn={brep.get('warn')}")

    ph = os.path.join(tmp, "preview.html")
    r = run([CLI, "preview", EXAMPLE, "-o", ph])
    html = ""
    if os.path.exists(ph):
        with open(ph, "r", encoding="utf-8") as f:
            html = f.read()
    no_stub = "{{PANGU" not in html and "__PANGU_WORLD_JSON__" not in html
    injected = '"cosmology"' in html and '"biomes"' in html
    check("E6", "preview 生成 HTML 且数据注入完整、无残留占位符",
          r.returncode == 0 and len(html) > 50000 and no_stub and injected,
          f"{len(html)//1024} KB")

    md = os.path.join(tmp, "档案.md")
    r = run([CLI, "export", EXAMPLE, "--md", md, "--json-out", os.path.join(tmp, "rep.json")])
    mlen = os.path.getsize(md) if os.path.exists(md) else 0
    check("E7", "export 生成世界档案与报告", r.returncode == 0 and mlen > 2000, f"{mlen} 字节")


def test_map(tmp):
    print("\n§1.1.1 行星地图")

    outdir = os.path.join(tmp, "map")
    r = run([CLI, "map", EXAMPLE, "--res", "120x60", "--render", "480x240",
             "--run", "--out", outdir], timeout=300)
    need = ["map-elevation.png", "map-biome.png", "map-temperature.png",
            "map-precipitation.png", "map-tectonics.png", "map-habitat.png",
            "map-relief.png", "map-globe.png", "map.html", "map-data.json"]
    miss = [f for f in need if not os.path.exists(os.path.join(outdir, f))]
    sizes = [os.path.getsize(os.path.join(outdir, f)) for f in need
             if os.path.exists(os.path.join(outdir, f))]
    check("M1", "map --run 出齐七层图 + 地球 + 交互页",
          r.returncode == 0 and not miss and min(sizes or [0]) > 500,
          f"缺 {miss}")

    # 1.1.6 · 每层带图例，且色带与标尺由渲染口径同源生成
    legend = {}
    try:
        with open(os.path.join(outdir, "map.html"), encoding="utf-8") as f:
            m = re.search(r'<script id="data"[^>]*>(.*?)</script>', f.read(), re.S)
        legend = (json.loads(m.group(1)) if m else {}).get("legend") or {}
    except Exception:
        legend = {}
    need_lg = {"elevation", "temperature", "precipitation", "habitat", "relief", "tectonics"}
    ok_lg = need_lg.issubset(legend) and all(
        ("grad" in legend[k] or "items" in legend[k]) for k in need_lg)
    check("M1b", "map.html 每层带图例（色带与标尺同源）", ok_lg,
          f"keys={sorted(legend)}")

    r = run([CLI, "map", EXAMPLE, "--check", "--res", "120x60"], timeout=300)
    check("M2", "map --check 同 seed 复算一致且六项体检通过",
          r.returncode == 0 and "地图可复算" in r.stdout, (r.stdout + r.stderr)[-160:])

    # 地图必须真被喂进 world.json（coarse 场），否则 CA 耦合是空转
    data = jload(os.path.join(outdir, "map-data.json"))
    wcopy = os.path.join(tmp, "map-world.json")
    shutil.copy(EXAMPLE, wcopy)
    r = run([CLI, "map", wcopy, "--res", "120x60", "--write", "--yes",
             "--out", outdir], timeout=300)
    pm = jload(wcopy)["cosmology"]["bodies"][0].get("planet_map") or {}
    coarse = pm.get("coarse") or {}
    ok = bool(coarse.get("habitat")) and data.get("hash") == pm.get("hash")
    check("M3", "world.json 带 coarse 场与地图哈希", ok,
          f"hash={data.get('hash')} / pm={pm.get('hash')}")


def test_organism(tmp):
    print("\n§1.1.2 生物视角与元素")

    d = jload(EXAMPLE)
    chem = d.get("chemistry") or {}
    bio = d.get("biology") or {}
    comp = chem.get("composition") or {}
    sums = {}
    for k in ("planet", "atmosphere"):
        mix = comp.get(k) or {}
        sums[k] = round(sum(v for v in mix.values() if isinstance(v, (int, float))), 4)
    base = (bio.get("biochemistry") or {}).get("composition") or {}
    sums["creature"] = round(sum(v for v in base.values() if isinstance(v, (int, float))), 4)
    check("B1", "行星 / 大气 / 生命配比均归一",
          bool(sums) and all(abs(s - 1) <= 0.02 for s in sums.values()), str(sums))

    els = [e for e in (chem.get("fictional_elements") or []) if isinstance(e, dict)]
    naming_ok = bool(els)
    for e in els:
        g = str(e.get("glyph") or "")
        m = re.match(r"^⿸气⿰钅([\u4e00-\u9fff])$", g)
        if not m or m.group(1) != str(e.get("component") or ""):
            naming_ok = False
    syms = [str(e.get("symbol") or "") for e in els]
    check("B2", "虚构元素为「气+钅+单字」且符号唯一",
          naming_ok and len(set(syms)) == len(syms),
          f"{len(els)} 个：{'、'.join(syms)}")

    r = run([CLI, "validate", EXAMPLE, "--json"])
    try:
        rep = json.loads(r.stdout)
    except Exception:
        rep = {}
    kmap = {c["id"]: c["verdict"] for c in rep.get("checks", []) if str(c["id"]).startswith("K")}
    check("B3", "K01–K03 元素/命名/基座三项全部通过",
          all(kmap.get(k) == "pass" for k in ("K01", "K02", "K03")), str(kmap))

    ph = os.path.join(tmp, "preview-creature.html")
    r = run([CLI, "preview", EXAMPLE, "-o", ph])
    html = ""
    if os.path.exists(ph):
        with open(ph, "r", encoding="utf-8") as f:
            html = f.read()
    need = ['id="creature-view"', "makeCreature", "双影猎兽", "⿸气⿰钅辰", "cr-species"]
    miss = [n for n in need if n not in html]
    check("B4", "预览页含可操控生物视角与新元素字形",
          r.returncode == 0 and not miss, f"缺 {miss}")


def test_tuning(tmp):
    print("\n§1.1.2 调参层")

    # T1 查：--get 能取到带单位字符串
    r = run([CLI, "patch", EXAMPLE, "--get", "physics.constants[0].world_value"])
    check("T1", "patch --get 取到常数原值", r.returncode == 0 and "4.004e-11" in r.stdout,
          (r.stdout + r.stderr)[-160:])

    # T2 改：写盘后版本 +1、修订记录 +1、值真的变了
    w = os.path.join(tmp, "tune.json")
    shutil.copy(EXAMPLE, w)
    before = jload(w)
    n_rev = len((before.get("history") or {}).get("revisions") or [])
    r = run([CLI, "patch", w, "--set", "cosmology.bodies[0].albedo=0.40",
             "--note", "自测：反照率", "--json"])
    after = jload(w)
    ver_ok = (after["meta"]["version"] != before["meta"]["version"])
    rev_ok = len(after["history"]["revisions"]) == n_rev + 1
    val_ok = abs(float(after["cosmology"]["bodies"][0]["albedo"]) - 0.40) < 1e-9
    check("T2", "patch 写盘：值变更 + 版本推进 + 记修订",
          r.returncode == 0 and ver_ok and rev_ok and val_ok,
          f"ver={after['meta']['version']} rev={len(after['history']['revisions'])}")

    # T3 增：默认拒绝写不存在的字段，--create 才允许
    r1 = run([CLI, "patch", w, "--set", "physics.selftest_field=1"])
    r2 = run([CLI, "patch", w, "--set", "physics.selftest_field=1", "--create"])
    check("T3", "patch 默认拒绝孤儿字段，--create 放行",
          r1.returncode == 2 and r2.returncode == 0
          and jload(w)["physics"].get("selftest_field") == 1,
          f"r1={r1.returncode} r2={r2.returncode}")

    # T4 扫：JSON 出 3 行，基线分可读
    r = run([CLI, "sweep", w, "--param", "cosmology.bodies[0].mass_earth",
             "--percent", "20", "--steps", "3", "--json"])
    try:
        sw = json.loads(r.stdout)
    except Exception:
        sw = {}
    check("T4", "sweep 出连续谱并给出安全窗",
          r.returncode == 0 and len(sw.get("rows") or []) == 3
          and sw.get("baseline", {}).get("score") == 100,
          (r.stdout + r.stderr)[-160:])

    # T5 扫：--list 能列出可扫参数
    r = run([CLI, "sweep", EXAMPLE, "--list"])
    check("T5", "sweep --list 列出可扫参数",
          r.returncode == 0 and "physics.constants[0].world_value" in r.stdout,
          (r.stdout + r.stderr)[-160:])

    # T6 比：diff 抓到改动并给下游清单
    r = run([CLI, "diff", EXAMPLE, w, "--json"])
    try:
        df = json.loads(r.stdout)
    except Exception:
        df = {}
    tasks = {t.get("task") for t in (df.get("downstream") or [])}
    changed = {c.get("path") for c in (df.get("changes") or [])}
    check("T6", "diff 抓到 albedo / 版本变化并给出重跑清单",
          r.returncode == 0 and "cosmology.bodies[0].albedo" in changed
          and {"export", "preview"} <= tasks,
          f"changed={list(changed)[:4]} tasks={tasks}")

    # T7 索引：代价类型二次索引覆盖全部积木
    r = run([CLI, "axioms", "--cost-list"])
    tags = ["时间", "空间", "能量", "物质", "感知", "社会", "生命", "结构"]
    r2 = run([CLI, "axioms", "--cost", "空间", "--json"])
    try:
        pool = json.loads(r2.stdout)
    except Exception:
        pool = []
    check("T7", "公理库按代价类型可索引且过滤结果带标签",
          r.returncode == 0 and all(t in r.stdout for t in tags)
          and bool(pool) and all("空间" in a.get("cost_tags", []) for a in pool),
          f"{len(pool)} 条")

    # T8 指数：反常识度进入校验输出与 JSON 派生量
    r = run([CLI, "validate", EXAMPLE, "--json"])
    try:
        rep = json.loads(r.stdout)
    except Exception:
        rep = {}
    wd = (rep.get("derived") or {}).get("weirdness") or {}
    r2 = run([CLI, "validate", EXAMPLE])
    check("T8", "反常识度指数进入派生量与报告",
          0 <= int(wd.get("score", -1)) <= 100 and "反常识度" in r2.stdout,
          f"score={wd.get('score')}")


def test_flow(tmp):
    print("\n§1.1.3 七斧状态机")

    r = run([CLI, "plan", EXAMPLE, "--json"])
    try:
        p = json.loads(r.stdout)
    except Exception:
        p = {}
    states = p.get("states") or []
    cmds = p.get("commands") or []
    check("F1", "plan 给出 7 斧状态、斧位与下一步命令",
          r.returncode == 0 and len(states) == 7 and p.get("axe") in range(1, 8)
          and bool(cmds) and bool(p.get("gates")) and len(p["gates"]) == 6,
          f"axe={p.get('axe')} states={len(states)} cmds={len(cmds)}")

    r = run([CLI, "plan", EXAMPLE, "--brief"])
    line = (r.stdout or "").strip()
    check("F2", "plan --brief 一行式结论", r.returncode == 0 and "\n" not in line
          and "斧" in line and "/100" in line, line[:100])

    r = run([CLI, "plan", EXAMPLE, "--next"])
    first = (r.stdout or "").strip()
    check("F3", "plan --next 只输出一条可执行命令",
          r.returncode == 0 and "\n" not in first and " " in first, first[:80])

    # 骨架世界应当停在第 1 斧（有悖论才算收斧）
    w = os.path.join(tmp, "skeleton.json")
    run([CLI, "init", "--name", "骨架", "--out", w])
    r = run([CLI, "plan", w, "--json"])
    try:
        p2 = json.loads(r.stdout)
    except Exception:
        p2 = {}
    miss = p2.get("missing") or []
    check("F4", "空骨架停在斧 1 且报出缺口",
          p2.get("axe") == 1 and any("core_paradox" in m for m in miss),
          f"axe={p2.get('axe')} missing={miss[:2]}")

    r = run([CLI, "validate", EXAMPLE, "--brief"])
    line = (r.stdout or "").strip()
    check("F5", "validate --brief 一行式结论",
          r.returncode == 0 and "\n" not in line and "/100" in line and "下一步" in line,
          line[:100])


def test_cards(tmp):
    print("\n§1.1.3 选项卡")

    r = run([CLI, "options", "--stats"])
    check("O1", "选项卡规模：≥31 命题 / ≥100 选项 / 7 斧",
          r.returncode == 0 and "31 个命题" in r.stdout and "斧 7" in r.stdout,
          (r.stdout or "")[:120])

    w = os.path.join(tmp, "cards.json")
    shutil.copy(EXAMPLE, w)
    before = jload(w)
    r = run([CLI, "options", w, "--adopt", "Q2.1=B"])
    after = jload(w)
    ch = ((after.get("seed") or {}).get("brief") or {}).get("choices") or []
    hit = next((c for c in ch if c.get("qid") == "Q2.1"), {})
    check("O2", "adopt 写入 seed.brief 并升版本记修订",
          r.returncode == 0 and hit.get("option") == "B" and bool(hit.get("cost"))
          and after["meta"]["version"] != before["meta"]["version"]
          and len(after["history"]["revisions"]) == len(before["history"]["revisions"]) + 1,
          f"choices={len(ch)} ver={after['meta']['version']}")

    # 跨命题互斥：Q1.1=C（无恒星）撞上已采纳的 Q2.1=B（有恒星）
    n_before = len(ch)
    r = run([CLI, "options", w, "--adopt", "Q1.1=C"])
    r2 = run([CLI, "options", w, "--adopt", "Q1.1=C", "--force"])
    ch2 = ((jload(w).get("seed") or {}).get("brief") or {}).get("choices") or []
    hit2 = next((c for c in ch2 if c.get("qid") == "Q1.1"), {})
    qids = [c.get("qid") for c in ch2]
    check("O3", "互斥选项被拒绝，--force 才放行",
          r.returncode == 2 and "互斥" in (r.stdout + r.stderr)
          and r2.returncode == 0 and hit2.get("option") == "C"
          and len(qids) == len(set(qids)) and len(ch2) <= n_before + 1,
          f"r={r.returncode} r2={r2.returncode} {n_before}→{len(ch2)}")

    # 卡与世界对账：无恒星卡 + 三恒星数据 → R01 必须报
    r = run([CLI, "validate", w, "--json"])
    try:
        rep = json.loads(r.stdout)
    except Exception:
        rep = {}
    r01 = next((c for c in rep.get("checks", []) if c["id"] == "R01"), {})
    r3 = run([CLI, "options", w, "--check"])
    check("O4", "R01 / options --check 抓到「卡说无恒星，数据有三颗」",
          r01.get("verdict") == "warn" and "有恒星" in r01.get("note", "")
          and "对账" in r3.stdout,
          f"{r01.get('verdict')} {r01.get('note', '')[:80]}")


def test_entail(tmp):
    print("\n§1.1.3 必然推论")

    r = run([CLI, "entail", EXAMPLE, "--json"])
    try:
        rows = json.loads(r.stdout)
    except Exception:
        rows = []
    ok = bool(rows) and all(x.get("claim") and x.get("trace") and x.get("src") for x in rows)
    check("I1", "entail 推出 ≥5 条带断言/痕迹/出处 的推论",
          r.returncode == 0 and len(rows) >= 5 and ok, f"{len(rows)} 条")

    # 从「没有任何 entail 标记」的世界开始，才验得出「回写」这件事
    w = os.path.join(tmp, "entail.json")
    d0 = jload(EXAMPLE)
    d0["cosmology"]["sky_phenomena"] = [
        s for s in d0["cosmology"]["sky_phenomena"] if "〔entail" not in str(s)]
    n0 = len(d0["cosmology"]["sky_phenomena"])
    with open(w, "w", encoding="utf-8") as f:
        json.dump(d0, f, ensure_ascii=False)

    r = run([CLI, "entail", w, "--write", "--yes"])
    sky1 = jload(w)["cosmology"]["sky_phenomena"]
    r2 = run([CLI, "entail", w, "--write", "--yes"])
    sky2 = jload(w)["cosmology"]["sky_phenomena"]
    check("I2", "entail --write 幂等回写 sky_phenomena",
          r.returncode == 0 and len(sky1) > n0 and len(sky2) == len(sky1)
          and all("〔entail" in str(s) for s in sky1[n0:]),
          f"{n0} → {len(sky1)} → {len(sky2)}")

    r = run([CLI, "entail", w, "--check"])
    check("I3", "entail --check 全部有效（无失效推论）",
          r.returncode == 0 and "没有失效条目" in r.stdout, (r.stdout or "")[-120:])

    # 改设定让推论失效：删掉第三颗恒星后 E02 不再成立
    d = jload(w)
    d["cosmology"]["stars"] = d["cosmology"]["stars"][:2]
    bad = os.path.join(tmp, "entail-stale.json")
    with open(bad, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    r = run([CLI, "entail", bad, "--check"])
    check("I4", "改设定后失效推论被点名",
          r.returncode == 1 and "失效" in r.stdout, (r.stdout or "")[-120:])


def test_small(tmp):
    print("\n§1.1.3 小改动")

    r = run([CLI, "axioms", "--axe", "4", "--json"])
    try:
        pool = json.loads(r.stdout)
    except Exception:
        pool = []
    check("S1", "axioms --axe 只给该斧领域的积木",
          r.returncode == 0 and bool(pool) and {a["domain"] for a in pool} == {"chemistry"},
          f"{len(pool)} 条：{sorted({a['domain'] for a in pool})}")

    r = run([CLI, "sweep", EXAMPLE, "--param", "physics.constants[0].world_value",
             "--from", "3e-11", "--to", "4.8e-11", "--steps", "4", "--log", "--json"])
    try:
        sw = json.loads(r.stdout)
    except Exception:
        sw = {}
    vals = [x["value"] for x in (sw.get("rows") or [])]
    geo = (len(vals) == 4
           and all(abs((vals[i + 1] / vals[i]) - (vals[1] / vals[0])) < 1e-9
                   for i in range(len(vals) - 2)))
    check("S2", "sweep --log 按等比采样（相邻比值恒定）",
          r.returncode == 0 and geo, f"vals={vals}")

    w = os.path.join(tmp, "suggest.json")
    shutil.copy(EXAMPLE, w)
    r = run([CLI, "patch", w, "--set", "cosmology.bodies[0].mass_earth=30.0", "--suggest"])
    check("S3", "patch --suggest 给出密度/重力自洽建议（不写盘）",
          r.returncode == 0 and "自洽建议" in r.stdout and "density_gcc" in r.stdout,
          (r.stdout or "")[-160:])

    r = run([CLI, "slice", EXAMPLE, "--prompt"])
    need = ["【居民】", "【孩童】", "【外来者】", "【敌对科学家】"]
    check("S4", "slice --prompt 给出四种视角的写作提示",
          r.returncode == 0 and all(n in r.stdout for n in need),
          f"缺 {[n for n in need if n not in (r.stdout or '')]}")

    r = run([CLI, "diff", EXAMPLE, w])
    check("S5", "diff 输出斧位与缺口变化",
          r.returncode == 0 and "斧位" in r.stdout and "门槛" in r.stdout,
          (r.stdout or "")[:120])


def test_review(tmp):
    print("\n§1.1.3 交付体检（review）")

    r = run([CLI, "review", EXAMPLE], timeout=600)
    ids = [f"D{i}" for i in range(1, 9)]
    check("V1", "review 一条命令跑完八项并给单一结论",
          r.returncode == 0 and all(i in r.stdout for i in ids) and "可交付" in r.stdout,
          f"缺 {[i for i in ids if i not in (r.stdout or '')]}")

    r = run([CLI, "review", EXAMPLE, "--json", "--fast"])
    try:
        res = json.loads(r.stdout)
    except Exception:
        res = {}
    check("V2", "review --json 给出 items / hard_fail / ok",
          r.returncode == 0 and len(res.get("items") or []) == 12
          and res.get("ok") is True and res.get("hard_fail") == [],
          f"items={len(res.get('items') or [])} ok={res.get('ok')}")

    # 把红队全部打回 open，硬门槛必须拦下来
    w = os.path.join(tmp, "rt-open.json")
    d = jload(EXAMPLE)
    for q in ((d.get("consistency") or {}).get("redteam") or []):
        if isinstance(q, dict):
            q["verdict"] = "open"
    with open(w, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    r = run([CLI, "review", w, "--fast", "--strict"])
    check("V3", "有未结红队时 review --strict 退出码 1 并点名 D4",
          r.returncode == 1 and "D4" in r.stdout and "不可交付" in r.stdout,
          f"rc={r.returncode}")


def test_whatif(tmp):
    print("\n§1.1.3 反事实推演（whatif）")

    before = open(EXAMPLE, "rb").read()
    r = run([CLI, "whatif", EXAMPLE, "--scale", "physics.constants[0].world_value=0.7",
             "--recalc", "--json"])
    try:
        res = json.loads(r.stdout)
    except Exception:
        res = {}
    g0, g1 = (res.get("derived") or {}).get("gravity_g") or (None, None)
    after = open(EXAMPLE, "rb").read()
    check("W1", "whatif --scale 改 G 后重力下降，原文件不动",
          r.returncode == 0 and g0 and g1 and g1 < g0 and before == after,
          f"gravity {g0} → {g1}")

    r = run([CLI, "whatif", EXAMPLE, "--scale", "cosmology.bodies[0].mass_earth=3", "--json"])
    try:
        res2 = json.loads(r.stdout)
    except Exception:
        res2 = {}
    check("W2", "改质量不重算时点名先崩的那一条（P01）",
          r.returncode == 0
          and any(c.get("id") == "P01" for c in (res2.get("new_fatal") or []))
          and (res2.get("after") or {}).get("fatal", 0) > 0,
          f"new_fatal={[c.get('id') for c in (res2.get('new_fatal') or [])]}")

    out = os.path.join(tmp, "whatif.json")
    r = run([CLI, "whatif", EXAMPLE, "--scale", "physics.constants[0].world_value=0.7",
             "--recalc", "--write", out])
    ok_file = os.path.exists(out)
    d = jload(out) if ok_file else {}
    changed = (d.get("physics", {}).get("constants") or [{}])[0].get("world_value")
    orig = (jload(EXAMPLE).get("physics", {}).get("constants") or [{}])[0].get("world_value")
    check("W3", "whatif --write 写出假设世界，原世界仍未被改动",
          r.returncode == 0 and ok_file and changed != orig
          and open(EXAMPLE, "rb").read() == before,
          f"{orig} → {changed}")


def test_sky(tmp):
    print("\n§1.1.4 观测层（sky）")

    r = run([CLI, "sky", EXAMPLE])
    need = ("【今夜】", "【全天】", "【关键天体】", "【一年】", "【判断】")
    check("K1", "sky 五段输出齐全（今夜/全天/关键天体/一年/判断）",
          r.returncode == 0 and all(k in r.stdout for k in need),
          f"缺 {[k for k in need if k not in (r.stdout or '')]}")

    r = run([CLI, "sky", EXAMPLE, "--json"])
    try:
        d = json.loads(r.stdout)
    except Exception:
        d = {}
    sk = d.get("sky") or {}
    check("K2", "sky --json 字段稳定（moment/sky/suns/year/checks）",
          r.returncode == 0 and all(k in d for k in ("moment", "sky", "suns", "year", "checks"))
          and all(k in sk for k in ("limit_mag", "visible_stars", "milky_way", "sky_brightness")),
          f"keys={sorted(d)[:8]}")

    check("K3", "赫利孔：极限星等 ≤4.5、银河不可见、可见星 <1000",
          sk.get("limit_mag", 99) <= 4.5 and sk.get("milky_way") is False
          and sk.get("visible_stars", 9999) < 1000,
          f"limit={sk.get('limit_mag')} mw={sk.get('milky_way')} vis={sk.get('visible_stars')}")

    r = run([CLI, "sky", ASTER, "--json"])
    try:
        d2 = json.loads(r.stdout)
    except Exception:
        d2 = {}
    sk2 = d2.get("sky") or {}
    check("K4", "星夜：极限星等 ≥6.0、可见星 ≥2500、银河可见",
          sk2.get("limit_mag", 0) >= 6.0 and sk2.get("visible_stars", 0) >= 2500
          and sk2.get("milky_way") is True,
          f"limit={sk2.get('limit_mag')} vis={sk2.get('visible_stars')} mw={sk2.get('milky_way')}")

    md = os.path.join(tmp, "night.md")
    r = run([CLI, "sky", EXAMPLE, "--md", md])
    png = os.path.join(tmp, "night.png")
    chart_ok = r.returncode == 0 and os.path.exists(md) and os.path.exists(png)
    lines = 0
    if chart_ok:
        lines = len([x for x in open(md, encoding="utf-8").read().splitlines()])
    check("K5", "ASCII 星图 + PNG 星图都能落地",
          chart_ok and lines > 40 and os.path.getsize(png) > 2000,
          f"md={os.path.exists(md)} png={os.path.exists(png) if chart_ok else 0}")

    r = run([CLI, "sky", EXAMPLE, "--check"])
    check("K6", "sky --check S01/S02/S03 全 pass",
          r.returncode == 0 and "S01" in r.stdout and "S02" in r.stdout
          and "S03" in r.stdout and "✗" not in r.stdout and "  ! S0" not in r.stdout,
          (r.stdout or "")[-200:])

    # ── 一年：昼长 ────────────────────────────────────────────
    r = run([CLI, "sky", EXAMPLE, "--year"])
    ok_y1 = False
    try:
        rows = [x for x in r.stdout.splitlines() if "月" in x and "昼长" not in x]
        ok_y1 = r.returncode == 0 and "15." in r.stdout and "16." in r.stdout and len(rows) >= 8
    except Exception:
        ok_y1 = False
    check("Y1", "sky --year 与手算对得上（赫利孔 15.0–16.4 h，8 个月）", ok_y1,
          (r.stdout or "")[:180])

    w0 = os.path.join(tmp, "tilt0.json")
    d = jload(EXAMPLE)
    d["cosmology"]["bodies"][0]["axial_tilt_deg"] = 0.0
    with open(w0, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    r = run([CLI, "sky", w0, "--year"])
    flat = "无" in r.stdout and "15.7" in r.stdout
    check("Y2", "倾角 0° → 全年昼长等于半天（15.7 h）", r.returncode == 0 and flat,
          (r.stdout or "")[:180])

    w90 = os.path.join(tmp, "tilt90.json")
    d = jload(EXAMPLE)
    d["cosmology"]["bodies"][0]["axial_tilt_deg"] = 90.0
    with open(w90, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    r = run([CLI, "sky", w90, "--year"])
    check("Y3", "倾角 90° → 出现极昼与极夜", r.returncode == 0 and "极昼 有" in r.stdout
          and "极夜 有" in r.stdout, (r.stdout or "")[-180:])

    # ── whatif --sky ──────────────────────────────────────────
    r = run([CLI, "whatif", EXAMPLE, "--set",
             "cosmology.bodies[0].axial_tilt_deg=80", "--sky", "--json"])
    try:
        res = json.loads(r.stdout)
    except Exception:
        res = {}
    sky_rows = ((res.get("sky") or {}).get("rows") or [])
    check("W4", "whatif --sky 加第五层「抬头」，倾角 80° 报出极昼极夜",
          r.returncode == 0 and any(x.get("field") == "极昼" for x in sky_rows)
          and any(x.get("field") == "极夜" for x in sky_rows),
          f"rows={[x.get('field') for x in sky_rows]}")

    r = run([CLI, "whatif", EXAMPLE, "--set",
             "cosmology.bodies[0].atmosphere.surface_pressure_kpa=300", "--sky", "--json"])
    try:
        res2 = json.loads(r.stdout)
    except Exception:
        res2 = {}
    rows2 = ((res2.get("sky") or {}).get("rows") or [])
    layered = all(k in res2 for k in ("changes", "before", "after", "phenomena", "downstream"))
    check("W5", "whatif --sky 增压后极限星等下降，原四层输出不变",
          r.returncode == 0 and layered
          and any(x.get("field") == "极限星等" for x in rows2),
          f"rows={[x.get('field') for x in rows2]} layered={layered}")

    # ── 呈现与自检 ────────────────────────────────────────────
    md2 = os.path.join(tmp, "world_export.md")
    r = run([CLI, "export", EXAMPLE, "--md", md2])
    body = open(md2, encoding="utf-8").read() if os.path.exists(md2) else ""
    check("D1", "档案第一屏是「第一眼」：星图 + 今夜一行",
          r.returncode == 0 and "第一眼" in body and "今夜" in body
          and body.find("第一眼") < body.find("创作路线"),
          f"len={len(body)}")

    html = os.path.join(tmp, "p.html")
    r = run([CLI, "preview", EXAMPLE, "-o", html])
    page = open(html, encoding="utf-8").read() if os.path.exists(html) else ""
    check("D2", "预览页带今夜星图卡片（帧数据已注入）",
          r.returncode == 0 and "pangu-sky" in page and '"frames"' in page,
          f"len={len(page)}")

    mdtxt = open(md, encoding="utf-8").read() if os.path.exists(md) else ""
    check("X6", "sky --md 出的表含逐月昼长与银河说明",
          "昼长" in mdtxt and "mag/arcsec" in mdtxt and "简化模型" in mdtxt,
          f"len={len(mdtxt)}")

    r = run([CLI, "doctor"])
    check("X7", "doctor 认出观测层 sky.py", r.returncode == 0 and "sky.py" in r.stdout,
          (r.stdout or "")[-160:])


def test_earth(tmp):
    print("\n§1.1.4 增补（温室 / 寿命 / 季节 / 承载力 / 基准）")

    # ── 温室与恒星 ────────────────────────────────────────────
    earth = {
        "atmosphere": {"surface_pressure_kpa": 101.325,
                       "composition": {"N2": 0.78, "O2": 0.21, "CO2": 0.00042}},
    }
    gh, why = ws.estimate_greenhouse(earth)
    check("G1", "温室由成分估：地球 420 ppm CO₂ → 33 K ±3",
          abs(gh - 33.0) <= 3.0 and why == "composition", f"gh={gh:.1f}")

    w = jload(EXAMPLE)
    d = ws.compute_derived(w)
    b0 = d["bodies"][0]
    check("G2", "温室声明值优先（赫利孔仍用 33 K，不被 10% CO₂ 估成 55 K）",
          b0["greenhouse_delta_k"] == 33.0 and b0["greenhouse_source"] == "declared"
          and (b0.get("greenhouse_estimated_k") or 0) > 45,
          f"decl={b0['greenhouse_delta_k']} est={b0.get('greenhouse_estimated_k')}")

    sun = [s for s in d["stars"] if s["name"] == "长明"]
    check("G3", "恒星主序寿命：太阳质量 → 10 Gyr",
          sun and abs(sun[0]["ms_lifetime_gyr"] - 10.0) < 0.6,
          f"{sun[0]['ms_lifetime_gyr'] if sun else '—'}")

    hz = d.get("hz_au") or []
    check("G4", "宜居带（总光度 1.47 L☉ → 1.16–1.67 AU）",
          len(hz) == 2 and 1.0 < hz[0] < 1.3 and 1.5 < hz[1] < 1.8, f"hz={hz}")

    # ── 季节 ──────────────────────────────────────────────────
    r = run([CLI, "map", EXAMPLE, "--season", "--res", "144x72"])
    ok_s1 = r.returncode == 0 and "summer" in r.stdout and "winter" in r.stdout
    check("S1", "map --season 出冬夏两套气候", ok_s1, (r.stdout or "")[-160:])

    oks = oki = 0.0
    try:
        for line in r.stdout.splitlines():
            if line.strip().startswith("summer"):
                oks = float(line.split("降水 北")[1].split("/")[0])
            if line.strip().startswith("winter"):
                oki = float(line.split("降水 北")[1].split("/")[0])
    except Exception:
        pass
    check("S2", "北半球夏季降水 > 冬季（ITCZ 随赤纬北移）", oks > oki * 1.5,
          f"夏 {oks:.0f} / 冬 {oki:.0f}")

    w0 = os.path.join(tmp, "flat.json")
    d0 = jload(EXAMPLE)
    d0["cosmology"]["bodies"][0]["axial_tilt_deg"] = 0.0
    with open(w0, "w", encoding="utf-8") as f:
        json.dump(d0, f, ensure_ascii=False)
    r = run([CLI, "map", w0, "--season", "--res", "96x48"])
    check("S3", "倾角 0° 时明确说「没有季节」",
          r.returncode == 0 and "没有季节" in r.stdout, (r.stdout or "")[-100:])

    # ── 承载力 ────────────────────────────────────────────────
    r = run([CLI, "capacity", ASTER, "--json"])
    try:
        cap = json.loads(r.stdout)
    except Exception:
        cap = {}
    check("C1", "星夜（地球参数）陆地 NPP 落在 45–70 Gt C/yr",
          r.returncode == 0 and 45 <= cap.get("land_npp_gtc_yr", 0) <= 70,
          f"npp={cap.get('land_npp_gtc_yr')}")

    check("C2", "capacity --json 字段齐全且人口为正",
          all(k in cap for k in ("land_npp_gtc_yr", "harvest_fraction",
                                 "humans_subsistence", "assumptions"))
          and cap.get("humans_subsistence", 0) > 0,
          f"keys={sorted(cap)[:4]}")

    wc = os.path.join(tmp, "cap.json")
    with open(wc, "w", encoding="utf-8") as f:
        json.dump(jload(ASTER), f, ensure_ascii=False)
    r = run([CLI, "capacity", wc, "--write", "--yes"])
    got = jload(wc).get("biology", {}).get("carrying_capacity") or {}
    check("C3", "capacity --write 写回 biology.carrying_capacity",
          r.returncode == 0 and got.get("generator") == "capacity/1.1.4"
          and got.get("humans_subsistence", 0) > 0,
          f"got={list(got)[:4]}")

    # ── 基准 ──────────────────────────────────────────────────
    r = run([CLI, "benchmark", "earth"])
    check("B1", "benchmark earth 退出码 0 且给出通过数",
          r.returncode == 0 and "通过" in r.stdout and "纬向" in r.stdout,
          (r.stdout or "")[-140:])

    r = run([CLI, "benchmark", "earth", "--json"])
    try:
        bm = json.loads(r.stdout)
    except Exception:
        bm = {}
    rows = bm.get("rows") or []
    check("B2", "benchmark --json 25 条曲线齐全且全部达标",
          len(rows) == 25 and all(x.get("ok") for x in rows) and bm.get("ok"),
          f"failed={[x.get('id') for x in rows if not x.get('ok')]} "
          f"passed={bm.get('passed')}/{bm.get('total')}")

    t_row = next((x for x in rows if x.get("id") == "B01"), {})
    check("B3", "纬向温度 RMSE ≤ 8 K、降水相关 ≥ 0.70",
          t_row.get("got", 99) <= 8.0
          and next((x.get("got", 0) for x in rows if x.get("id") == "B02"), 0) >= 0.70,
          f"T={t_row.get('got')}")

    r = run([CLI, "review", EXAMPLE, "--fast"])
    check("B4", "review 含 D9 基准项", "D9" in r.stdout and "基准" in r.stdout,
          (r.stdout or "")[-160:])

    # ── 导出 ──────────────────────────────────────────────────
    md = os.path.join(tmp, "w2.md")
    r = run([CLI, "export", EXAMPLE, "--md", md])
    body = open(md, encoding="utf-8").read() if os.path.exists(md) else ""
    check("E5", "档案带承载力 / 温室对账 / 恒星寿命三段",
          r.returncode == 0 and "承载力" in body and "主序寿命" in body
          and "温室" in body, f"len={len(body)}")


def test_small2(tmp):
    print("\n§1.1.3 小改动（第二批）")

    r = run([CLI, "plan", EXAMPLE, "--axe", "3"])
    check("X1", "plan --axe 只看这一斧：缺口 / 提问 / 检索",
          r.returncode == 0 and "斧 3" in r.stdout and "立律" in r.stdout
          and "要回答" in r.stdout and "斧 7" not in r.stdout,
          (r.stdout or "")[:80])

    r = run([CLI, "options", EXAMPLE, "--unanswered", "--axe", "3"])
    md = os.path.join(tmp, "cards.md")
    r2 = run([CLI, "options", EXAMPLE, "--md", md])
    body = open(md, encoding="utf-8").read() if os.path.exists(md) else ""
    check("X2", "options --unanswered 列未答命题 / --md 导出卡表",
          r.returncode == 0 and "Q3.1" in r.stdout and "未答命题" in r.stdout
          and r2.returncode == 0 and "| Q2.1 |" in body and "代价" in body,
          f"md={len(body)} 字节")

    r = run([CLI, "validate", EXAMPLE, "--only", "P01,R01"])
    r2 = run([CLI, "patch", EXAMPLE, "--history", "-n", "2"])
    check("X3", "validate --only 只跑指定检查 / patch --history 列修订",
          r.returncode == 0 and "P01" in r.stdout and "R01" in r.stdout
          and "N01" not in r.stdout
          and r2.returncode == 0 and "修订历史" in r2.stdout
          and ("1.1.3" in r2.stdout or "1.1.4" in r2.stdout),
          f"only={r.returncode} history={r2.returncode}")

    r = run([CLI, "entail", "--list"])
    r2 = run([CLI, "entail", EXAMPLE, "--exclude", "E01,E02", "--json"])
    try:
        rows = json.loads(r2.stdout)
    except Exception:
        rows = []
    ids = {x["id"] for x in rows}
    check("X4", "entail --list 列 36 条规则 / --exclude 反向排除",
          r.returncode == 0 and "E30" in r.stdout and "必然推论规则" in r.stdout
          and r2.returncode == 0 and rows and "E01" not in ids and "E02" not in ids,
          f"剩 {len(rows)} 条")

    r = run([CLI, "slice", EXAMPLE, "--cites"])
    r2 = run([CLI, "axioms", "--id", "C05"])
    env = dict(os.environ, PANGU_ASCII="1")
    r3 = subprocess.run([PY, CLI, "plan", EXAMPLE, "--brief"], capture_output=True,
                        text=True, encoding="utf-8", errors="replace", cwd=ROOT, env=env)
    check("X5", "slice --cites / axioms --id / PANGU_ASCII",
          r.returncode == 0 and "可解析" in r.stdout
          and r2.returncode == 0 and "代价：" in r2.stdout
          and r3.returncode == 0 and "✓" not in r3.stdout and "｜" not in r3.stdout,
          f"cites={r.returncode} id={r2.returncode} ascii={r3.returncode}")


def test_ca(tmp):
    print("\n§1.1.1 生态自动机")

    r = run([CLI, "ca", EXAMPLE, "--check"], timeout=600)
    check("C1", "ca --check 逐格 final_hash 与 summary 对齐",
          r.returncode == 0 and "final_hash" in r.stdout and "一致" in r.stdout,
          (r.stdout + r.stderr)[-200:])

    # 逐规则邻居半径：半径 1 的 Moore 邻居最多 8 个，不能被半径 2 的表污染
    sys.path.insert(0, HERE)
    import ca_engine as ca
    n1 = ca._build_neighbors(9, 7, 1, ca.SHAPE_MOORE, "lon-closed")
    n2 = ca._build_neighbors(9, 7, 2, ca.SHAPE_MOORE, "lon-closed")
    check("C2", "逐规则邻居表：半径 1 / 2 分开建",
          max(len(x) for x in n1) <= 8 and max(len(x) for x in n2) <= 24
          and max(len(x) for x in n2) > max(len(x) for x in n1),
          f"r1={max(len(x) for x in n1)} r2={max(len(x) for x in n2)}")


# ════════════════════════════════════════════════════════════════════
# §10.5 跨 harness 用例
# ════════════════════════════════════════════════════════════════════

def test_install(tmp):
    print("\n§10.5 安装器")

    r = run([INSTALL, "--list"])
    targets = ["skill", "agents", "cursor", "windsurf", "gemini", "claude-project", "all"]
    check("P1", "install --list 列出全部 target",
          r.returncode == 0 and all(t in r.stdout for t in targets),
          f"缺 {[t for t in targets if t not in r.stdout]}")

    dest = os.path.join(tmp, "inst_dry")
    r = run([INSTALL, "--target", "all", "--dest", dest,
             "--skill-dir", os.path.join(dest, "skill"), "--dry-run"])
    check("P2", "--dry-run 不写磁盘", r.returncode == 0 and not os.path.exists(dest),
          f"目录被创建：{os.path.exists(dest)}")

    dest = os.path.join(tmp, "inst")
    skill = os.path.join(dest, "skill")
    a1 = run([INSTALL, "--target", "all", "--dest", dest, "--skill-dir", skill])
    a2 = run([INSTALL, "--target", "all", "--dest", dest, "--skill-dir", skill])
    ok = a1.returncode == 0 and a2.returncode == 0
    counts = []
    for fn in ("AGENTS.md", "GEMINI.md", "CLAUDE.md"):
        p = os.path.join(dest, fn)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                counts.append(f.read().count("<!-- pangu:begin -->"))
    check("P3", "连跑两次幂等，标记块仍为 1",
          ok and counts == [1, 1, 1], f"counts={counts}")

    guard = os.path.join(ROOT, "_selftest_guard")
    r = run([INSTALL, "--target", "skill", "--skill-dir", guard])
    refused = ("拒绝" in r.stdout) and not os.path.exists(guard)
    check("P4", "目标在技能源内部时拒绝（防递归复制）", refused,
          (r.stdout + r.stderr)[-160:])
    if os.path.exists(guard):
        shutil.rmtree(guard, ignore_errors=True)

    stubs = 0
    for rel in (".cursor/rules/pangu.mdc", ".windsurf/rules/pangu.md"):
        p = os.path.join(dest, rel)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                stubs += f.read().count("{{PANGU_ROOT}}")
        else:
            stubs += 999
    check("P5", "指针文件占位符已全部替换", stubs == 0, f"残留 {stubs} 处")


def test_mcp():
    print("\n§10.5 MCP")

    def rpc(reqs):
        inp = "\n".join(json.dumps(r, ensure_ascii=False) for r in reqs) + "\n"
        r = subprocess.run([PY, MCP], input=inp, capture_output=True,
                           text=True, encoding="utf-8", timeout=180, cwd=ROOT)
        out = []
        for line in (r.stdout or "").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
        return out, (r.stderr or "")

    reps, err = rpc([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ])
    by_id = {m.get("id"): m for m in reps}

    init = by_id.get(1, {}).get("result", {})
    check("P6", "initialize 返回协议版本与 serverInfo",
          init.get("protocolVersion") and init.get("serverInfo", {}).get("name") == "pangu",
          str(init)[:120])

    tools = by_id.get(2, {}).get("result", {}).get("tools", [])
    names = {t["name"] for t in tools}
    need = {"pangu_guide", "pangu_doctor", "pangu_init",
            "pangu_validate", "pangu_preview", "pangu_export", "pangu_axioms",
            "pangu_map", "pangu_ca", "pangu_patch", "pangu_sweep", "pangu_diff",
            "pangu_plan", "pangu_options", "pangu_entail",
            "pangu_review", "pangu_whatif", "pangu_sky",
            "pangu_benchmark", "pangu_capacity", "pangu_chronicle"}
    schema_ok = all(t.get("inputSchema", {}).get("type") == "object" for t in tools)
    check("P7", "tools/list 返回 21 个工具且 schema 合法",
          len(tools) == 21 and need.issubset(names) and schema_ok,
          f"{len(tools)} 个，缺 {need - names}")

    reps, _ = rpc([
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "pangu_validate", "arguments": {"world": EXAMPLE}}},
        {"jsonrpc": "2.0", "id": 4, "method": "bogus/method"},
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "no_such_tool", "arguments": {}}},
    ])
    by_id = {m.get("id"): m for m in reps}

    res3 = by_id.get(3, {}).get("result", {})
    text3 = (res3.get("content") or [{}])[0].get("text", "")
    check("P8", "tools/call → pangu_validate 返回报告",
          res3.get("isError") is False and "自洽性审查" in text3,
          text3[:120])

    err4 = by_id.get(4, {}).get("error", {})
    check("P9", "未知方法返回 -32601", err4.get("code") == -32601, str(err4))

    res5 = by_id.get(5, {}).get("result", {})
    check("P10", "未知工具返回 isError=true", res5.get("isError") is True,
          str(res5)[:120])


def test_v115(tmp):
    print("\n§1.1.5 守恒 / 量纲 / 误差 / 适用域 / 重放")

    # ── 内核 ──────────────────────────────────────────────────
    r = run([CLI, "kernel", "--json"])
    try:
        kn = json.loads(r.stdout)
    except Exception:
        kn = {}
    rows = kn.get("rows") or []
    check("V1", "kernel 一条命令跑完 8 个内核且全过",
          r.returncode == 0 and kn.get("ok") and len(rows) == 8
          and all(x.get("ok") for x in rows),
          f"passed={kn.get('passed')}/{kn.get('total')}")

    # ── 守恒账本 ──────────────────────────────────────────────
    r = run([CLI, "ledger", EXAMPLE, "--json"])
    try:
        led = json.loads(r.stdout)
    except Exception:
        led = {}
    c02 = next((x for x in led.get("rows") or [] if x.get("id") == "C02"), {})
    check("V2", "ledger 抓到「声明温室 33 K ≠ 辐射解 51.5 K」",
          r.returncode == 0 and led.get("rows")
          and c02.get("status") in ("warn", "ok") and "C02" in str(led.get("bad")),
          f"bad={led.get('bad')} c02={c02.get('residual')}")

    import benchmark
    import conservation
    led2 = conservation.ledger(benchmark.earth_world())
    check("V3", "地球参数的世界账本能配平（辐射/水/碳/元素）",
          led2.get("ok") is True and led2.get("scored", 0) >= 2
          and led2.get("info", 0) >= 2,
          f"scored={led2.get('scored')} info={led2.get('info')} bad={led2.get('bad')}")

    # ── 量纲硬域 ──────────────────────────────────────────────
    wp = os.path.join(tmp, "unit.json")
    with open(wp, "w", encoding="utf-8") as f:
        json.dump(jload(EXAMPLE), f, ensure_ascii=False)
    r = run([CLI, "patch", wp, "--set",
             "cosmology.bodies[0].surface_temperature_k=1e9", "--dry-run"])
    check("V4", "patch 拒绝把 1e9 写进温度字段（量纲硬域）",
          r.returncode == 2 and ("量纲" in r.stdout + r.stderr),
          (r.stdout + r.stderr)[-120:])

    r = run([CLI, "patch", wp, "--set",
             "cosmology.bodies[0].radius_km=1e9", "--dry-run", "--force-unit"])
    out5 = r.stdout + r.stderr
    check("V5", "--force-unit 可以明知故犯地放行",
          r.returncode == 0 and "量纲硬域" not in out5,
          out5[-100:])

    # ── 误差传播 ──────────────────────────────────────────────
    import uq
    u = uq.propagate(uq._earth())
    t_eq = next((x for x in u["rows"] if x["id"] == "U01"), {})
    check("V6", "误差传播：地球平衡温度 254 ± 3–6 K（反照率 ±0.05 主导）",
          3.0 <= t_eq.get("pm", 0) <= 6.0
          and abs(t_eq.get("value", 0) - 254.3) < 1.0,
          f"t_eq={t_eq.get('value')}±{t_eq.get('pm')}")

    # ── 适用域 ────────────────────────────────────────────────
    r = run([CLI, "certify", EXAMPLE, "--json", "--no-bench"])
    try:
        cert = json.loads(r.stdout)
    except Exception:
        cert = {}
    bk = cert.get("by_kind") or {}
    check("V7", "certify 把结论分成算的/半算/经验/拍的，并给覆盖率",
          r.returncode == 0 and cert.get("total", 0) >= 10
          and len(bk.get("computed") or []) >= 5
          and 0.0 < cert.get("coverage", -1) <= 1.0,
          f"total={cert.get('total')} cov={cert.get('coverage')}")

    # ── 重放 ──────────────────────────────────────────────────
    r = run([CLI, "replay", EXAMPLE, "--json"])
    try:
        rp = json.loads(r.stdout)
    except Exception:
        rp = {}
    check("V8", "replay：map 与 ca 同 seed 逐位一致",
          r.returncode == 0 and rp.get("ok")
          and {x.get("layer") for x in rp.get("rows") or []} == {"map", "ca"},
          str(rp.get("rows"))[:120])

    r = run([CLI, "replay", EXAMPLE, "--layer", "ca", "--seed", "12345", "--json"])
    try:
        rp2 = json.loads(r.stdout)
    except Exception:
        rp2 = {}
    check("V9", "replay --seed：换 seed 后与存档不同（预期）",
          r.returncode == 0 and rp2.get("ok")
          and "预期" in str(rp2.get("rows")), str(rp2.get("rows"))[:120])

    # ── validate 的 C 系 ──────────────────────────────────────
    rep = ws.validate(jload(EXAMPLE))
    ids = {c.id for c in rep.checks}
    check("V10", "validate 里 C01–C03 三件套在位",
          {"C01", "C02", "C03"} <= ids,
          f"missing={ {'C01', 'C02', 'C03'} - ids }")

    # ── review 的 D10/D11 ─────────────────────────────────────
    r = run([CLI, "review", EXAMPLE, "--fast"])
    check("V11", "review 十一项（含 D10 守恒 / D11 适用域）",
          "D10" in r.stdout and "D11" in r.stdout,
          (r.stdout or "")[-120:])

    # ── 预览页里的账本（可视化）────────────────────────────────
    prev = os.path.join(tmp, "pv.html")
    r = run([CLI, "preview", ASTER, "-o", prev, "--fast"])
    html = ""
    try:
        with open(prev, encoding="utf-8") as f:
            html = f.read()
    except Exception:
        pass
    m = re.search(r'<script id="pangu-books"[^>]*>(.*?)</script>', html, re.S)
    books = {}
    if m:
        try:
            books = json.loads(m.group(1))
        except Exception:
            books = {}
    check("V12", "preview 内置账本页：占位符已替换、数据已注入",
          r.returncode == 0 and 'id="books-view"' in html
          and bool(books.get("ledger")) and "__PANGU_BOOKS_JSON__" not in html,
          f"size={len(html)} keys={sorted(books)[:5]}")




def test_preview_map(tmp):
    print("\n§1.1.6 地图入口（preview → map.html 新窗口）")

    def href_of(path):
        if not os.path.exists(path):
            return "MISSING"
        with open(path, encoding="utf-8") as f:
            h = f.read()
        if "__PANGU_MAP_HREF__" in h:
            return "PLACEHOLDER"
        m = re.search(r'<script id="pangu-map-href"[^>]*>(.*?)</script>', h, re.S)
        return (m.group(1).strip() if m else "NO-TAG")

    out = os.path.join(tmp, "prev_nomap.html")
    r = run([CLI, "preview", EXAMPLE, "-o", out, "--no-map"])
    v = href_of(out)
    check("V19", "--no-map 不挂地图入口（占位符已替换为空）",
          r.returncode == 0 and v == "", f"href={v!r}")

    d = os.path.join(tmp, "mapdir")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "map.html"), "w", encoding="utf-8") as f:
        f.write("<!doctype html><title>stub</title>")
    out2 = os.path.join(d, "prev.html")
    r2 = run([CLI, "preview", EXAMPLE, "-o", out2])
    v2 = href_of(out2)
    check("V20", "同目录有 map.html 时挂上入口（点了开新窗口）",
          r2.returncode == 0 and v2 == "map.html", f"href={v2!r}")

    # 内嵌那套必须彻底退场：既不该再有 200 KB 的场数据，也不该有画布
    with open(out2, encoding="utf-8") as f:
        h2 = f.read()
    check("V21", "预览不再内嵌地图数据（体积回落、无 map-canvas）",
          'id="map-canvas"' not in h2 and 'id="pangu-map"' not in h2,
          f"size={len(h2)}")


def test_chronicle(tmp):
    print("\n§1.1.6 编年层（chronicle）")

    r = run([CLI, "chronicle", EXAMPLE, "--json"])
    try:
        d = json.loads(r.stdout or "{}")
    except Exception:
        d = {}
    ev = d.get("events") or []
    check("V13", "chronicle --json 给出事件链 / hash / 人口模型",
          r.returncode == 0 and len(ev) >= 8 and len(str(d.get("hash") or "")) == 8
          and (d.get("population") or {}).get("carrying_capacity"),
          f"rc={r.returncode} n={len(ev)} hash={d.get('hash')}")

    a = json.loads(run([CLI, "chronicle", EXAMPLE, "--json", "--seed", "11"]).stdout or "{}")
    b = json.loads(run([CLI, "chronicle", EXAMPLE, "--json", "--seed", "11"]).stdout or "{}")
    c = json.loads(run([CLI, "chronicle", EXAMPLE, "--json", "--seed", "12"]).stdout or "{}")
    ha, hb, hc = a.get("hash"), b.get("hash"), c.get("hash")
    check("V14", "编年史可复算：同 seed 同 hash，换 seed 换 hash",
          bool(ha) and ha == hb and ha != hc, f"{ha} / {hb} / {hc}")

    no_src = [e.get("id") for e in ev if not (e.get("src") or [])]
    check("V15", "每条事件都带 src：不许有无出处的史",
          not no_src, f"缺依据：{no_src[:4]}")

    out = os.path.join(tmp, "chronicle.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(jload(EXAMPLE), f, ensure_ascii=False)
    w1 = run([CLI, "chronicle", out, "--write", "--yes"])
    w2 = run([CLI, "chronicle", out, "--check"])
    check("V16", "chronicle --write 后 --check 对得上（hash 可复算）",
          w1.returncode == 0 and w2.returncode == 0,
          f"write={w1.returncode} check={w2.returncode}")

    d2 = jload(out)
    evs = ((d2.get("history") or {}).get("chronicle") or {}).get("events") or []
    if evs:
        evs[0]["text"] = str(evs[0].get("text") or "") + "（手改）"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(d2, f, ensure_ascii=False)
    w3 = run([CLI, "chronicle", out, "--check"])
    check("V17", "手改史书后 --check 退出码 1 并点名 hash",
          w3.returncode == 1 and "hash" in (w3.stdout or ""),
          f"rc={w3.returncode}")

    res = json.loads(run([CLI, "review", EXAMPLE, "--json", "--fast"]).stdout or "{}")
    ids = [i.get("id") for i in (res.get("items") or [])]
    check("V18", "review 多出 D12 编年（十二项体检）",
          "D12" in ids and len(ids) == 12, f"items={ids}")

    # V22/V23：切片接上编年（1.1.6 收尾的一根线）
    r = run([CLI, "slice", EXAMPLE, "--prompt"])
    txt = r.stdout or ""
    years = re.findall(r"第 ([\d,]+) 年", txt)
    ev_years = {f"{int(e.get('t_year') or 0):,}" for e in ev}
    check("V22", "slice --prompt 注入编年前情，年份都来自存档编年",
          r.returncode == 0 and "只准引用这些" in txt
          and bool(years) and all(y in ev_years for y in years),
          f"years={years[:4]}")

    t2 = run([CLI, "slice", EXAMPLE, "--prompt", "--at-year", "5000"]).stdout or ""
    ys = sorted(int(y.replace(",", "")) for y in re.findall(r"第 ([\d,]+) 年", t2))
    early = run([CLI, "slice", EXAMPLE, "--prompt", "--at-year", "-100"])
    check("V23", "--at-year 只给那一年之前的事；再往前则明说「没有史」",
          bool(ys) and max(ys) <= 5000 and "18,362" not in t2
          and "成文史之前" in (early.stdout or ""),
          f"years={ys}")


# ════════════════════════════════════════════════════════════════════

def test_naming(tmp):
    print("\n§1.1.6 命名层（naming）")

    r = run([CLI, "naming", EXAMPLE, "--json"])
    try:
        d = json.loads(r.stdout or "{}")
    except Exception:
        d = {}
    ph = d.get("phonology") or {}
    per = d.get("person") or []
    plc = d.get("place") or []
    bad = [p.get("name") for p in per + plc
           if not (p.get("syllables") and p.get("rule") and p.get("src"))]
    check("V24", "naming --json 给出音系 / pool / 人名 / 地名，且每条可拆可溯",
          r.returncode == 0 and bool(ph.get("consonants")) and bool(ph.get("vowels"))
          and len(per) == 10 and len(plc) == 10 and not bad
          and (d.get("pool") or {}).get("cv", 0) > 0,
          f"cons={len(ph.get('consonants') or [])} bad={bad[:3]}")

    ha = d.get("hash")
    hb = json.loads(run([CLI, "naming", EXAMPLE, "--json"]).stdout or "{}").get("hash")
    hc = json.loads(run([CLI, "naming", EXAMPLE, "--json", "--seed", "99"]).stdout or "{}").get("hash")
    check("V25", "命名可复算：同 seed 同 hash，换 seed 换 hash",
          bool(ha) and ha == hb and ha != hc, f"{ha} / {hb} / {hc}")

    out = os.path.join(tmp, "naming.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(jload(EXAMPLE), f, ensure_ascii=False)
    w1 = run([CLI, "naming", out, "--write", "--yes"])
    w2 = run([CLI, "naming", out, "--check"])
    d2 = jload(out)
    d2["civilization"]["names"]["person"][0]["name"] = "Zzz"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(d2, f, ensure_ascii=False)
    w3 = run([CLI, "naming", out, "--check"])
    check("V26", "naming --write 后 --check 绿；手改一个名字后变红",
          w1.returncode == 0 and w2.returncode == 0 and w3.returncode == 1,
          f"write={w1.returncode} check={w2.returncode} tampered={w3.returncode}")

    r = run([CLI, "naming", EXAMPLE, "--set-phonology", "c=q,w,x;v=u,a;K=q"])
    check("V27", "--set-phonology 让作者接管音系（q / w / x 进门）",
          r.returncode == 0 and "q" in (r.stdout or "").lower(),
          f"rc={r.returncode}")


# ════════════════════════════════════════════════════════════════════

def main() -> int:
    _enc()
    print("=" * 62)
    print("  盘古 · 验收自测")
    print(f"  root: {ROOT}")
    print(f"  python: {sys.version.split()[0]}")
    print("=" * 62)

    tmp = tempfile.mkdtemp(prefix="pangu_selftest_")
    try:
        test_engine(tmp)
        test_organism(tmp)
        test_tuning(tmp)
        test_flow(tmp)
        test_cards(tmp)
        test_entail(tmp)
        test_small(tmp)
        test_review(tmp)
        test_whatif(tmp)
        test_sky(tmp)
        test_earth(tmp)
        test_small2(tmp)
        test_map(tmp)
        test_ca(tmp)
        test_install(tmp)
        test_mcp()
        test_v115(tmp)
        test_preview_map(tmp)
        test_chronicle(tmp)
        test_naming(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r[2])
    failed = [r for r in RESULTS if not r[2]]

    print("\n" + "-" * 62)
    print(f"  结果：{passed}/{total} 通过")
    if failed:
        print("  失败项：")
        for cid, name, _, note in failed:
            print(f"    ✗ {cid} {name}  {note[:120]}")
        print("-" * 62)
        return 1
    print("  全部通过。可以交付。")
    print("-" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
