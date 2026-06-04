#!/usr/bin/env python3
"""市场情绪 V1.0 — 北向资金+涨跌比+涨停家数"""
import sys, os, json, urllib.request, ssl
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_market_sentiment():
    """评估市场情绪: 🟢积极 🟡中性 🔴谨慎"""
    from datetime import datetime
    now = datetime.now()
    hour = now.hour * 100 + now.minute
    # 盘后无法判断情绪，默认中性
    if hour < 930 or hour > 1500:
        return "⚪盘后", "非交易时段,默认允许交易"
    try:
        # 涨跌比 (新浪)
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=80&sort=changepercent&asc=0&node=hs_a&symbol="
        req = urllib.request.Request(url, headers={"Referer":"https://finance.sina.com.cn","User-Agent":"Mozilla/5.0"})
        stocks = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("gbk"))
        
        up = sum(1 for s in stocks if float(s.get('changepercent',0)) > 0)
        down = sum(1 for s in stocks if float(s.get('changepercent',0)) < 0)
        limit_up = sum(1 for s in stocks if float(s.get('changepercent',0)) >= 9.8)
        limit_down = sum(1 for s in stocks if float(s.get('changepercent',0)) <= -9.8)
        
        ratio = up / max(down, 1)
        
        if ratio >= 2 and limit_up >= 5:
            return "🟢积极", f"涨跌比{ratio:.1f} 涨停{limit_up}家 适合满仓"
        elif ratio >= 1 and limit_up >= 3:
            return "🟡中性", f"涨跌比{ratio:.1f} 涨停{limit_up}家 半仓操作"
        else:
            return "🔴谨慎", f"涨跌比{ratio:.1f} 跌停{limit_down}家 轻仓观望"
    except:
        return "⚪未知", "数据获取失败"

if __name__ == "__main__":
    sentiment, detail = get_market_sentiment()
    print(f'{sentiment} {detail}')
