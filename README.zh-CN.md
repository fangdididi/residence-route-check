# 居留路线核查（Residence Route Check）

[English](README.md) | **简体中文**

一个智能体技能，把“我们能合法搬到哪儿去？”变成一张注明日期的路线核查表，适用于个人或一家人。每条候选居留路线（数字游民、技术工作、留学转工作、创业自雇、被动收入、投资居留）都按同样的五道关来过，每条关键规则都必须对应近期读过的官方页面，最后给出明确结论，并列出能改变结论的具体变化、待核实事项和时间点。

> 本技能不构成法律、税务或移民建议。它帮你整理事实、提前发现问题；最终请以官方页面为准，案情复杂时请咨询持证专业人士。

## 为什么需要它

大多数搬家失败或延误，并不是因为选错了国家，而是因为一些本来可以提前核对的小事：

- 护照不在这条路线的国籍名单上；
- 收入门槛按家庭计算、按税前口径、需要 6 个月证明，而不是 3 个月；
- 无犯罪证明在预约前就过期了；
- 这条路线不能续签也不能转换，对想拿永居的人来说是死胡同；
- 第一次住得太久，不知不觉变成了当地税务居民。

居留路线核查让智能体在你为翻译、律师或机票付钱之前，把这些问题先找出来。

## 功能

- **固定顺序的五道关：** 护照、资金、条件、时间、目标。
- **四种诚实的结论：** 现在可行、待核实、需改变后可行、走不通，每种都附上理由。
- **证据纪律：** 关键结论必须有注明读取日期的官方来源；来源过期、或读取后规则有变，都会被自动标出。
- **把资金算对：** 带压力折扣的汇率换算、家属加成、年度门槛换算月度、税前税后口径不一致提醒、证明月数、存款最低要求。
- **文件倒计时：** 每份文件最早从哪天开具才不会过期、最晚哪天必须开始办才来得及，都从递交日倒推。
- **实际停留天数：** 按自然年和滚动 12 个月两种口径统计天数，对照每个国家的税务居民门槛，给出越线日期。
- **按目标排序：** 按最快永居、最快入籍，或（试住时）最早可递交来排序路线。
- **零依赖：** 一个只用标准库的 Python 脚本，附 54 个测试。

## 安装

把整个文件夹复制到你的智能体读取技能的位置。

| 智能体 | 放置位置 |
|---|---|
| Claude Code | `~/.claude/skills/residence-route-check/`（个人）或 `.claude/skills/residence-route-check/`（项目） |
| Codex CLI | `~/.codex/skills/residence-route-check/`，或在 `AGENTS.md` 中引用 `SKILL.md` |
| Cursor | `.cursor/skills/residence-route-check/`，或用项目规则指向 `SKILL.md` |
| 其他智能体 | 把 `SKILL.md`（或 `SKILL.zh-CN.md`）作为指令加载，并让它能运行 `scripts/routecheck.py` |

```bash
git clone https://github.com/fangdididi/residence-route-check.git ~/.claude/skills/residence-route-check
```

脚本只需要 Python 3.9 或更高版本。

## 使用方法

直接用自然语言告诉智能体，例如：

- “我们是两个大人一个孩子，中国护照，远程工作月收入大约 3.6 万人民币。明年夏天想搬去欧洲，哪些居留路线真的可行？”
- “帮我看看博客上这个数字游民签证适不适合我，以及要去官网核实什么。”
- “如果我想三月递交，无犯罪证明应该什么时候开？”

智能体会一次性问清家庭情况，去读官方页面，写好案例文件，然后运行脚本：

```bash
python3 scripts/routecheck.py template > case.json      # 生成模板
python3 scripts/routecheck.py check case.json --out route-sheet.md
python3 scripts/routecheck.py check case.json --json     # 机器可读输出
```

## 示例

`examples/family-of-three.json` 使用的是虚构的国家和数字。核查表节选：

| 路线 | 结论 | 原因 |
|---|---|---|
| Eastvale 技术工作卡 | 需改变后可行 | 需要工作 offer；扣除汇率压力后每月差 283 欧元；资格页面是在规则变更前读的 |
| Northland 远程工作居留 | 需改变后可行 | 还要补 2 个月收入证明；余量只有 11%；保险未确认 |
| Southmark 数字游民签证 | 走不通 | 护照不在名单上；到期只能离开；唯一来源是博客 |

核查表还显示：六月到十二月的停留会在 12 月 1 日越过自然年 183 天门槛。完整输出见 `examples/family-of-three.sheet.md`。

## 案例文件一览

| 部分 | 填什么 |
|---|---|
| `as_of`、`stale_days`、`headroom_pct` | 核查日期、来源允许的最长时效、希望保留的收入余量 |
| `rates` | 各币种一单位折合统一基准币的值，并注明汇率出处 |
| `household` | 护照、成年人数、孩子数、收入（金额、币种、税前/税后、证明月数）、存款、目标、计划搬家日期、汇率压力折扣 |
| `routes[]` | 国籍名单、收入和存款要求、其他条件（已满足/未满足/未知，能否改变）、到期去向、永居和入籍年限、提前递交天数、来源 |
| `documents[]` | 文件名、哪些路线需要、准备天数、有效天数、已开具的日期 |
| `trips[]`、`tax_rules[]` | 计划的停留，以及每个国家的天数门槛和计算口径 |

## 文件结构

```
residence-route-check/
├── SKILL.md                 # 技能说明（英文）
├── SKILL.zh-CN.md           # 技能说明（中文）
├── README.md                # 英文说明
├── README.zh-CN.md          # 本文件
├── LICENSE
├── scripts/
│   └── routecheck.py        # 五道关、文件倒计时、天数统计、Markdown/JSON 输出
├── examples/
│   ├── family-of-three.json       # 示例案例（虚构数据）
│   └── family-of-three.sheet.md   # 生成的核查表
└── tests/
    └── test_routecheck.py   # 54 个单元测试和端到端测试
```

运行测试：`python3 -m unittest discover -s tests`。

## 许可证

MIT，见 [LICENSE](LICENSE)。
