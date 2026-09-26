# 创建

初始化一个技能仓：本地脚手架 + 在 `awam-skills` 组织下建**空仓**并设 remote。不 push 内容。

## 前置收集

向用户确认（已给的可跳过）：

1. **skill `name`**（kebab-case，将写入 SKILL frontmatter）
2. **一句话 description**（写入 frontmatter；发布时也可作 repo description / overrides 初值）
3. **布局**：默认扁平；仅当有根目录 CLI / 多技能 / 要 CONTEXT 时用嵌套
4. **本地路径**：用户指定的空目录或将创建的目录（须可 `git init`）

推导 `repo_name`：`name` 已以 `-skill` 结尾则用 `name`，否则 `<name>-skill`。

## 步骤

1. **目录**：若路径不存在则创建；`git init`（已是 git 仓则跳过）。默认分支 `main`。
2. **写入最小文件**：
   - **扁平**：根目录 [templates/SKILL.md](../templates/SKILL.md)（替换 `name` / `description`）+ [templates/gitignore](../templates/gitignore) → `.gitignore`
   - **嵌套**：`skills/<name>/SKILL.md`（同上模板）+ 根 `.gitignore`；**不要**预置空 `CONTEXT.md` / `docs/agents` / `evals`，除非用户当次明确要求
3. **awam-git**：按已安装的 `awam-git` Skill，在技能仓根写入 `.cursor/rules/git-commit.mdc` 与 `.cursorrules`。推荐 scope：`skills`、`doc`（有脚本再加 `scripts`）。
4. **建远程空仓**（需 `gh` 已登录且对组织有权限）：

   ```bash
   gh repo create "awam-skills/<repo_name>" --public --description "<description>"
   git remote add origin "https://github.com/awam-skills/<repo_name>.git"
   ```

   若仓已存在：只补 remote（或核对 URL），不要删远程内容。
5. **停在这里**：不要 `git push`。告知用户：实现技能内容后，用本 Skill 的**发布**流程收尾。

## 校验

- [ ] 本地存在 `SKILL.md`（扁平在根 / 嵌套在 `skills/<name>/`）
- [ ] `.gitignore`、awam-git 两套提交规范已落盘
- [ ] `origin` 指向 `awam-skills/<repo_name>`
- [ ] 未 push；未改索引仓 `skills.overrides.json`
- [ ] 未创建 ClawHub / `skill.json` 等市场文件

## 模板注意

- frontmatter 含 `name`、`description`；默认加 `disable-model-invocation: true`（仅用户点名时加载）。若用户要求可被模型自动调用，再去掉该字段。
- description 用第三人称、含 WHAT + WHEN；可中文。
- 正文只写该技能自己的步骤；不要塞通用「如何写好 Skill」教程。
