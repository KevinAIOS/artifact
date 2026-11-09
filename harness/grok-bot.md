# Grok Bot（服务端聊天）挂钩

Grok Bot 的会话与历史在**服务器**，不在用户本机 home。本地 `install.sh` 只覆盖 Claude Code／Codex。

## 已完成（Kevin 账号）

- Workflows 包：`/home/box/agent-data/workflows/artifact/`（与 `/workspace/artifact-skill/` 同步）
- **MCP 已注册**：命名空间 `user-artifact` / 服务器名 `artifact`
  - 工具：`upsert_artifact`、`resolve_artifact`、`attach_ontology`、`query_artifacts`、`list_classes`
  - Store：通过 connector 环境的 `ARTIFACT_STORE`（或项目路径）指向独立 JSON，勿共用开发者 `~/.artifact`
  - 冒烟：`list_classes` 已通过

## 平台仍须做（脚本做不到）

1. **Skill 发现／UpdateSkill**：由父代理或平台把 name+description 列入常驻发现（本 executor 不负责 UpdateSkill）。
2. **每轮类名清单自动注入**：在 agent loop 里由代码调 `list_classes` 或等价，把短名单拼进当轮上下文。  
   **没有平台改动时不会自动每轮注入**——模型可手动调 `list_classes`，或本地用 `artifact classes --inject` 弱挂钩。
3. **按用户／项目 store**：继续用 `ARTIFACT_STORE=/data/artifact/{user}/{project}/store.json`（或等价）；无需自建业务数据库。

## 现成 mcp.json 片段（给平台／父代理挂载用）

```json
{
  "mcpServers": {
    "artifact": {
      "command": "python3",
      "args": ["/home/box/agent-data/workflows/artifact/mcp/server.py"],
      "env": {
        "ARTIFACT_STORE": "/home/box/agent-data/artifact-stores/default/store.json"
      }
    }
  }
}
```

项目隔离示例：把 `ARTIFACT_STORE` 换成该项目路径，或设 `ARTIFACT_PROJECT=1` 且 cwd 为项目根（使用 `./.artifact/store.json`）。

## 建议挂载形态

```
Bot workflows:  …/workflows/artifact/SKILL.md
Tools:          MCP artifact (user-artifact)  ← 已挂
Inject each turn (仍缺平台钩子):
                list_classes → 短名单进上下文
Store:
                ARTIFACT_STORE=…/{user}/{project}/store.json
```

## 诚实边界

- 「用户说装 skill 就全自动」：需要平台安装器（拷 workflows + 注册 MCP + 挂 inject）。本包是被安装物。
- **自动每轮 inject**：Cursor／Grok Bot 核心 harness 未开放时，本包无法单方面改平台；最大可运行层＝MCP + skill 文 + CLI inject + 本文说明。
