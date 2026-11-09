# Codex 挂钩

与 Claude Code 共用 `scripts/install.sh`：

1. 拷到 `~/.agents/skills/artifact/`
2. `~/.local/bin/artifact`
3. `--write-snippets` → 刷新 `~/.agents/AGENTS.md` 标记块

## 类名清单

```bash
artifact classes --inject
artifact --project classes --inject
```

## Store

同 README：`ARTIFACT_STORE` → 项目 `.artifact/store.json` → `~/.artifact/store.json`。

## 冒烟

```bash
bash scripts/install.sh --write-snippets
export PATH="$HOME/.local/bin:$PATH"
artifact --project upsert --name smoke --reference art://smoke
# 重启 Codex
```
