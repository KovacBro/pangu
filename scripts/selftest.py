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
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLI = os.path.join(HERE, "pangu.py")
MCP = os.path.join(ROOT, "adapters", "mcp", "pangu_mcp.py")
INSTALL = os.path.join(ROOT, "install.py")
EXAMPLE = os.path.join(ROOT, "examples", "helikon", "world.json")
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
            "pangu_map", "pangu_ca"}
    schema_ok = all(t.get("inputSchema", {}).get("type") == "object" for t in tools)
    check("P7", "tools/list 返回 9 个工具且 schema 合法",
          len(tools) == 9 and need.issubset(names) and schema_ok,
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
        test_map(tmp)
        test_ca(tmp)
        test_install(tmp)
        test_mcp()
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
