#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古 · MCP 服务器（stdio / JSON-RPC 2.0 / 零依赖）
==================================================

把盘古引擎暴露成 MCP tool，供任何支持 Model Context Protocol 的宿主调用：
Claude Desktop、Cursor、Zed、Continue、Cherry Studio、以及自研 harness。

设计原则
--------
1. **不重写逻辑**：所有操作都转调 `scripts/pangu.py`，MCP 只是一层薄壳。
   这样 CLI 与 MCP 的行为永远一致，不会分叉。
2. **零依赖**：只用标准库，不需要 `pip install mcp`。协议实现是手写的最小集合
   （initialize / tools/list / tools/call / ping）。
3. **stdout 只走协议**：任何日志、异常都打到 stderr，否则会污染 JSON-RPC 流。

启动
----
    python /abs/path/to/盘古/adapters/mcp/pangu_mcp.py

客户端配置（Claude Desktop / Cursor 等）：

    {
      "mcpServers": {
        "pangu": {
          "command": "python",
          "args": ["/abs/path/to/盘古/adapters/mcp/pangu_mcp.py"]
        }
      }
    }

自检：
    echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python pangu_mcp.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CLI = os.path.join(ROOT, "scripts", "pangu.py")

SERVER_NAME = "pangu"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL = "2024-11-05"
SUPPORTED_PROTOCOLS = ("2024-11-05", "2024-10-07", "2025-03-26", "2025-06-18")

MAX_OUTPUT = 60000  # 单次 tool 返回字符上限，超出截断（防止撑爆上下文）


# ════════════════════════════════════════════════════════════════════
# 工具定义
# ════════════════════════════════════════════════════════════════════

def _schema(props: dict, required: list | None = None) -> dict:
    return {
        "type": "object",
        "properties": props,
        "required": required or [],
        "additionalProperties": False,
    }


_S = {"type": "string"}
_B = {"type": "boolean"}
_I = {"type": "integer"}

TOOLS = [
    {
        "name": "pangu_guide",
        "title": "读取创世方法论",
        "description": (
            "读取盘古的创世方法论。不传 section 返回主文档 SKILL.md（约 200 行，"
            "含三律、七斧流程、检索策略、审查协议、命令速查）；"
            "传 section 可单独读取某份参考文档，用于渐进披露、节省上下文。"
            "造世界前必先调用本工具。"
        ),
        "inputSchema": _schema({
            "section": {
                "type": "string",
                "enum": ["skill", "axes", "axioms", "search", "audit", "schema"],
                "description": "skill=主文档；axes=七斧创世法；axioms=公理库；search=检索策略；audit=自洽性审查协议；schema=world.json 字段规范",
            }
        }),
    },
    {
        "name": "pangu_doctor",
        "title": "环境自检",
        "description": "检查 Python 版本、模板文件、示例世界、CDN 可达性。首次使用或报错时先跑这个。",
        "inputSchema": _schema({}),
    },
    {
        "name": "pangu_init",
        "title": "生成世界骨架",
        "description": (
            "从一个名字与一句话种子，生成符合规范的 world.json 骨架"
            "（含 meta/seed/cosmology/physics 等全部顶层字段的空壳）。"
            "生成后由 agent 按七斧逐步填充。"
        ),
        "inputSchema": _schema({
            "name": {"type": "string", "description": "世界名，如「赫利孔」"},
            "seed": {"type": "string", "description": "一句话种子，如「三倍地球大，天上有两个太阳」"},
            "out": {"type": "string", "description": "输出路径（绝对路径最稳）。缺省写到 ./out/<id>/world.json"},
            "id": {"type": "string", "description": "英文 slug，缺省由名字生成"},
            "star_count": {"type": "integer", "description": "恒星数量 1–4，默认 2"},
            "no_stars": {"type": "boolean", "description": "无恒星世界（靠地热或其他能源）"},
            "autonomy": {
                "type": "string",
                "enum": ["auto", "co-create", "audit"],
                "description": "自主度：auto=全自主；co-create=共创；audit=只做审查",
            },
        }, ["name"]),
    },
    {
        "name": "pangu_validate",
        "title": "自洽性校验与打分",
        "description": (
            "对 world.json 做可机检的自洽性审查：结构完整性、单位与量纲、"
            "派生量计算（密度/重力/逃逸速度/平衡温度）、双星轨道稳定性、洛希极限、"
            "能量收支数量级。返回评分（0–100）、等级、致命项与修补建议。"
            "**交付前必须调用，有 fatal 不许交付。**"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "json": {"type": "boolean", "description": "返回结构化 JSON 而非人类可读报告"},
            "fix_hint": {"type": "boolean", "description": "附带每项的修补建议（默认 true）"},
        }, ["world"]),
    },
    {
        "name": "pangu_preview",
        "title": "生成 3D 预览页",
        "description": (
            "把 world.json 渲染成单文件 3D 预览页（Three.js）：多恒星系统、程序化行星表面、"
            "大气辉光、云层、轨道线、多光源昼夜、潮汐锁定、时间控制、视角切换。"
            "输出自包含 HTML，双击即可看。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "out": {"type": "string", "description": "输出 html 路径，缺省与 world.json 同目录"},
            "title": {"type": "string", "description": "页面标题，缺省用世界名"},
        }, ["world"]),
    },
    {
        "name": "pangu_export",
        "title": "导出世界档案",
        "description": (
            "生成人类可读的世界档案 Markdown：三律、常数表与地球对照、派生量、"
            "天空与气候、生态、文明、审查结论。可同时输出审查报告 JSON。"
        ),
        "inputSchema": _schema({
            "world": {"type": "string", "description": "world.json 路径"},
            "md": {"type": "string", "description": "输出 md 路径"},
            "json_out": {"type": "string", "description": "同时输出审查报告 JSON 的路径"},
        }, ["world"]),
    },
    {
        "name": "pangu_axioms",
        "title": "抽取反常识积木",
        "description": (
            "从 60+ 条公理积木里查询或随机抽取可复用的反常识设定，每条含："
            "设定、代价、痕迹、适用尺度。卡住时用它打破地球直觉。"
        ),
        "inputSchema": _schema({
            "domain": {
                "type": "string",
                "enum": ["physics", "cosmos", "math", "chemistry", "biology", "civilization"],
                "description": "领域过滤",
            },
            "roll": {"type": "integer", "description": "随机抽 N 条"},
            "json": {"type": "boolean", "description": "返回结构化 JSON"},
        }),
    },
]

GUIDE_FILES = {
    "skill": ("SKILL.md", None),
    "axes": ("references/七斧创世法.md", None),
    "axioms": ("references/公理库.md", None),
    "search": ("references/检索与灵感策略.md", None),
    "audit": ("references/自洽性审查协议.md", None),
    "schema": ("references/world-schema.md", None),
}


# ════════════════════════════════════════════════════════════════════
# 执行
# ════════════════════════════════════════════════════════════════════

def _log(msg: str) -> None:
    """日志只能走 stderr，否则会污染 JSON-RPC 流。"""
    try:
        sys.stderr.write(f"[pangu-mcp] {msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def _run_cli(args: list) -> tuple:
    """转调 CLI，返回 (退出码, stdout, stderr)。"""
    if not os.path.exists(CLI):
        return 3, "", f"找不到 CLI：{CLI}"
    try:
        r = subprocess.run(
            [sys.executable, CLI, *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
        return r.returncode, r.stdout or "", r.stderr or ""
    except subprocess.TimeoutExpired:
        return 3, "", "命令超时（300s）"
    except Exception as e:  # noqa: BLE001
        return 3, "", f"{type(e).__name__}: {e}"


def _clip(text: str) -> str:
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n\n…（已截断，原文 {len(text)} 字符）"


def _result(text: str, is_error: bool = False) -> dict:
    return {
        "content": [{"type": "text", "text": _clip(text)}],
        "isError": bool(is_error),
    }


def _call_tool(name: str, a: dict) -> dict:
    # ── 读方法论 ──────────────────────────────────────────────
    if name == "pangu_guide":
        key = a.get("section") or "skill"
        rel = GUIDE_FILES.get(key)
        if not rel:
            return _result(f"未知 section：{key}。可选：{'/'.join(GUIDE_FILES)}", True)
        path = os.path.join(ROOT, rel[0])
        if not os.path.exists(path):
            return _result(f"文档缺失：{path}", True)
        with open(path, "r", encoding="utf-8") as f:
            return _result(f.read())

    # ── 环境自检 ──────────────────────────────────────────────
    if name == "pangu_doctor":
        code, out, err = _run_cli(["doctor"])
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 生成骨架 ──────────────────────────────────────────────
    if name == "pangu_init":
        world = a.get("name") or ""
        if not world:
            return _result("缺少参数 name", True)
        args = ["init", "--name", world]
        if a.get("seed"):
            args += ["--seed", str(a["seed"])]
        if a.get("id"):
            args += ["--id", str(a["id"])]
        if a.get("out"):
            args += ["--out", str(a["out"])]
        if a.get("star_count"):
            args += ["--star-count", str(int(a["star_count"]))]
        if a.get("no_stars"):
            args += ["--no-stars"]
        if a.get("autonomy"):
            args += ["--autonomy", str(a["autonomy"])]
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 校验 ──────────────────────────────────────────────────
    if name == "pangu_validate":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["validate", str(w)]
        if a.get("json"):
            args.append("--json")
        if a.get("fix_hint", True):
            args.append("--fix-hint")
        code, out, err = _run_cli(args)
        body = out + (f"\n[stderr]\n{err}" if err.strip() else "")
        return _result(body, code not in (0, 1))   # 1 = 有 fatal，仍是有效结果

    # ── 预览 ──────────────────────────────────────────────────
    if name == "pangu_preview":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["preview", str(w)]
        if a.get("out"):
            args += ["-o", str(a["out"])]
        if a.get("title"):
            args += ["--title", str(a["title"])]
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 导出 ──────────────────────────────────────────────────
    if name == "pangu_export":
        w = a.get("world")
        if not w:
            return _result("缺少参数 world", True)
        args = ["export", str(w)]
        if a.get("md"):
            args += ["--md", str(a["md"])]
        if a.get("json_out"):
            args += ["--json-out", str(a["json_out"])]
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    # ── 公理库 ────────────────────────────────────────────────
    if name == "pangu_axioms":
        args = ["axioms"]
        if a.get("domain"):
            args += ["--domain", str(a["domain"])]
        if a.get("roll"):
            args += ["--roll", str(int(a["roll"]))]
        if a.get("json"):
            args.append("--json")
        code, out, err = _run_cli(args)
        return _result(out + (f"\n[stderr]\n{err}" if err.strip() else ""), code != 0)

    return _result(f"未知工具：{name}", True)


# ════════════════════════════════════════════════════════════════════
# JSON-RPC 2.0 over stdio
# ════════════════════════════════════════════════════════════════════

def _send(obj: dict) -> None:
    data = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write(data + "\n")
    sys.stdout.flush()


def _ok(mid, result: dict) -> None:
    _send({"jsonrpc": "2.0", "id": mid, "result": result})


def _err(mid, code: int, message: str, data=None) -> None:
    e = {"code": code, "message": message}
    if data is not None:
        e["data"] = data
    _send({"jsonrpc": "2.0", "id": mid, "error": e})


def _handle(msg: dict) -> None:
    method = msg.get("method")
    mid = msg.get("id")
    params = msg.get("params") or {}
    is_notification = "id" not in msg

    # ── 握手 ─────────────────────────────────────────────────
    if method == "initialize":
        want = params.get("protocolVersion")
        ver = want if want in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL
        _ok(mid, {
            "protocolVersion": ver,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": (
                "盘古造世引擎。造世界前先调用 pangu_guide 读方法论；"
                "然后用 pangu_init 建骨架、逐步填充 world.json、"
                "pangu_validate 审查、pangu_preview 出 3D、pangu_export 出档案。"
            ),
        })
        return

    if method in ("notifications/initialized", "initialized"):
        return                      # 通知，无需响应

    if method in ("notifications/cancelled", "notifications/roots/list_changed",
                  "notifications/progress", "$/cancelRequest"):
        return

    if method == "ping":
        _ok(mid, {})
        return

    if method == "tools/list":
        _ok(mid, {"tools": TOOLS})
        return

    if method == "tools/call":
        if is_notification:
            return
        tname = params.get("name")
        targs = params.get("arguments") or {}
        if not isinstance(targs, dict):
            _err(mid, -32602, "arguments 必须是对象")
            return
        try:
            _ok(mid, _call_tool(tname, targs))
        except Exception as e:  # noqa: BLE001
            _log(f"tool {tname} 异常：{e}")
            _ok(mid, _result(f"工具执行失败：{type(e).__name__}: {e}", True))
        return

    if method in ("resources/list", "prompts/list"):
        _ok(mid, {"resources": []} if method == "resources/list" else {"prompts": []})
        return

    if method == "logging/setLevel":
        return

    if is_notification:
        return
    _err(mid, -32601, f"Method not found: {method}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

    _log(f"启动 · root={ROOT} · python={sys.version.split()[0]}")
    if not os.path.exists(CLI):
        _log(f"警告：找不到 CLI {CLI}")

    for raw in sys.stdin.buffer:
        line = raw.decode("utf-8", "replace").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            _err(None, -32700, "Parse error")
            continue

        if isinstance(msg, list):
            for m in msg:
                if isinstance(m, dict):
                    _handle(m)
            continue
        if isinstance(msg, dict):
            _handle(msg)
        else:
            _err(None, -32600, "Invalid Request")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
    except BrokenPipeError:
        sys.exit(0)
