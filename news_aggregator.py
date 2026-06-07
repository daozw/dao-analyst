#!/usr/bin/env python3
"""财经新闻聚合 — 证券时报+新浪+金十"""
import sys, os, json, requests, re
from datetime import datetime

def get_stcn_news():
    """证券时报网头条"""
    try:
        r = requests.get('https://www.stcn.com/', 
            headers={'User-Agent':'Mozilla/5.0'}, timeout=8)
        titles = re.findall(r'title="([^"]{8,60})"', r.text)
        # 过滤A股相关
        keywords = ['A股','沪指','深指','板块','涨停','跌停','IPO','注册制',
                   '证监会','央行','降息','降准','并购','重组','年报']
        a_share = [t for t in titles if any(k in t for k in keywords)]
        return a_share[:5]
    except:
        return []

def get_jin10_news():
    """金十快讯(A股相关)"""
    try:
        r = requests.get('https://flash-api.jin10.com/get_flash_list?channel=-8200&vip=1',
            headers={'User-Agent':'Mozilla/5.0','x-app-id':'bVBF4FyRTn5NJF5n','x-version':'1.0.0'}, timeout=8)
        data = r.json()
        flashes = data.get('data',[])
        keywords = ['A股','沪指','深指','央行','降息','降准','LPR','MLF','证监会',
                   'IPO','注册制','板块','涨停','跌停','成交额','北向']
        news = []
        for f in flashes:
            content = f.get('data',{}).get('content','')
            if any(k in content for k in keywords):
                news.append(content[:100])
            if len(news) >= 5: break
        return news
    except:
        return []

def get_market_news():
    """聚合所有源"""
    news = []
    
    stcn = get_stcn_news()
    if stcn:
        news.append('📰 证券时报')
        for t in stcn:
            news.append(f'  · {t}')
    
    jin10 = get_jin10_news()
    if jin10:
        news.append('📡 金十快讯')
        for t in jin10:
            news.append(f'  · {t}')
    
    return '\n'.join(news) if news else None

if __name__ == '__main__':
    news = get_market_news()
    if news:
        print(news)
    else:
        print('📡 暂无A股要闻')
