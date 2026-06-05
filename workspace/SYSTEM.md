# SYSTEM.md — 系统架构文档

## 目录结构
```
~/dao-analyst/
├── pipeline/          # 核心交易引擎
│   ├── autotrade.py   # 波段策略 (MX, ¥20,000)
│   ├── xuanwu_trade.py # 打板策略 (华泰, ¥10,000)
│   ├── fetcher.py     # 数据获取 (腾讯+新浪+通达信)
│   ├── signals.py     # 6维信号评分
│   └── trade_notify.py # 微信通知队列
├── strategy/          # 策略配置
│   ├── band/          # 波段策略配置
│   ├── board/         # 打板策略配置
│   ├── growth/        # 增长策略配置
│   ├── value/         # 价值策略配置
│   └── shared/        # 共享层
├── board_*.py         # 打板雷达+竞价
├── hub_dispatcher.py  # 中枢分配+质量评分
├── auto_adjust.py     # 自动调仓
├── realtime_watch.py  # WebSocket实时监控
├── market_sentiment.py # 市场情绪
├── data/state/        # 运行时状态
└── data/watchlist.json # 股票池配置
```

## 关键技术栈
- 数据: 腾讯qt.gtimg.cn, 新浪finance.sina.com.cn, 通达信mootdx
- 交易: MX mkapi2.dfcfs.com, 华泰 a-share-paper-trading
- LLM: Ollama Qwen3 27B (本地)
- 调度: macOS crontab + OpenClaw Agent
- 监控: WebSocket push2.eastmoney.com

## 版本历史
- V3.1: 基础波段+打板
- V3.2: MX持仓感知+每日≤3只+动态总资金
- V3.3: 3万作战系统+质量评分+实时WebSocket+中枢分配
