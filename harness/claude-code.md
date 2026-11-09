# Claude Code 挂钩

## 安装

```bash
bash scripts/install.sh --write-snippets
export PATH="$HOME/.local/bin:$PATH"
```

脚本会：拷到 `~/.claude/skills/artifact/`；装 `~/.local/bin/artifact`；初始化 `~/.artifact/store.json`；刷新 `~/.claude/CLAUDE.md` 里 `# BEGIN ARTIFACT SKILL` 块。

## 每轮类名注入

**代码维护，勿让模型自己扫名单。** 回合开始：

```bash
artifact classes --inject
# 或项目内：
artifact --project classes --inject
```

Snippet 已写明；若 Claude Code 无自动钩子，至少按 CLAUDE.md 提示先跑再贴进上下文（弱挂钩）。

## Store

1. `ARTIFACT_STORE`
2. `./.artifact/store.json`（存在或 `--project`）
3. `~/.artifact/store.json`

## 工具

- CLI：`artifact upsert|resolve|attach|query|classes`
- MCP：`python3 ~/.local/share/artifact-skill/mcp/server.py`

## 冒烟

```bash
cd /path/to/repo
artifact --project upsert --name smoke --reference art://smoke
artifact --project attach --reference art://smoke --key class --value 示例类
artifact --project classes --inject
# 重启 Claude Code
```
