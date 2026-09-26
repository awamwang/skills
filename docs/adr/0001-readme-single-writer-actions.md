# ADR-0001: 索引 README 由 Actions 单写

## Context

发布技能时既要更新 `skills.overrides.json`，又要刷新 `README.md`。本地跑 `sync_skills.py` 与 push overrides 触发的「Sync Skills Catalog」会争写同一文件。

## Decision

索引仓 `README.md` 只由 GitHub Actions 写入。发布流程更新 Topics、description、overrides 后 push；**不**在本地执行同步。

## Consequences

发布后 README 可能短暂滞后，直到 Actions 跑完。需要立刻看目录时用 `workflow_dispatch` 手动触发，仍不要本地双写。
