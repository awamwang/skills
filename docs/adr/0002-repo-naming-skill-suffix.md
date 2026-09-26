# ADR-0002: 新技能仓命名带 `-skill` 后缀

## Context

组织内既有裸名仓（如 `github-organize`）也有 `-skill` 后缀仓（如 `windows-autostart-skill`）。新仓需要统一可预期的命名。

## Decision

新建仓名：skill `name` 已以 `-skill` 结尾则用 `name`；否则用 `<name>-skill`。既有仓不回溯改名。

## Consequences

新仓名一眼可辨；与历史裸名并存。Agent 创建时按上述规则推导，不再默认「仓名 = skill name」。
