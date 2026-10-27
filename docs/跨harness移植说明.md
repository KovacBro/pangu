# 跨 harness 移植说明

盘古是**一个技能，多种入口**。本文说明各 agent 的加载机制、配置方式与排错路径。

- 只想赶紧用 → 看 §1
- 想知道某宿主为什么没触发 → 看 §3 对应小节
- 想接入一个新宿主 → 看 §4

---

## 1. 三条路，怎么选

| 你在用什么 | 走哪条 | 一条命令 |
|---|---|---|
| Claude Code、Cline、OpenHands、或任何支持 `SKILL.md` 的框架 | A 原生技能目录 | `python install.py --target skill` |
| Codex CLI、Amp、Jules、Cursor、Windsurf、Gemini CLI（只读项目级指令文件） | B 指令指针 | `python install.py --target all --dest .` |
| Zed、Continue、Cherry Studio、Claude Desktop（MCP 客户端） | C MCP 服务器 | `python install.py --print-mcp` |
| 网页聊天、不能读文件的模型 | D 纯对话 | 贴 `adapters/generic/BOOTSTRAP.md` |

`--target all` = A + B 全部。C 只需在客户端加一段 JSON。**四条路共享同一份 `scripts/` 与 `references/`。**

---

## 2. 共同前提

| 项 | 要求 | 检查 |
|---|---|---|
| Python | ≥ 3.9，仅标准库 | `python scripts/pangu.py doctor` |
| 浏览器（仅 3D） | 支持 WebGL | 打开 `examples/helikon/preview.html` 能转即可 |

Windows 上若 `python` 不可用，用 `py -3` 或解释器绝对路径。**MCP 配置里必须写绝对路径**，因为客户端的工作目录不可控。

---

## 3. 各宿主详解

### 3.1 Claude Code / Claude.ai Skills

**机制**：启动时扫描技能目录，读每个 `SKILL.md` 的 `description` 建立索引；命中时把正文注入上下文，`references/` 由模型按需再用工具读。

**安装**：

```bash
python install.py --target skill                    # → ~/.claude/skills/pangu
# 或指定位置
python install.py --target skill --skill-dir "D:/agents/skills/pangu"
```

**要点**：

- 目录名与 frontmatter `name` 保持一致（都是 `pangu`）。部分实现以目录名派生技能名，不一致会导致调用不到
- 技能名用 ASCII（`pangu` 而非 `盘古`），避免校验器拒绝；中文名保留在正文 H1 与 `metadata.title` 里
- `description` 决定了"什么时候被想起"。它是唯一在未加载时可见的内容，所以必须写清**触发场景**，而不只是功能

**验证**：新开一个会话，说"帮我造一个双恒星世界的物理法则"，看它是否读 `SKILL.md`。

### 3.2 OpenAI Codex CLI / Amp / Jules / 通用 AGENTS.md

**机制**：每轮把项目根的 `AGENTS.md`（及子目录同名文件）注入上下文。没有"技能索引"，只有"常驻指令"。

**安装**：

```bash
python install.py --target agents --dest .
```

**要点**：

- 指针只有 21 行，成本可以接受；但仍要求它**先读 `SKILL.md` 正文**，指针本身不含方法论
- `AGENTS.md` 常被用户自己的项目说明占用。安装器用标记块追加，不覆盖既有内容：

  ```
  <!-- pangu:begin -->
  ...
  <!-- pangu:end -->
  ```

  重复安装只会替换块内内容，不会堆出第二份

### 3.3 Cursor

**机制**：`.cursor/rules/*.mdc`，frontmatter 的 `description` / `globs` / `alwaysApply` 决定触发方式。

**安装**：

```bash
python install.py --target cursor --dest .
```

**要点**：

- 采用 `alwaysApply: false` + `description` 触发，避免常驻占用上下文
- `.mdc` 里引用 `SKILL.md` 用**绝对路径**（安装时由 `{{PANGU_ROOT}}` 替换），因为 Cursor 的工作目录随打开的文件夹变化
- 若发现不触发，把 `alwaysApply` 改成 `true` 试一次，确认是触发问题还是加载问题

### 3.4 Windsurf

**机制**：`.windsurf/rules/*.md`，frontmatter `trigger` 支持 `manual` / `always_on` / `model_decision` / `glob`。

**安装**：

```bash
python install.py --target windsurf --dest .
```

**要点**：这里用 `trigger: model_decision`（由模型判断是否相关）。规则文件有长度上限，所以指针刻意写短，正文放在 `SKILL.md` 里按需读。

### 3.5 Gemini CLI

**机制**：项目根 `GEMINI.md` 常驻注入。

**安装**：

```bash
python install.py --target gemini --dest .
```

**要点**：与 `AGENTS.md` 同构，用标记块幂等追加；若项目已有 `GEMINI.md`，内容不会被破坏。

### 3.6 MCP 客户端（Zed / Continue / Cherry Studio / Claude Desktop）

**机制**：客户端启动时拉起服务器进程，通过 stdio 交换 JSON-RPC。工具以 schema 形式暴露给模型。

**配置**：

```bash
python install.py --print-mcp
```

把输出的 JSON 合并进客户端配置：

```json
{
  "mcpServers": {
    "pangu": {
      "command": "C:/path/to/python.exe",
      "args": ["/absolute/path/to/pangu/adapters/mcp/pangu_mcp.py"],
      "env": {}
    }
  }
}
```

配置文件位置：Claude Desktop 为 `claude_desktop_config.json`；Cursor 为 `~/.cursor/mcp.json`；Zed 为 `settings.json` 的 `context_servers`；Continue 为 `config.yaml`。

**手动验证**（不依赖客户端）：

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python adapters/mcp/pangu_mcp.py
```

应返回 7 个 tool 的 JSON。若无输出，先看 stderr（日志只走 stderr，不会污染协议）。

**七个工具**：

| tool | 用途 |
|---|---|
| `pangu_guide` | 读方法论（`section` 可分段：skill / axes / axioms / search / audit / schema） |
| `pangu_doctor` | 环境自检 |
| `pangu_init` | 生成 world.json 骨架 |
| `pangu_validate` | 自洽性校验与打分 |
| `pangu_preview` | 生成 3D 预览页 |
| `pangu_export` | 导出世界档案 |
| `pangu_axioms` | 抽取反常识积木 |

### 3.7 纯对话（无文件、无工具）

贴 `adapters/generic/BOOTSTRAP.md` 全文，再补一句种子。

**这是降级路径**：没有脚本，意味着没有机检、没有 3D、没有真实的派生量计算。自洽性完全依赖模型自审。适合快速脑暴，不适合交付。能读文件时**不要**用这条。

---

## 4. 接入一个新 harness

只需三步，不必改核心：

1. **判断加载机制**：常驻指令（类似 `AGENTS.md`）？带描述的规则文件（类似 `.mdc`）？还是 MCP？
2. **写指针**：从 `adapters/cursor/pangu.mdc` 复制一份，保留 `{{PANGU_ROOT}}` 占位符，改写 frontmatter，正文保持三件套——绝对路径、"先读 SKILL.md"硬指令、四条纪律摘要。
3. **加 target**：在 `install.py` 的 `TARGETS` 与 `install_pointer()` 里各加一个分支，并在 `adapters/README.md` 的兼容矩阵补一行。

**不要**复制 `SKILL.md` 正文进适配器。入口层一旦有第二份方法论，就会漂移。

---

## 5. 排错速查

| 现象 | 最可能的原因 | 处理 |
|---|---|---|
| agent 完全不提盘古 | 文件位置/命名不符合宿主约定 | 对照 §3 的路径；`AGENTS.md` 必须在项目根 |
| 触发了但行为像"通用写作" | 只读了指针，没读正文 | 指针里已有硬指令；检查宿主是否截断了上下文。可改成分步：先让它"读 SKILL.md 并复述三律" |
| `No module named world_schema` | 从错误目录执行 CLI | `pangu.py` 会自行把 `scripts/` 加入 `sys.path`，此错误通常说明调用的不是本项目的 `pangu.py` |
| `python` 不是内部命令 | PATH 未配 | 用 `py -3` 或绝对路径 |
| MCP 客户端显示 server 启动失败 | 配置里用了相对路径 / 解释器路径错 | 两处都必须绝对路径；先跑 §3.6 的手动验证 |
| MCP 有 tool 但调用无输出 | 服务器把日志写进了 stdout | 本项目已强制日志走 stderr；若你改过代码，检查是否 `print` 了调试信息 |
| Cursor/Windsurf 不触发 | `description` 太泛或 `globs` 不匹配 | 把 `alwaysApply` 临时设 `true` 定位问题 |
| 3D 页面白屏 | CDN 不可达或 WebGL 被禁 | 页面有离线降级视图；检查浏览器控制台 |
| 安装后目录里出现 `skill/skill/skill/...` | 递归复制缺陷 | 1.0 已修复：目标位于技能源内部会被拒绝。清理后重装 |

---

## 6. 一份技能，多处安装，如何保持同步

- **推荐符号链接**：`python install.py --target skill --link`（Unix/macOS 直接生效；Windows 需开发者模式或管理员权限，失败会自动回退为复制）
- **复制模式**下，改完源目录后重新执行一次 `--target skill` 即可覆盖（不含 `__pycache__` / `out` / `dist`）
- 指针文件天然同步：它们只有路径，没有正文

---

## 7. 设计取舍备忘

| 取舍 | 选择 | 原因 |
|---|---|---|
| 技能名 ASCII vs 中文 | ASCII `pangu`，中文留在正文 | 兼容最严的校验器；中文名不影响人类理解 |
| 指针复制正文 vs 只放路径 | 只放路径 | 多份正文必然漂移 |
| MCP 依赖官方 SDK vs 手写协议 | 手写 | 用户环境常常装不了包；只用得到 4 个方法 |
| MCP 直连内核 vs 转调 CLI | 转调 CLI | CLI 是唯一行为源，避免双份逻辑 |
| 无文件宿主怎么办 | 提供压缩版提示词，明确标注降级 | 有总比没有好，但不能假装它等价 |
