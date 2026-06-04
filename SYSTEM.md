# DAO量化助手 V3.2 — 系统架构

> 最后更新: 2026-06-01 03:41

---

## 📦 模块分类

### 🔵 数据层 (5个)
| 模块 | 用途 | 数据源 | 积分 |
|------|------|------|:--:|
| `pipeline/fetcher.py` | 统一数据获取 | 腾讯+东财+通达信+雪球 | 0 |
| `free_screener.py` | 五源全市场筛选 | 同上+妙想(可选) | 0-1 |
| `points_tracker.py` | 积分消耗追踪 | mx_data/output目录 | 0 |
| `usage_monitor.py` | API用量监控 | 同上 | 0 |
| `social_heat.py` | 社交媒体热度 | 东财人气榜HTTP | 0 |

### 🟢 分析层 (4个)
| 模块 | 用途 | 输入 | 输出 |
|------|------|------|------|
| `pipeline/signals.py` | 信号+价位计算 | fetcher JSON | 6信号+8价位 |
| `sector_rotation.py` | 板块轮动分析 | mx-xuangu | 热度分级 |
| `volume_divergence.py` | 量价背离检测 | K线数据 | 背离信号 |
| `enhanced_screener.py` | 六维增强评分 | 多源数据 | 0-13评分 |

### 🟡 决策层 (4个)
| 模块 | 用途 | 核心算法 |
|------|------|------|
| `position_sizer.py` | 动态仓位管理 | 凯利×ATR×市场温度 |
| `risk_manager.py` | 统一止盈止损 | ATR+浮动+时间+大盘联动 |
| `swap_analyzer.py` | 切换收益对比 | 预期收益差+2%缓冲 |
| `portfolio_scheduler.py` | 持仓调度 | 当日有效+评分替换 |

### 🔴 执行层 (2个)
| 模块 | 用途 | 对接 |
|------|------|------|
| `mx_bridge.py` | 模拟交易桥接 | 妙想模拟账户(100万) |
| `backtest_multi.py` | 多策略回测 | backtrader本地 |

### 🟣 展示层 (3个)
| 模块 | 用途 | 输出 |
|------|------|------|
| `pipeline/render.py` | HTML渲染(3模式) | Tailwind手机优化 |
| `pipeline/run.py` | 管道编排器 | PNG长图 |
| `draw_report.py` | 个股报告(旧版) | PNG |
| `report_template.py` | 市场报告(旧版) | HTML→PNG |

### ⚙️ 自动化层 (5条Cron)
| Cron | 时间 | 调用 | 积分 |
|------|------|------|:--:|
| Policy-Scan | 08:30 | pipeline/run.py market | 0 |
| Morning-Brief | 09:00 | pipeline/run.py market | 0 |
| Intraday-Monitor | */15 | pipeline/run.py market | 0 |
| Evening-Review | 15:05 | pipeline/run.py nightly | 0 |
| Nightly-Brief | 23:00 | pipeline/run.py nightly | 0 |

---

## 📡 API分类

### 免费API (直接HTTP, 0积分)
| API | 用途 | 更新频率 | 可靠性 | 限制 |
|------|------|:--:|:--:|------|
| 腾讯行情 `qt.gtimg.cn` | 实时价/量/PE/换手 | 3-5秒 | ⭐⭐⭐⭐⭐ | 无 |
| 东财资金 `push2.eastmoney.com` | 主力资金流向 | T+1 | ⭐⭐⭐⭐ | 凌晨空 |
| 通达信K线 `mootdx` | OHLCV日K/分钟 | 实时 | ⭐⭐⭐⭐ | 需安装 |
| 雪球热榜 `xueqiu.com` | 社区热度排名 | 实时 | ⭐⭐⭐ | 需Cookie |
| 东财人气榜 `push2.eastmoney.com` | 关注度排名 | 实时 | ⭐⭐⭐ | 可能限流 |

### 妙想API (消耗积分)
| API | 用途 | 积分消耗 | 何时用 |
|------|------|:--:|------|
| mx-xuangu | 选股筛选 | 1/次 | 仅全市场初筛 |
| mx-data | 财务/行情数据 | 1/次 | 备选(已有免费替代) |
| mx-search | 新闻/公告搜索 | 1/次 | 深度研究时 |
| mx-zixuan | 自选股管理 | 1/次 | 添加/删除自选 |
| mx-moni | 模拟交易 | 1/次 | 实盘模拟 |

### 本地AI (0费用)
| 模型 | 用途 | 速度 | 何时用 |
|------|------|:--:|------|
| Qwen3 14B | 中文分析/报告 | 5-10秒 | 白天 |
| DeepSeek-R1 14B | 深度推理 | 60-120秒 | 复杂分析 |

---

## 🔄 工作流

### 盘前流程 (08:30-09:25)
```
Cron触发 → pipeline/run.py market
         → fetcher获取指数+热度
         → render渲染市场全景
         → 微信推送PNG
         
手动 → 查看波段池4只候选
     → 09:15集合竞价观察
     → 09:25确认买卖清单
```

### 盘中流程 (09:30-15:00)
```
Cron每15分钟 → pipeline/run.py market(轻量)
              → 仅异常推送
              → 无异常NO_REPLY

手动 → 波段池中符合条件→mx_bridge执行
     → 止损触发→无条件出局
     → 止盈触发→分批卖出
```

### 盘后流程 (15:05-23:00)
```
15:05 Cron → pipeline/run.py nightly
           → 全维度数据+人气榜
           → 微信推送PNG

23:00 Cron → pipeline/run.py nightly
           → 深夜情报站
           → 微信推送PNG
```

---

## 🗂️ 数据文件

```
~/tradingagents/
├── pipeline/          # 管道引擎(5文件)
├── data/
│   └── watchlist.json # 自选股分组
├── *.py               # 23个策略/分析模块
├── astock/            # TradingAgents A股版
├── rules.md           # 交易规则 V3.2

~/.cache/pipeline/     # API缓存(5分钟)
~/reports/             # 报告归档
~/mx_data/output/      # 妙想数据缓存
```

---

## 📊 监控面板

```
积分: 7/370 (1.9%)  |  Cron: 5/5就绪  |  模块: 23个
API可用: 腾讯✅ 通达信✅ 雪球✅ 东财⚠️ 妙想✅
Ollama: Qwen3✅ DeepSeek-R1✅
资金: ¥20,000  |  仓位: 动态0-100%
```
