#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘古 · 跨 harness 安装器
========================

把盘古的入口铺到目标 agent / harness，不改动技能本体。
纯标准库，Windows / macOS / Linux 通用，可重复执行（幂等）。

用法
----
    python install.py --list                    # 看有哪些 target
    python install.py --target skill            # 装成原生技能目录（默认 ~/.claude/skills/pangu）
    python install.py --target all --dest .     # 在当前项目铺齐所有指针文件
    python install.py --target cursor --dest .  # 只装 Cursor 规则
    python install.py --target skill --skill-dir "D:/agents/skills/pangu"
    python install.py --target skill --link     # 用符号链接代替复制（便于随源更新）
    python install.py --print-mcp               # 打印 MCP 客户端配置片段
    python install.py --target all --dest . --dry-run   # 只预览，不动磁盘
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
VERSION = "1.0.0"

BEGIN = "<!-- pangu:begin -->"
END = "<!-- pangu:end -->"

IGNORE = shutil.ignore_patterns(
    "__pycache__", "*.pyc", ".git", ".gitignore", "out", "dist",
    "*.zip", ".DS_Store", "Thumbs.db", ".venv", "venv",
)

TARGETS = {
    "skill": "装成原生技能目录（Claude Code / Codex / Cline / OpenHands 等，复制整棵树）",
    "agents": "写 AGENTS.md 指针（Codex / Amp / Jules / 多数 IDE agent）",
    "cursor": "写 .cursor/rules/pangu.mdc（Cursor）",
    "windsurf": "写 .windsurf/rules/pangu.md（Windsurf）",
    "gemini": "写/追加 GEMINI.md（Gemini CLI）",
    "claude-project": "写/追加 CLAUDE.md（Claude Code 项目级）",
    "all": "以上全部（skill + 所有指针）",
}


# ════════════════════════════════════════════════════════════════════
# 输出
# ════════════════════════════════════════════════════════════════════

def say(msg: str = "") -> None:
    print(msg)


def ok(msg: str) -> None:
    say(f"  \u2713 {msg}")


def skip(msg: str) -> None:
    say(f"  \u2013 {msg}")


def warn(msg: str) -> None:
    say(f"  ! {msg}")


# ════════════════════════════════════════════════════════════════════
# 指针块
# ════════════════════════════════════════════════════════════════════

def pointer_block() -> str:
    r = ROOT.replace("\\", "/")
    return f"""{BEGIN}
## 盘古造世引擎（世界构建技能）

技能根：`{r}`

当任务涉及**造世界 / 宇宙 / 星球并设定底层法则**、非地球物理（双恒星、反向重力、无水生命）、
**架空设定自洽性审查**、**可交互 3D 星球预览**时启用本技能：

1. 先完整读 `{r}/SKILL.md`（技能正文，不要跳过）。
2. 再按正文点名，按需读 `{r}/references/` 下的文件（渐进披露，不要全量加载）。
3. 脚本一律用绝对路径调用：`python "{r}/scripts/pangu.py" <子命令>`

四条纪律：

- **先立律，后长物**：物理层未定稿，不谈生物与文明。
- **三律**：逆行（至少一条常识是反的）、代价（可量化）、痕迹（居民看得见）。
- **单一数据源**：只改 `world.json`；`preview.html`、`世界档案.md` 是生成物，禁止手改。
- **产物隔离**：写 `./out/<世界id>/`，不要写进技能根。

仅依赖 Python ≥3.9 标准库，无需 `pip install`。
{END}"""


def upsert_block(path: str, block: str, dry: bool) -> str:
    """把 block 幂等写入 path：有标记则替换，无标记则追加，不存在则新建。"""
    path = os.path.abspath(path)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            old = f.read()
        if BEGIN in old and END in old:
            head, _, rest = old.partition(BEGIN)
            _, _, tail = rest.partition(END)
            new = head + block + tail
            action = "replace"
        else:
            sep = "" if old.endswith("\n\n") or not old.strip() else ("\n" if old.endswith("\n") else "\n\n")
            new = old + sep + block + "\n"
            action = "append"
    else:
        new = block + "\n"
        action = "create"

    if not dry:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new)
    return action


def write_file(path: str, content: str, dry: bool) -> str:
    path = os.path.abspath(path)
    existed = os.path.exists(path)
    if not dry:
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    return "overwrite" if existed else "create"


def render_adapter(rel: str) -> str:
    """读适配器模板，替换 {{PANGU_ROOT}} 占位符。"""
    p = os.path.join(ROOT, rel)
    with open(p, "r", encoding="utf-8") as f:
        s = f.read()
    return s.replace("{{PANGU_ROOT}}", ROOT.replace("\\", "/"))


# ════════════════════════════════════════════════════════════════════
# 各 target
# ════════════════════════════════════════════════════════════════════

def install_skill(skill_dir: str, link: bool, dry: bool) -> None:
    skill_dir = os.path.abspath(os.path.expanduser(skill_dir))
    say(f"\n[skill] → {skill_dir}")
    if dry:
        warn("dry-run：将复制整棵技能树（跳过 __pycache__ / out / dist）")
        return

    src = os.path.abspath(ROOT)
    if skill_dir == src:
        skip("目标即技能源目录，无需复制")
        return

    # 防止自我递归：目标在源内部（或反之）会让 copytree 无限嵌套自己
    def _inside(a: str, b: str) -> bool:
        return a == b or a.startswith(b + os.sep)

    if _inside(skill_dir, src):
        warn("目标目录位于技能源内部，会递归复制自身，已拒绝。")
        say("    请换到源目录之外，例如：")
        say(f"      python install.py --target skill --skill-dir ~/.claude/skills/pangu")
        say(f"      python install.py --target skill --skill-dir {os.path.join(os.path.dirname(src), 'pangu')}")
        return
    if _inside(src, skill_dir):
        warn("技能源位于目标内部，会覆盖自身，已拒绝。")
        return

    if link:
        try:
            if os.path.islink(skill_dir):
                os.unlink(skill_dir)
            elif os.path.exists(skill_dir):
                warn("目标已存在且不是符号链接，改为复制覆盖")
                shutil.copytree(ROOT, skill_dir, dirs_exist_ok=True, ignore=IGNORE)
                ok("已复制")
                return
            os.makedirs(os.path.dirname(skill_dir) or ".", exist_ok=True)
            os.symlink(ROOT, skill_dir, target_is_directory=True)
            ok("已创建符号链接（源目录更新会自动生效）")
            return
        except (OSError, NotImplementedError) as e:
            warn(f"符号链接失败（{e}），回退到复制")

    os.makedirs(skill_dir, exist_ok=True)
    shutil.copytree(ROOT, skill_dir, dirs_exist_ok=True, ignore=IGNORE)
    n = sum(len(fs) for _, _, fs in os.walk(skill_dir))
    ok(f"已复制 {n} 个文件")
    ok(f"入口：{os.path.join(skill_dir, 'SKILL.md')}")


def install_pointer(kind: str, dest: str, dry: bool) -> None:
    dest = os.path.abspath(os.path.expanduser(dest))
    say(f"\n[{kind}] → {dest}")

    if kind == "agents":
        a = upsert_block(os.path.join(dest, "AGENTS.md"), pointer_block(), dry)
        ok(f"AGENTS.md {a}")

    elif kind == "gemini":
        a = upsert_block(os.path.join(dest, "GEMINI.md"), pointer_block(), dry)
        ok(f"GEMINI.md {a}")

    elif kind == "claude-project":
        a = upsert_block(os.path.join(dest, "CLAUDE.md"), pointer_block(), dry)
        ok(f"CLAUDE.md {a}")

    elif kind == "cursor":
        p = os.path.join(dest, ".cursor", "rules", "pangu.mdc")
        a = write_file(p, render_adapter("adapters/cursor/pangu.mdc"), dry)
        ok(f".cursor/rules/pangu.mdc {a}")

    elif kind == "windsurf":
        p = os.path.join(dest, ".windsurf", "rules", "pangu.md")
        a = write_file(p, render_adapter("adapters/windsurf/pangu.md"), dry)
        ok(f".windsurf/rules/pangu.md {a}")


def print_mcp() -> None:
    server = os.path.join(ROOT, "adapters", "mcp", "pangu_mcp.py")
    cfg = {
        "mcpServers": {
            "pangu": {
                "command": sys.executable or "python",
                "args": [server],
                "env": {},
            }
        }
    }
    say("\n[mcp] 把下面这段合并进客户端配置")
    say("      Claude Desktop: claude_desktop_config.json")
    say("      Cursor: ~/.cursor/mcp.json  ·  Cherry Studio / Zin / Continue 同理")
    say("")
    say(json.dumps(cfg, ensure_ascii=False, indent=2))
    say("")
    say("  提示：command 建议写解释器绝对路径；args 必须是 pangu_mcp.py 的绝对路径。")
    say("  验证：echo '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}' | python \""
        + server + "\"")


def list_targets() -> None:
    say(f"盘古 {VERSION} · 可安装目标\n")
    for k, v in TARGETS.items():
        say(f"  {k:<16} {v}")
    say("\n示例：")
    say("  python install.py --target all --dest .")
    say("  python install.py --target skill --skill-dir ~/.claude/skills/pangu")
    say("  python install.py --print-mcp")


# ════════════════════════════════════════════════════════════════════
# main
# ════════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:
            pass

    p = argparse.ArgumentParser(
        prog="install",
        description="把盘古的入口铺到各种 agent / harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="核心只有一份，入口可以有很多个。",
    )
    p.add_argument("--target", default=None,
                   choices=list(TARGETS.keys()),
                   help="安装目标（不传则显示列表）")
    p.add_argument("--dest", default=".", help="指针文件的落点，默认当前目录")
    p.add_argument("--skill-dir", default=None,
                   help="skill 目标的安装目录，默认 ~/.claude/skills/pangu")
    p.add_argument("--link", action="store_true", help="skill 目标用符号链接代替复制")
    p.add_argument("--print-mcp", action="store_true", help="打印 MCP 客户端配置")
    p.add_argument("--dry-run", action="store_true", help="只显示将做什么，不写磁盘")
    p.add_argument("--list", action="store_true", help="列出安装目标")
    p.add_argument("--version", action="version", version=f"pangu {VERSION}")
    args = p.parse_args(argv)

    if args.list or (not args.target and not args.print_mcp):
        list_targets()
        return 0

    dry = args.dry_run
    if dry:
        warn("DRY-RUN：不会写入任何文件\n")

    t = args.target
    skill_dir = args.skill_dir or os.path.join(os.path.expanduser("~"), ".claude", "skills", "pangu")

    if t in ("skill", "all"):
        install_skill(skill_dir, args.link, dry)
    if t in ("agents", "all"):
        install_pointer("agents", args.dest, dry)
    if t in ("gemini", "all"):
        install_pointer("gemini", args.dest, dry)
    if t in ("claude-project", "all"):
        install_pointer("claude-project", args.dest, dry)
    if t in ("cursor", "all"):
        install_pointer("cursor", args.dest, dry)
    if t in ("windsurf", "all"):
        install_pointer("windsurf", args.dest, dry)

    if t == "all" or args.print_mcp:
        print_mcp()

    say("")
    say("完成。下一步：让 agent 读 SKILL.md，或直接问它「帮我造一个世界」。")
    say("纯对话环境（不能读文件）请改贴 adapters/generic/BOOTSTRAP.md。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
