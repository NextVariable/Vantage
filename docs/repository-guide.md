# 仓库目录说明 · Repository guide

使用者从 [README](../README.md) 或[中文说明](../README.zh-CN.md)开始。GitHub 按路径展示文件，以下按用途解释目录。

| 用途 / Purpose | 位置 / Location |
| --- | --- |
| 使用与安装 / Getting started | `README.md`、`README.zh-CN.md` |
| 智能体接入 / Agent integration | `SKILL.md`、`agents/`、`references/` |
| 运行代码 / Runtime code | `src/` |
| 配置与数据契约 / Configuration and contracts | `config/`、`schemas/` |
| 示例与说明 / Examples and documentation | `docs/` |
| 测试、评测与检查 / Tests, evaluations and checks | `tests/`、`evals/`、`scripts/`、`.github/workflows/` |
| 打包 / Packaging | `pyproject.toml`、`setup.py`、`MANIFEST.in` |
| 贡献、版本与许可 / Contributions, changes and license | `CONTRIBUTING.md`、`CHANGELOG.md`、`LICENSE` |

详细职责见[架构说明](architecture.md)。本地研究输出放在被忽略的 `runs/`，使用者无需逐个浏览工程目录。

See [architecture](architecture.md) for detailed ownership. Local research outputs belong in ignored `runs/`; users do not need to browse every implementation directory.

## Branch audit · 分支审计

Remote refs checked on 2026-11-25, with `main` at `d9eba3c`. GitHub
returned no open pull requests. A repository-wide reference scan found
historical mentions in the release, audit and specification records.
Public search did not surface external links to the four historical
branches. Unindexed links, forks and private integrations cannot be ruled out.

| Remote branch | Audited tip | Unique commits relative to main | Proposed archive reference |
| --- | --- | ---: | --- |
| `release/vantage-1.0-beta` | `d9eba3c` | 0 | Existing `v1.0.0b1` points to the same commit. |
| `audit/synthesis-runtime-2` | `e59f4f1` | 0 | `archive/audit-synthesis-runtime-2` |
| `dev/trae-research-quality` | `3576cc8` | 0 | `archive/trae-research-quality` |
| `dev/vantage-1.0` | `102fdf3` | 0 | `archive/vantage-1.0-development` |
| `dev/vantage-1.1-global-sources` | `2f54628` before this cleanup | 10 at audit start | Active branch. |
| `main` | `d9eba3c` | 0 | Default branch. |

The four historical tips are ancestors of the audited `main`. Keep both
active branches. After approval, recheck tips, PRs and known consumers,
then use annotated tags at the three distinct historical tips and switch
any remaining branch links to a tag or commit permalink before retiring
branches. Preserve existing release tags and the Beta checkout.

The [published Beta release](https://github.com/NextVariable/Vantage/releases/tag/v1.0.0b1)
already uses the fixed tag. The README on the unchanged default branch and in
the tagged Beta checkout still gives a branch-based installation command,
so keep `release/vantage-1.0-beta` as a compatibility reference until the
default documentation is updated and users of older instructions can find the
tag-based procedure. The updated READMEs in the 1.1 branch use the fixed tag.
This audit creates no archive tag and deletes no ref.

## Privacy and third-party material · 隐私与第三方内容

- Keep raw runs, working ledgers, caches, build outputs and environment files
  local. The tracked fixtures, public research excerpts and recorded example
  traces are deliberate artifacts. Review new excerpts for source rights and
  redact private data before promotion to a public example.
- Repository code is [MIT-licensed](../LICENSE). Direct runtime dependencies
  declare MIT in the checked distribution metadata: `jsonschema`,
  `referencing`, `rfc3339-validator`, and `PyYAML`. Installers resolve them
  separately. The package does not bundle their code or the optional
  [yt-dlp executable](https://github.com/yt-dlp/yt-dlp#license).
- External software keeps its upstream terms. Source text, reviews, captions,
  and account access follow their own terms, independent of Vantage's MIT
  license. See [source authorization](source-authorization.md).
