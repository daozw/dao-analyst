#!/usr/bin/env python3
"""自动调仓 V1.0 — 根据信号自动管理波段池和价值池"""
import sys, os, json
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

WATCHLIST = os.path.expanduser('~/dao-analyst/data/watchlist.json')
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "auto_adjust.json")

from pipeline.fetcher import fetch
from pipeline.signals import analyze

def auto_adjust():
    """自动调整股票池"""
    wl = json.load(open(WATCHLIST))
    changes = []
    
    # ━━ 1. 波段池维护 ━━
    band = wl['groups'].get('band', {}).get('stocks', [])
    keep_band = []
    for s in band:
        d = fetch(s['code'], use_cache=False)
        if 'error' in d:
            keep_band.append(s); continue
        
        a = analyze(d)
        sig = a['g']
        
        # 连续3天信号<2 → 移出波段池
        if sig < 2:
            changes.append(f"🔴 波段池 {s['name']}({s['code']}) 信号{sig}/6 → 移入观察池")
            # 移入观察池
            watch = wl['groups'].setdefault('watch', {"name": "👀 观察池", "desc": "待确认信号", "stocks": []})
            if not any(x['code'] == s['code'] for x in watch['stocks']):
                watch['stocks'].append({"code": s['code'], "name": s['name'], 
                    "note": f"信号{sig}/6 · 从波段池移出"})
        else:
            keep_band.append(s)
    
    wl['groups']['band']['stocks'] = keep_band
    # ━━ 板块集中度检查 ━━
    from collections import Counter
    import json as json
    _sm = {}
    if os.path.exists(os.path.expanduser('~/dao-analyst/data/sector_map_v2.json')):
        _sm = json.load(open(os.path.expanduser('~/dao-analyst/data/sector_map_v2.json')))
    band = wl['groups'].get('band', {}).get('stocks', [])
    sec_count = Counter(_sm.get(s['code'],'综合') for s in band)
    for sec, cnt in sec_count.items():
        if cnt >= 4:
            changes.append(f"⚠️ 板块集中: {sec}板块{cnt}只,建议分散")

    
    # ━━ 2. 价值池维护 ━━
    value = wl['groups'].get('value', {}).get('stocks', [])
    keep_value = []
    for s in value:
        d = fetch(s['code'], use_cache=False)
        if 'error' in d:
            keep_value.append(s); continue
        
        a = analyze(d)
        sig = a['g']
        pe = d.get('pe', 0)
        
        # PE恶化或信号<1 → 移出
        if sig < 1 or (pe > 100 and sig < 3):
            changes.append(f"🔴 价值池 {s['name']}({s['code']}) PE={pe:.0f} 信号{sig}/6 → 移出")
        else:
            keep_value.append(s)
    
    wl['groups']['value']['stocks'] = keep_value
    
    # ━━ 3. 观察池 → 波段池升级 ━━
    watch = wl['groups'].get('watch', {}).get('stocks', [])
    keep_watch = []
    for s in watch:
        d = fetch(s['code'], use_cache=False)
        if 'error' in d:
            keep_watch.append(s); continue
        
        a = analyze(d)
        sig = a['g']
        
        # 信号恢复到3+ → 升回波段池
        if sig >= 3:
            if not any(x['code'] == s['code'] for x in wl['groups']['band']['stocks']):
                wl['groups']['band']['stocks'].append({
                    "code": s['code'], "name": s['name'],
                    "note": f"PE={d.get('pe',0):.0f} · 信号{sig}/6 · 恢复"
                })
                changes.append(f"🟢 观察池 {s['name']}({s['code']}) 信号恢复{sig}/6 → 升入波段池")
        else:
            keep_watch.append(s)
    
    wl['groups']['watch']['stocks'] = keep_watch
    
    # 保存
    wl['updated'] = datetime.now().strftime('%Y-%m-%d %H:%M')
    with open(WATCHLIST, 'w') as f:
        json.dump(wl, f, ensure_ascii=False, indent=2)
    
    # 状态
    state = {"last_run": datetime.now().strftime('%Y-%m-%d %H:%M'), "changes": changes}
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    print(f'🔄 自动调仓 {datetime.now().strftime("%H:%M")}')
    print(f'  波段池 {len(wl["groups"]["band"]["stocks"])}只')
    print(f'  价值池 {len(wl["groups"]["value"]["stocks"])}只')
    print(f'  观察池 {len(wl["groups"]["watch"]["stocks"])}只')
    
    if changes:
        print(f'\n  变更 {len(changes)}项:')
        for c in changes: print(f'  {c}')
    else:
        print(f'  无变更')
    
    return changes

if __name__ == "__main__":
    auto_adjust()
