#!/usr/bin/env python3
"""
信号捕捉器 V1.0 — 提前量信号,在价格启动前捕捉
核心思路: 不等到+7%才报警, 用盘口/量能/加速度提前检测启动迹象

信号类型:
  🚀 启动 — vol_ratio翻倍+盘口买盘增长, 涨幅尚在2-5%
  📈 急拉 — 单周期涨>1%+量能放大, 加速中
  🔄 翻转 — imbalance_ratio由负转正, 买方接管
  🔥 大单 — inside>2+vol>2, 外盘主导吃货
  ⚡ 抢板 — 5-7%+量比>3+盘口偏多, 抢板提前量
"""
import json, time, os

SIGNAL_COOLDOWN = 600  # 同票冷却(秒,无视信号类型)
SIGNAL_FILE = "/tmp/dao_signals.json"

_snapshots = {}
_signal_cooldown = {}

def capture(code, name, px, commit=False):
    """输入单票行情快照, 检测信号"""
    now = time.time()
    
    snap = {
        'ts': now, 'price': px['price'], 'chg': px.get('chg', 0),
        'vol_ratio': px.get('vol_ratio', 1), 'bid_total': px.get('bid_total', 0),
        'ask_total': px.get('ask_total', 0), 'imb': px.get('imbalance_ratio', 0),
        'inside': px.get('inside_ratio', 1), 'comm': px.get('commission_ratio', 0),
        'turnover': px.get('turnover', 0)
    }
    
    if code not in _snapshots:
        _snapshots[code] = []
    _snapshots[code].append(snap)
    if len(_snapshots[code]) > 10:
        _snapshots[code] = _snapshots[code][-10:]
    
    if not commit or len(_snapshots[code]) < 2:
        return []
    
    snaps = _snapshots[code]
    first, prev, cur = snaps[0], snaps[-2], snap
    chg = cur['chg']
    signals = []
    
    def _cooled(st):
        key = f"{code}_{st}"
        last = _signal_cooldown.get(key, 0)
        if now - last < SIGNAL_COOLDOWN:
            return False
        _signal_cooldown[key] = now
        return True
    
    # 🚀 启动: vol从<1.5跳>2.5 + bid增长 + chg 2-5%
    if 2 <= chg <= 5:
        if cur['vol_ratio'] >= 2.5 and first.get('vol_ratio', 1) < 1.5:
            if cur['bid_total'] > first.get('bid_total', 0) * 1.3 and _cooled('launch'):
                signals.append({'type':'🚀启动','code':code,'name':name,'price':cur['price'],
                    'chg':round(chg,1),'priority':8,'ts':now,'actionable':True,
                    'msg':f"🚀 启动 {name}({code}) +{chg:.1f}% 量比{cur['vol_ratio']:.1f}x 买盘增长"})
        elif cur['vol_ratio'] >= 2 and cur['imb'] > -0.3 and _cooled('launch'):
            signals.append({'type':'🚀启动','code':code,'name':name,'price':cur['price'],
                'chg':round(chg,1),'priority':6,'ts':now,'actionable':True,
                'msg':f"🚀 启动 {name}({code}) +{chg:.1f}% 量能{cur['vol_ratio']:.1f}x 盘口改善"})
    
    # 📈 急拉: 本周期涨>1%
    delta = cur['chg'] - prev['chg']
    if delta >= 1.0 and cur['vol_ratio'] >= 1.5 and chg >= 3 and _cooled('surge'):
        signals.append({'type':'📈急拉','code':code,'name':name,'price':cur['price'],
            'chg':round(chg,1),'priority':9,'ts':now,'actionable':True,
            'msg':f"📈 急拉 {name}({code}) +{chg:.1f}% ↑{delta:.1f}% 量比{cur['vol_ratio']:.1f}x"})
    
    # 🔄 翻转: imb由负转正
    if prev['imb'] < -0.1 and cur['imb'] > 0.1 and chg >= 1 and _cooled('flip'):
        signals.append({'type':'🔄翻转','code':code,'name':name,'price':cur['price'],
            'chg':round(chg,1),'priority':7,'ts':now,'actionable':True,
            'msg':f"🔄 盘口翻转 {name}({code}) +{chg:.1f}% 买方接管 失衡{cur['imb']:.0%}"})
    
    # 🔥 大单: inside>2+vol>2
    if cur['inside'] > 2 and cur['vol_ratio'] > 2 and chg > 1 and _cooled('big'):
        signals.append({'type':'🔥大单','code':code,'name':name,'price':cur['price'],
            'chg':round(chg,1),'priority':8,'ts':now,'actionable':True,
            'msg':f"🔥 大单 {name}({code}) +{chg:.1f}% 外盘{cur['inside']:.1f}x 量比{cur['vol_ratio']:.1f}x"})
    
    # ⚡ 抢板: 5-7%+vol>3+盘口偏多
    if 5 <= chg < 7 and cur['vol_ratio'] >= 3 and cur['imb'] > -0.2 and _cooled('board'):
        signals.append({'type':'⚡抢板','code':code,'name':name,'price':cur['price'],
            'chg':round(chg,1),'priority':10,'ts':now,'actionable':True,
            'msg':f"⚡ 抢板窗口 {name}({code}) +{chg:.1f}% 量比{cur['vol_ratio']:.1f}x 盘口偏多"})
    
    if signals:
        _save(signals)
    return signals

def _save(new_sigs):
    existing = []
    if os.path.exists(SIGNAL_FILE):
        try: existing = json.load(open(SIGNAL_FILE))
        except: pass
    existing.extend(new_sigs)
    existing = existing[-100:]
    json.dump(existing, open(SIGNAL_FILE, 'w'), ensure_ascii=False, indent=2)

def recent(minutes=10):
    if not os.path.exists(SIGNAL_FILE): return []
    try: all_s = json.load(open(SIGNAL_FILE))
    except: return []
    cutoff = time.time() - minutes*60
    return [s for s in all_s if s.get('ts',0) >= cutoff]

def clear_old():
    if not os.path.exists(SIGNAL_FILE): return
    all_s = json.load(open(SIGNAL_FILE))
    fresh = [s for s in all_s if s.get('ts',0) >= time.time()-3600]
    json.dump(fresh, open(SIGNAL_FILE, 'w'), ensure_ascii=False, indent=2)
