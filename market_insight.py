#!/usr/bin/env python3
"""市场洞察 — 金十数据快讯聚合"""
import sys, os, json, requests
from datetime import datetime

def get_flash_news(limit=10):
    """获取金十快讯"""
    try:
        r = requests.get('https://flash-api.jin10.com/get_flash_list?channel=-8200&vip=1',
            headers={'User-Agent':'Mozilla/5.0','x-app-id':'bVBF4FyRTn5NJF5n','x-version':'1.0.0'}, timeout=8)
        data = r.json()
        flashes = data.get('data',[])
        news = []
        keywords = ['A股','沪指','深指','央行','降息','降准','LPR','MLF','证监会','IPO','注册制',
                   '板块','涨停','跌停','成交额','北向','南向','ETF','回购','增持','减持']
        for f in flashes:
            content = f.get('data',{}).get('content','')
            time_str = f.get('data',{}).get('time','')
            # 过滤A股相关
            if any(k in content for k in keywords):
                news.append({'time': time_str, 'content': content})
            if len(news) >= limit: break
        return news
    except Exception as e:
        return []

def get_market_insight():
    """市场洞察摘要"""
    news = get_flash_news(5)
    if not news:
        return None
    
    lines = ['📡 市场要闻']
    for n in news:
        lines.append(f'  · {n["content"][:80]}')
    return '\n'.join(lines)

if __name__ == '__main__':
    insight = get_market_insight()
    if insight:
        print(insight)
    else:
        print('📡 暂无要闻')
