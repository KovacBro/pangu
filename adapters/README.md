# 适配器层 · 让任何 agent 都能用盘古

盘古的核心（`SKILL.md` + `references/` + `scripts/`）与宿主无关。这里只是**入口适配**，不复制任何逻辑。

## 兼容矩阵

| Harness | 加载方式 | 入口文件 | 自动加载 |
|---|---|---|---|
| **Claude Code** | 技能目录 `~/.claude/skills/pangu/` | `SKILL.md` | ✅ 按 description 自动匹配 |
| **Claude.ai / Claude Desktop** | 上传技能包 / MCP | `SKILL.md` 或 MCP | ✅ |
| **OpenAI Codex CLI** | 项目根 `AGENTS.md` 或 `~/.codex/AGENTS.md` | `AGENTS.md` | ✅ 每轮自动读 |
| **Cursor** | `.cursor/rules/pangu.mdc` | `adapters/cursor/pangu.mdc` | ⚠️ 由 description 决定触发 |
| **Windsurf** | `.windsurf/rules/pangu.md` | `adapters/windsurf/pangu.md` | ⚠️ `model_decision` 触发 |
| **Gemini CLI** | 项目根 `GEMINI.md` | `adapters/gemini/GEMINI.md` | ✅ |
| **Cline / Roo / Kilo** | 自定义指令 / 工作区规则 | `AGENTS.md` | ✅ |
| **Amp / Jules / OpenHands** | `AGENTS.md` | `AGENTS.md` | ✅ |
| **Zed / Continue / Cherry Studio** | MCP | `adapters/mcp/pangu_mcp.py` | ✅ tool 调用 |
| **任意纯对话模型** | 粘贴提示词 | `adapters/generic/BOOTSTRAP.md` | ❌ 手动 |

## 三种安装方式

```bash
# 1) 装成原生技能目录（复制整棵树）—— Claude Code 等
python install.py --target skill

# 2) 只铺指针文件到当前项目 —— Codex / Cursor / Windsurf / Gemini
python install.py --target all --dest .

# 3) MCP：把这段 JSON 加进客户端的 server 配置
python install.py --print-mcp
```

`--dry-run` 可以先看会写哪些文件，不动磁盘。

## 指针里的路径占位符

`adapters/*/` 下的文件共用占位符 `{{PANGU_ROOT}}`。`install.py` 安装时会替换成技能根的绝对路径。若你手工复制这些文件，请自己替换，否则 agent 不知道去哪读 `SKILL.md`。

## 排错

| 现象 | 原因 | 处理 |
|---|---|---|
| agent 完全不提盘古 | 指针文件没被加载 | 确认文件名与位置符合该宿主约定（见上表） |
| agent 读了入口但行为跑偏 | 只读了指针没读 `SKILL.md` | 在指针里已有硬要求"先读 SKILL.md 全文"，检查是否被上下文截断 |
| 脚本报 `No module named world_schema` | 从错误目录执行 | `cd` 到技能根，或直接用 `python <绝对路径>/scripts/pangu.py` |
| `python` 不存在 | 环境变量未配 | 换成真实解释器路径（Windows 常见 `py -3`） |
| MCP 客户端看不到 tool | 配置里用了相对路径 | 必须用 `pangu_mcp.py` 的**绝对路径** |
