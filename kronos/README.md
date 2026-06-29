# Kronos-mini — A股K线预测引擎

## 模型
- **Kronos-mini** | 清华大学 | AAAI 2026
- 参数: 4.1M | 上下文: 2048 | 训练数据: 45+全球交易所
- 输入: OHLCV K线序列
- 输出: 未来K线走势预测

## 部署
```bash
cd ~/dao-analyst/kronos
bash install.sh    # 安装PyTorch + 下载模型(~50MB)
```

## 使用
```python
from kronos.predict import KronosPredictor
k = KronosPredictor()
forecast = k.predict(ohlcv_data, steps=5)
```

## DAO集成
- 盘前: 输入近期K线 → 预测当日走势
- 选股: 批量预测候选股 → 排序优选
- 风控: 预测回撤风险 → 提前预警

## 资源
- 模型: huggingface.co/NeoQuasar/Kronos-mini
- 论文: arxiv.org/abs/2508.02739
- 硬件: Apple M4 MPS加速 | 24GB内存 | CPU推理毫秒级
