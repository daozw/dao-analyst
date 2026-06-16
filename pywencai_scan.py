#!/usr/bin/env python3
"""问财智能选股 — 自然语言一键筛选,集成到DAO监控池"""
import json, os, sys
from datetime import datetime

STATE_FILE = os.path.expanduser("~/dao-analyst/data/state/pywencai_candidates.json")

# 过滤规则: 排除创业板/科创板/北交所
def _valid(code):
    return not any(code.startswith(p) for p in ('300','688','8'))

def band_candidates():
    """波段候选: 涨幅1-5%,量比>1.5,换手3-15%,PE<50,主板非ST"""
    from pywencai import get
    df = get(query='涨幅1到5个点 量比大于1.5 换手率3到15 市盈率小于50 主板 非ST', loop=True)
    codes = []
    for _, row in df.iterrows():
        c = row['股票代码'].replace('.SZ','').replace('.SH','')
        if _valid(c):
            codes.append(c)
    return codes

def board_candidates():
    """打板候选: 涨幅5-9.5%,量比>2,主板非ST"""
    from pywencai import get
    df = get(query='涨幅5到9.5个点 量比大于2 换手率小于25 主板 非ST', loop=True)
    codes = []
    for _, row in df.iterrows():
        c = row['股票代码'].replace('.SZ','').replace('.SH','')
        if _valid(c):
            codes.append(c)
    return codes

def scan_and_save():
    """运行扫描并保存结果"""
    result = {
        'time': datetime.now().isoformat(),
        'band': [],
        'board': [],
        'note': ''
    }
    
    try:
        result['band'] = band_candidates()
        result['note'] += f'波段{len(result["band"])}只 '
    except Exception as e:
        result['note'] += f'波段失败:{e} '
    
    try:
        result['board'] = board_candidates()
        result['note'] += f'打板{len(result["board"])}只'
    except Exception as e:
        result['note'] += f'打板失败:{e}'
    
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(result, f, ensure_ascii=False)
    
    return result

if __name__ == '__main__':
    r = scan_and_save()
    print(f"✅ {r['note']}")
    print(f"波段: {r['band'][:10]}{'...' if len(r['band'])>10 else ''}")
    print(f"打板: {r['board'][:10]}{'...' if len(r['board'])>10 else ''}")
