#!/usr/bin/env python3
"""实时监控 V1.0 — 3秒轮询,盯盘+触发交易,替代cron轮询"""
import sys, os, json, time, signal, urllib.request, ssl
from datetime import datetime
from signal_catcher import capture as catch_signal

# 抢板防重: 每日失败上限
BOARD_MAX_ATTEMPTS = 3
BOARD_ATTEMPT_COOLDOWN = 300
_board_attempts = {}
_pre_alert_cooldown = {}


ssl._create_default_https_context = ssl._create_unverified_context
PID_FILE = '/tmp/realtime_monitor.pid'
LOG_FILE = '/tmp/realtime_monitor.log'

running = True
last_trade_time = 0
TRADE_COOLDOWN = 120

def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')

def handle_signal(sig, frame):
    global running
    log("收到停止信号")
    running = False
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

# 延迟导入 (首次使用时加载)
_mx_trade = None

def _get_mx_trade():
    global _mx_trade
    if _mx_trade is None:
        from pipeline.autotrade import _exec_trade
        _mx_trade = _exec_trade
    return _mx_trade

from trader import get_trader as _get_htsc_trader  # 统一入口

# ── 数据 ──


# ── 持仓决策矩阵 ──
def hold_score(code, pos, px, open_price, hold_minutes):
    """综合打分 持有(7-10) / 观察(4-6) / 卖出(0-3)"""
    score = 5  # 起点中性
    reasons = []
    name = pos['name']
    price = px['price']; chg = px['chg']; vol = px.get('vol_ratio', 1)
    limit_up = round(px['pre_close'] * 1.10 + 0.0001, 2)
    
    # ── 1. 市场维度 ──
    try:
        with open('/tmp/dao_market_state.json') as f: ms = json.load(f)
        temp = ms.get('market_temp', {}).get('level', '')
        dd_count = ms.get('market_temp', {}).get('跌停数', 0)
    except: temp = ''; dd_count = 0
    
    if '进攻' in temp: score += 1; reasons.append('进攻市+1')
    elif '防御' in temp: score -= 2; reasons.append('防御市-2')
    if dd_count > 20: score -= 1; reasons.append(f'跌停{dd_count}只-1')
    
    # ── 2. 量能维度 ──
    if vol < 1.5: score -= 1; reasons.append(f'量比{vol:.1f}萎缩-1')
    elif vol > 3: score += 1; reasons.append(f'量比{vol:.1f}活跃+1')
    turn = px.get('turnover', 0)
    if turn > 30: score -= 2; reasons.append(f'换手{turn:.0f}%过高-2')
    elif 10 <= turn <= 25: score += 1; reasons.append(f'换手{turn:.0f}%健康+1')
    
    # ── 3. 时间维度 ──
    if hold_minutes < 15:
        score += 1; reasons.append('观察期中+1')
    elif hold_minutes < 30:
        if price < open_price * 0.98: score -= 1; reasons.append('15min回落-1')
    else:
        score -= 1; reasons.append(f'持有{hold_minutes}min未封-1')
        if price < open_price: score -= 1; reasons.append('30min水下-1')
    
    # ── 4. 价格维度 ──
    if open_price and open_price > 0:
        gap_from_open = (price - open_price) / open_price * 100
    else:
        gap_from_open = 0
    if gap_from_open > 5: score += 1; reasons.append('强势上攻+1')
    elif gap_from_open < -3: score -= 2; reasons.append(f'回落{gap_from_open:.0f}%-2')
    if chg >= 9.5: score += 2; reasons.append('逼近涨停+2')
    
    # ── Level-2盘口分析 ──
    try:
        imb = px.get('imbalance_ratio', 0)
        inside = px.get('inside_ratio', 0)
        comm = px.get('commission_ratio', 0)
        
        # 盘口失衡: 卖盘压倒买盘 → 减分
        if imb < -0.3:
            score -= 2; reasons.append(f'卖盘压倒(失衡{imb:.0%})-2')
        elif imb > 0.2:
            score += 1; reasons.append(f'买盘占优(失衡{imb:.0%})+1')
        
        # 内外比: <0.5表示内盘(主动卖)远大于外盘(主动买)
        if inside < 0.5:
            score -= 1; reasons.append(f'内盘主导({inside:.1f})-1')
        elif inside > 1.5:
            score += 1; reasons.append(f'外盘主导({inside:.1f})+1')
        
        # 委比: 委托买卖比, < -50%表示卖单积压
        if comm < -50:
            score -= 1; reasons.append(f'委比{comm:.0f}%卖压-1')
    except: pass
    
    # ── 逐笔分析(东财Level-2, 仅在HTSC持仓时启用) ──
    try:
        from pipeline.eastmoney_level2 import analyze_ticks
        tick_r = analyze_ticks(code)
        tick_s = tick_r.get('score', 0)
        if abs(tick_s) >= 2:
            score += tick_s
            reasons.append(f'逐笔{tick_s:+d}({tick_r["verdict"]})')
    except: pass
    
    return score, reasons

def batch_prices(codes):
    results = {}
    for i in range(0, len(codes), 50):
        batch = codes[i:i+50]
        q = ','.join(f'sh{c}' if c.startswith('6') else f'sz{c}' for c in batch)
        try:
            raw = urllib.request.urlopen(f'https://qt.gtimg.cn/q={q}', timeout=5).read().decode('gbk')
            for ln in raw.strip().splitlines():
                d = ln.split('~')
                if len(d) < 40: continue
                code = d[2]
                # 盘口数据(供信号捕捉)
                bid_total = sum(float(d[10+i*2]) for i in range(5) if len(d)>10+i*2 and d[10+i*2])
                ask_total = sum(float(d[20+i*2]) for i in range(5) if len(d)>20+i*2 and d[20+i*2])
                imb = (bid_total - ask_total) / (bid_total + ask_total) if (bid_total+ask_total) > 0 else 0
                outside = float(d[6]) if len(d)>6 and d[6] else 0  # 外盘
                inside = float(d[7]) if len(d)>7 and d[7] else 0    # 内盘
                in_ratio = outside/inside if inside>0 else 1.0
                results[code] = {
                    'name': d[1], 'price': float(d[3]),
                    'chg': float(d[32]), 'high': float(d[33]),
                    'low': float(d[34]), 'open': float(d[5]),
                    'pre_close': float(d[4]), 'turnover': float(d[38]),
                    'vol_ratio': float(d[49]) if len(d)>49 and d[49] else 1.0,
                    'amount': float(d[37]),
                    # 盘口(信号捕捉用)
                    'bid_total': bid_total, 'ask_total': ask_total,
                    'imbalance_ratio': imb, 'inside_ratio': in_ratio,
                    'commission_ratio': float(d[48]) if len(d)>48 and d[48] else 0,
                    'mcap': float(d[45]) if len(d)>45 and d[45] else 0,
                    'amount': float(d[37]) if len(d)>37 and d[37] else 0,
                    'pe': float(d[39]) if len(d)>39 and d[39] else 0,
                }
        except Exception as e:
            log(f"行情异常: {e}")
    return results

# ── 持仓 ──
def get_positions():
    positions = {}
    
    # MX模拟持仓 (止损止盈从成本价计算)
def get_mx_positions_file():
    try:
        from pipeline.autotrade import get_mx_positions as f
        import inspect
        return inspect.getfile(f)
    except:
        return "unknown"

    try:
        sys.path.insert(0, os.path.expanduser('~/dao-analyst'))
        from pipeline.autotrade import get_mx_positions, load_evolve_params
        mx_pos, total, _ = get_mx_positions(); _ = str(type(mx_pos))
        bp = load_evolve_params()
        sl_pct = bp.get('stop_loss_pct', -0.06)
        tp1_pct = bp.get('tp_half_pct', 0.08)
        tp2_pct = bp.get('tp_clear_pct', 0.15)
        if _ == "<class 'list'>" or isinstance(mx_pos, list): mx_pos = {p.get("code",p.get("secCode","")): p for p in mx_pos if p}
        for code, pos in (mx_pos.items() if hasattr(mx_pos,"items") else []):
            cost = pos['cost']
            positions[code] = {
                'account': 'MX', 'name': pos['name'],
                'qty': pos['qty'], 'cost': cost,
                'stop_loss': round(cost * (1 + sl_pct), 2),
                'tp1': round(cost * (1 + tp1_pct), 2),
                'tp2': round(cost * (1 + tp2_pct), 2),
            }
    except Exception as e:
        log(f"MX持仓: {e}")

    # 华泰持仓 (检测一字板: 当前价=涨停价 → 标记limit_up_held)
    try:
        from trader import UnifiedTrader
        trader = UnifiedTrader()
        resp = trader.positions()
        if not resp or not resp.get('ok'):
            log("🔴 HTSC连接异常!")
            try:
                with open('/tmp/dao_alert_critical.txt', 'a') as f:
                    f.write(f"[{time.strftime('%H:%M:%S')}] HTSC连接异常: {resp}\n")
            except: pass
            return positions
        if resp.get('ok'):
            for p in resp.get('data', {}).get('positions', []):
                code = p.get('secCode', p.get('code', ''))
                cost = p.get('costPrice', p.get('cost', 0))
                qty = p.get('count', p.get('qty', 0))
                if not code: continue
                pos = {
                    'account': 'HTSC', 'name': p.get('secName', p.get('name', '')),
                    'qty': qty, 'cost': cost,
                    'stop_loss': round(cost * 0.94, 2) if cost else 0,
                }
                # 检查是否一字板(当前价=涨停价,即被clear保留的)
                if code in prices:
                    px = prices.get(code, {})
                    limit_up = round(px.get('pre_close', cost) * 1.10 + 0.0001, 2)
                    if px.get('price', 0) >= limit_up:
                        pos['limit_up_held'] = True
                positions[code] = pos
    except Exception as e:
        log(f"华泰持仓: {e}")
    return positions

# ── 交易 ──
def exec_sell(code, name, price, qty, account):
    global last_trade_time
    if time.time() - last_trade_time < TRADE_COOLDOWN:
        return False
    try:
        if account == 'MX':
            ok, _ = _get_mx_trade()("SELL", code, name, price, qty, dry_run=False)
        else:
            resp = _get_htsc_trader().sell(code, price, qty)
            ok = resp.get('ok', False)
        last_trade_time = time.time()
        log(f"🔴 卖出 {name}({code}) {qty}股 @¥{price:.2f}")
        return ok
    except Exception as e:
        log(f"卖出异常 {name}: {e}")
        return False

def exec_board_buy(code, name, price, qty):
    global last_trade_time
    # ── 每票限制: 最多3次, 5分钟冷却 ──
    if code not in _board_attempts:
        _board_attempts[code] = []
    attempts = _board_attempts[code]
    if len(attempts) >= 3:
        return False
    if attempts and time.time() - attempts[-1] < 300:
        return False
    attempts.append(time.time())
    # ── 全局冷却 ──
    if time.time() - last_trade_time < TRADE_COOLDOWN:
        return False
    try:
        resp = _get_htsc_trader().buy(code, price, qty)
        ok = resp.get('ok', False)
        last_trade_time = time.time()
        log(f"🟢 打板 {name}({code}) {qty}股 @¥{price:.2f} {'✅' if ok else '❌'}({len(_board_attempts.get(code,[]))}/3)")
        return ok
    except Exception as e:
        log(f"🔴 打板异常 {name}: {e}")
        # 写告警文件供Agent检查
        try:
            with open('/tmp/dao_alert_critical.txt', 'a') as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] HTSC交易失败 {name}({code}): {e}\n")
        except: pass
        return False

# ── 监控 ──
def check_positions(positions, prices):
    for code, pos in positions.items():
        if code not in prices: continue
        px = prices[code]
        price = px['price']
        cost = pos['cost']
        profit_pct = (price - cost) / cost * 100 if cost and cost > 0 else 0
        pre_close = px['pre_close']
        limit_up = round(pre_close * 1.10 + 0.0001, 2)
        
        # 🔥 一字板炸板检测 (涨停开盘→开板下跌)
        if pos.get('account') == 'HTSC' and pos.get('limit_up_held'):
            if price < limit_up:
                log(f"💥 {pos['name']}({code}) 炸板! 涨停{limit_up}→现{price}")
                exec_sell(code, pos['name'], price, pos['qty'], 'HTSC')
                continue
        
        # 🔒 持有待封板: 封板即卖锁利 (昨日打板票高开持有)
        if pos.get('account') == 'HTSC' and price >= limit_up:
            log(f"🔒 {pos['name']}({code}) 封板@{price} → 止盈锁利{profit_pct:+.1f}%")
            exec_sell(code, pos['name'], price, pos['qty'], 'HTSC')
            continue
        
        if pos.get('stop_loss') and price <= pos['stop_loss']:
            log(f"⚠️ {pos['name']} 止损 {profit_pct:.1f}%")
            exec_sell(code, pos['name'], price, pos['qty'], pos['account'])
            continue
        
        if pos.get('tp2') and price >= pos['tp2']:
            log(f"💰 {pos['name']} 大赚{profit_pct:.1f}% 清仓")
            exec_sell(code, pos['name'], price, pos['qty'], pos['account'])
            continue
        
        if pos.get('tp1') and price >= pos['tp1'] and pos['account']=='MX':
            sell_qty = max(100, pos['qty']//2//100*100)
            log(f"📈 {pos['name']} 小赚{profit_pct:.1f}% 卖半仓")
            exec_sell(code, pos['name'], price, sell_qty, pos['account'])

def check_board_candidates(prices, positions=None):
    """实时打板扫描: 从board_pool中检测涨幅7-9.5%+量比>2的标的"""
    if positions is None:
        positions = get_positions()
    pos_codes = set(positions.keys())
    
    # 从board_scan.json获取候选列表(作为补充)
    board_codes = set()
    try:
        base = os.path.expanduser('~/dao-analyst')
        f = os.path.join(base, 'data', 'state', 'board_scan.json')
        if os.path.exists(f):
            scan = json.load(open(f))
            for c in scan.get('candidates', []):
                if c.get('can_board'):
                    board_codes.add(c.get('code', ''))
    except Exception as e:

        log(f"{type(e).__name__}: {e}")  # auto-logged
        pass
    
    # 从board_pool加载所有打板候选
    try:
        wl = json.load(open(os.path.join(os.path.expanduser('~/dao-analyst'), 'data/watchlist.json')))
        for s in wl.get('groups', {}).get('board', {}).get('stocks', []):
            if not s['code'].startswith(('300','688','8')):
                board_codes.add(s['code'])
    except Exception as e:

        log(f"{type(e).__name__}: {e}")  # auto-logged
        pass
    
    for code in board_codes:
        if code in pos_codes: continue
        if code not in prices: continue
        
        px = prices[code]
        chg = px['chg']; price = px['price']; vol = px['vol_ratio']
        pre_close = px['pre_close']; limit_up = round(pre_close*1.10, 2)
        turnover = px['turnover']
        name = px.get('name', '')
        
        # ── 垃圾股过滤 ──
        if 'ST' in name: continue  # ST/*ST
        mcap = px.get('mcap', 0)
        if 0 < mcap < 100: continue  # 市值<100亿
        amt = px.get('amount', 0)
        if 0 < amt < 3000: continue  # 成交额<3000万
        
        # 过滤条件
        if price >= limit_up: continue  # 已涨停只排板
        # 🔔 5-7%预警区: 仅通知,不交易
        if chg >= 5 and chg < 7 and vol >= 1.5:
            now_t = time.time()
            if now_t - _pre_alert_cooldown.get(code, 0) >= 120:
                name = px.get("name", "")
                log(f"🔔 预警 {name}({code}) +{chg:.1f}% 量比{vol:.1f}x | 提前关注")
                _pre_alert_cooldown[code] = now_t
            continue
        if chg < 7 or chg >= 9.5: continue  # 抢板区间
        if vol < 2: continue  # 无量的拉升不追
        if price < 3 or price > 30: continue  # 垃圾股/高价股
        if turnover > 30: continue  # 换手率过高(出货嫌疑)
        
        qty = max(100, min(500, int(10000/price/100)*100))
        log(f"🔥 实时抢板 {px['name']}({code}) +{chg:.1f}% 量比{vol:.1f}x 换手{turnover:.1f}%")
        exec_board_buy(code, px['name'], price, qty)

def check_band_signals(prices, pool, positions=None):
    if positions is None:
        positions = get_positions()
    pos_codes = set(positions.keys())
    
    sig_file = '/tmp/dao_band_signals.json'
    try:
        sigs = json.load(open(sig_file)) if os.path.exists(sig_file) else []
    except Exception as e:

        log(f"{type(e).__name__}: {e}")  # auto-logged
        sigs = []
    
    for code in pool:
        if code in pos_codes or code not in prices: continue
        px = prices[code]
        if px['chg']>=5 or px['chg']<=-2: continue
        if px['vol_ratio']<0.5: continue
        if px['price']<3 or px['price']>50: continue
        # 波段垃圾过滤(市值≥30亿)
        name_band = px.get('name','')
        if 'ST' in name_band: continue
        mcap_band = px.get('mcap',0)
        if 0 < mcap_band < 30: continue
        amt_band = px.get('amount',0)
        if 0 < amt_band < 1000: continue
        
        score = 0
        if px['chg']>0: score+=15
        if px['vol_ratio']>1.5: score+=20
        if 2<=px['turnover']<=8: score+=15
        
        if score>=35 and not any(s['code']==code for s in sigs):
            sigs.append({'code':code,'name':px['name'],'price':px['price'],
                         'score':score,'time':datetime.now().isoformat()})
            log(f"📊 波段信号 {px['name']}({code}) {score}分 +{px['chg']:.1f}%")
    
    with open(sig_file, 'w') as f:
        json.dump(sigs[-20:], f)

# ── 主循环 ──
def main():
    global running
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))
    
    log("🚀 实时监控启动")
    
    base = os.path.expanduser('~/dao-analyst')
    sys.path.insert(0, base)
    
    try:
        wl = json.load(open(os.path.join(base, 'data/watchlist.json')))
        band_pool = []
        for gn in ['core','band','value']:
            for s in wl['groups'].get(gn,{}).get('stocks',[]):
                if not s['code'].startswith(('300','688','8')):
                    band_pool.append(s['code'])
        board_pool = [s['code'] for s in wl['groups'].get('board',{}).get('stocks',[])
                      if not s['code'].startswith(('300','688','8'))]
        all_codes = list(set(band_pool + board_pool))
        log(f"监控池: 波段{len(band_pool)}只 + 打板{len(board_pool)}只")
    except Exception as e:
        log(f"池子失败: {e}")
        band_pool = []
        all_codes = ['600900']
    
    _pos_cache = {}
    cycle = 0
    # 交易日检测: 周末退出
    from datetime import datetime as _dtnow
    if _dtnow.now().weekday() >= 5:
        log("非交易日(周末), 退出")
        sys.exit(0)
    
    while running:
        try:
            cycle += 1
            # 每200轮(~10分钟)刷新监控池
            if cycle % 200 == 0:
                try:
                    wl2 = json.load(open(os.path.join(base, "data/watchlist.json")))
                    bp2 = []
                    for gn in ["core","band","value"]:
                        for s in wl2["groups"].get(gn,{}).get("stocks",[]):
                            if not s["code"].startswith(("300","688","8")):
                                bp2.append(s["code"])
                    bdp2 = [s["code"] for s in wl2["groups"].get("board",{}).get("stocks",[])
                            if not s["code"].startswith(("300","688","8"))]
                    all_codes = list(set(bp2 + bdp2))
                    band_pool = bp2
                    log(f"池子刷新: 波段{len(band_pool)}只 + 打板{len(bdp2)}只")
                    # 融合问财智能选股
                    try:
                        wcf = os.path.join(base, "data/state/pywencai_candidates.json")
                        if os.path.exists(wcf):
                            wc = json.load(open(wcf))
                            wc_time = wc.get("time","")
                            # 只融合同一天的扫描结果
                            if _dtnow.now().strftime("%Y-%m-%d") in wc_time:
                                wband = [c for c in wc.get("band",[]) if not c.startswith(("300","688","8"))]
                                wboard = [c for c in wc.get("board",[]) if not c.startswith(("300","688","8"))]
                                new_band = list(set(band_pool + wband))
                                new_board = list(set(bdp2 + wboard))
                                all_codes = list(set(new_band + new_board))
                                band_pool = new_band
                                log(f"池子刷新+问财: 波段{len(band_pool)}只 + 打板{len(new_board)}只")
                    except Exception as e:
                        log(f"问财融合失败: {e}")
                except Exception as e:
                    log(f"池子刷新失败: {e}")
            prices = batch_prices(all_codes)
            if not prices or prices is None:
                time.sleep(3)
                continue
            
            # 持仓缓存: 每5轮(15秒)刷新,减少API调用
            if cycle % 5 == 1:
                _pos_cache = get_positions()
            positions = _pos_cache
            
            # 检查熔断状态
            breaker_file = '/tmp/circuit_breaker_state.json'
            if os.path.exists(breaker_file):
                try:
                    bs = json.load(open(breaker_file))
                    if bs.get('triggered'):
                        log(f"🔴 熔断中! 跌停{bs.get('limit_down','?')}只,暂停交易")
                        time.sleep(30)
                        continue
                except: pass
            
            if positions:
                check_positions(positions, prices)
            # ── 信号捕捉(提前量,每只股票检测盘口+量能+加速度) ──
            for code, px in prices.items():
                name = px.get('name', '')
                try:
                    sigs = catch_signal(code, name, px, commit=True)
                    for s in sigs:
                        log(s['msg'])
                        try:
                            from pipeline.trade_notify import queue_alert
                            queue_alert('🚀SIG', s['code'], s['name'], s['price'], 0, 0, s['msg'])
                        except: pass
                except: pass
            # 打板扫描仅在9:20-15:00运行
            now_dt = _dtnow.now()
            if (now_dt.hour == 9 and now_dt.minute >= 20) or (now_dt.hour > 9 and now_dt.hour < 15) and now_dt.weekday() < 5:
                check_board_candidates(prices, positions)
            
            if cycle % 10 == 0 and band_pool:
                check_band_signals(prices, band_pool, positions)
            
            if cycle % 30 == 0:
                # 持久化dedup状态
                try:
                    json.dump({'attempts': dict(_board_attempts), 'ts': time.time()},
                              open('/tmp/realtime_monitor_state.json', 'w'))
                except: pass
            if cycle % 100 == 0:
                log(f"💓 第{cycle}轮 持仓{len(positions)}只")
                # 日志裁剪: 保留最近5000行
                try:
                    with open(LOG_FILE) as lf:
                        lines = lf.readlines()
                    if len(lines) > 6000:
                        with open(LOG_FILE, 'w') as lf:
                            lf.writelines(lines[-5000:])
                except: pass
        except Exception as e:
            log(f"异常: {e}")
        time.sleep(3)
    
    log("🛑 实时监控停止")
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)

if __name__ == '__main__':
    main()
