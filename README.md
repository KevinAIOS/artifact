# Artifact Skill

**Name + Reference** 工作对象协议：给 Claude Code、Codex、Grok Bot 等 Agent 一套可插拔的 Artifact 能力（建对象、挂类／信号等 ontology、按需查询）。

> Artifact 是可独立指认和管理的工作对象，不是「类」。类、信号是挂在 Artifact 上的性质。

## 解决什么问题

Agent 干活时产生文件、账号占位、帖子草稿……事后很难统一指认和对照现实反馈。Artifact skill 让模型：

- 用 **Name + Reference** 持久指认对象（实／虚均可）
- 事前声明、事中挂载、事后从轨迹补建
- 开放 **ontology**（预置「类」「信号」，也可自挂新性质）
- 用四个工具读写；类名短清单由代码注入，不塞全量对象进上下文

## 一分钟安装（Claude Code / Codex）

```bash
git clone https://github.com/KevinAIOS/artifact.git
cd artifact
bash scripts/install.sh --write-snippets
export PATH="$HOME/.local/bin:$PATH"

artifact upsert --name demo --reference art://demo
artifact attach --reference art://demo --key class --value example-class
artifact classes --inject   # 给 harness 的类名短清单
```

然后重启 Claude Code 或 Codex。细节：`harness/claude-code.md`、`harness/codex.md`。

项目隔离 store：

```bash
artifact --project upsert --name post --reference art://post-1
# → ./.artifact/store.json
# 或 export ARTIFACT_STORE=/path/to/store.json
```

## 工具

| 工具 | 作用 |
|------|------|
| `upsert_artifact` | 建／改 Name+Reference（可省略 reference → `art://<uuid>`） |
| `resolve_artifact` | 按引用／名／id 找回 |
| `attach_ontology` | 挂性质（class、signal…） |
| `query_artifacts` | 按性质／名检索 |
| `list_classes` | 类名短清单（harness 注入用） |

入口：`artifact` CLI，或 `python3 mcp/server.py`（stdio MCP stub）。

## 给模型看的定义（摘要）

见 `SKILL.md`。产品层（价值说法、类／信号配方）在 `references/product-layer.md`，**按需加载**，不要每轮塞整包。

## Grok Bot / 服务端聊天

聊天在服务器时，需：注册 MCP、每用户／项目 `ARTIFACT_STORE`、由 harness **每轮**注入类名清单。见 `harness/grok-bot.md`。

## 仓库结构

```
SKILL.md                 # Agent skill 正文
references/product-layer.md
scripts/install.sh       # 本地一键装
scripts/artifact_cli.py
scripts/harness_inject.py
mcp/server.py
harness/                 # 各表面挂钩说明
store/schema.json
```

## 状态

粗糙能跑：本地 CLI／MCP stub、项目 store、安装挂钩已通。信号「真拉数」、服务端自动每轮注入仍依赖宿主 harness。

## License

MIT
