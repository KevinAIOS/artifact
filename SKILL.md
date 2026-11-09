---
name: artifact
description: Manage durable work objects as Artifacts (Name+Reference), attach open ontology such as class and signal, create or update before during or after work, and query by properties. Use when the user mentions artifact, 类, 信号, ontology, registering or scanning work objects, binding real-world feedback, or persistent object management across chat history.
---

# Artifact

可插拔能力：把工作世界里值得独立管理的对象变成 **Artifact**，再挂可演化的性质（ontology）。不规定必须先登记才能干活。

加载策略（对齐 Skill／MCP 本体，勿每轮塞整包）：
- **常驻（harness／每轮）**：本 skill 的 name+description；四工具 schema；由代码维护的**类名短清单**（仅名，不含实例明细）。
- **触发后读本文件**：底座定义、工具契约、何时用（辅助非强制）。
- **按需再读**：[references/product-layer.md](references/product-layer.md)（价值说法、类／信号预置配方、信号 one-shot）。

## Install

用户说「装 artifact skill」后，由安装挂钩完成拷贝与 CLI／工具注册，而不是只让模型「每轮去读文件」。

- 包根：本目录（或发行包 `artifact-skill/`）。
- 一键本地装：`bash scripts/install.sh`（默认 `--user`）。
- 表面差异与下一步：见 [README.md](README.md)；Claude Code → [harness/claude-code.md](harness/claude-code.md)；Codex → [harness/codex.md](harness/codex.md)；Grok Bot 服务端 → [harness/grok-bot.md](harness/grok-bot.md)。
- 工具入口：`artifact` CLI（`scripts/artifact_cli.py`）或 `mcp/server.py`（stdio JSON-RPC 风格 stub）。
- 类名清单注入：`artifact classes --inject`（或 `python3 scripts/harness_inject.py --format prompt`），由 harness 每轮调用，勿让模型自己维护名单。
- Store：`ARTIFACT_STORE` → 已有 `./.artifact/store.json` 或 `--project` → 否则 `~/.artifact/store.json`。

## 底座

### 定义

- **Artifact**＝可独立指认和管理的工作对象。核心只有 **Name + Reference**。
- **Name**：人或 AI 怎么称呼它。
- **Reference**：以后能稳定指回同一对象的依据（路径、URL、id、内容范围、查询条件、或 `art://…` 占位）。选 Reference 的法则只有一句：**优先最不容易漂、最好重新解析的那种**；形态由模型按对象判断，不锁死唯一格式。
- **实／虚**：有可解析内容或外部落点的是实的；账号、好友等尚不能／不必用正文生成的，先建虚的（Name + `art://` 占位），有真地址再绑。实／虚与事前／事中／事后无关。
- **Ontology**：挂在 Artifact 上的可扩展性质与关系（类、信号、特征…）。不锁死字段；需要时可自挂新性质。类≠本体；本体始终是 Artifact。
- Name 与 Reference **一起创建**，禁止只有 Name、Reference 后补导致无法指认。

### 工具（四个）

实现可走本包 CLI／MCP stub；调用语义如下。

1. `upsert_artifact` — 建或改 Name+Reference（实／虚均可）。
2. `resolve_artifact` — 按引用找回。
3. `attach_ontology` — 挂或改性质（如 class、signal；名与值开放）。
4. `query_artifacts` — 按性质／名／引用检索。

不做：默认全量 Artifact 列表进上下文；强制工作流；把类抬成本体。`link_artifacts`（对象间语义边）第二批再上。

### 类名清单（代码，非模型）

- 由 harness／代码维护当前项目「有哪些类」的短名单，每轮 agent loop 注入。
- **不要**让模型自己维护或每轮全量扫来填这份名单。
- 名单只含类名；某类下有哪些实例、信号细节，需要时用 `query_artifacts`。

## 何时用（辅助，非强制）

用户自然语言可随时自定义；下列是建议，不是必经步骤。

- **创建**：一知道对象值得独立管，就 `upsert_artifact`（可先虚占位）；生成中或生成完再补全 Reference。
- **维护**：改名、换引用、`attach_ontology`。
- **使用**：`resolve`／`query` 后再操作；不把完整对象图塞进提示。
- **事后**：可扫历史／轨迹找高价值对象再建或补挂；可实可虚；可先建议再确认，或按用户口气直接建——以用户当轮指示为准。
- **事中**：知道要独立管就先占位；纯写完再挂也可以（如标题这类小对象）。

未声明关心哪些性质时，可先挂常见性质「类」「信号」——详见产品层；搜／改仍走上述四工具。

## 不做

- 不要求先登记才能干活。
- 不把类／信号写成唯一合法 ontology。
- 不每轮加载产品层全文或全量 Artifact。
