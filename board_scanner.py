#!/usr/bin/env python3
"""打板雷达 V1.2 — 早盘+午后 — 7%抢板 + 量比确认 + 板块联动"""
import sys,fcntl, os, json, time, warnings, urllib.request, ssl
from datetime import datetime
from collections import defaultdict
warnings.filterwarnings('ignore')
ssl._create_default_https_context = ssl._create_unverified_context

def _log(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime("%H:%M:%S")}] {msg}", file=__import__("sys").stderr)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board_tracker import BoardAnalyzer

# 加载配置
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strategy", "board", "config.json")
with open(CONFIG_FILE) as f:
    CONFIG = json.load(f)


def _safe_alert_append(entry, alert_file="/tmp/dao_trade_alerts.json"):
    """线程安全追加告警 (advisory file lock)"""
    import fcntl, struct
    lock_path = alert_file + ".lock"
    try:
        with open(lock_path, 'w') as lf:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            try:
                alerts = json.load(open(alert_file)) if os.path.exists(alert_file) else []
            except Exception as e:

                _log(f"{type(e).__name__}: {e}")  # auto-logged
                alerts = []
            alerts.append(entry)
            with open(alert_file, 'w') as af:
                json.dump(alerts, af, ensure_ascii=False, indent=2)
    except Exception as e:
        # Fallback: best-effort write without lock
        try:
            alerts = json.load(open(alert_file)) if os.path.exists(alert_file) else []
            alerts.append(entry)
            with open(alert_file, 'w') as af:
                json.dump(alerts, af, ensure_ascii=False, indent=2)
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            print(f"  ⚠️ 告警写入失败: {e}")

ALERT_FILE = "/tmp/dao_trade_alerts.json"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "board_scan.json")

PRE_MIN = CONFIG["buy_conditions"]["pre_board_chg_min"]   # 7%
PRE_MAX = CONFIG["buy_conditions"]["pre_board_chg_max"]    # 9.5%
VOL_MIN = CONFIG["buy_conditions"]["min_volume_ratio"]     # 2x
MAX_PRICE = CONFIG["buy_conditions"]["max_price"]          # ¥30
BOARD_CAPITAL = 10000       # 华泰打板总资金
MAX_DAILY_BOARD = 3         # 每日最多3只
SINGLE_BOARD_QTY = 100      # 单笔100股



def get_prematch_scores():
    """读取竞价匹配度，用于优先扫描"""
    state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "premarket.json")
    if os.path.exists(state_file):
        try:
            state = json.load(open(state_file))
            return state.get("match_scores", {})
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            pass
    return {}

def get_board_candidates():
    """新浪API → 涨幅≥5% → 过滤主板 → ≤MAX_PRICE"""
    candidates = []
    try:
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=80&sort=changepercent&asc=0&node=hs_a&symbol="
        req = urllib.request.Request(url, headers={
            "Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"
        })
        raw = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
        stocks = json.loads(raw)
        # 主板 + 非ST + ≤MAX_PRICE
        candidates = [s for s in stocks 
                if s.get("code", "").startswith(("60", "00"))
                and not s.get("code", "").startswith("688")
                and float(s.get("changepercent", 0)) >= 5.0
                and float(s.get("trade", 0)) <= MAX_PRICE
                and "ST" not in s.get("name", "")
                and "退" not in s.get("name", "")]
    except Exception as e:
        pass  # 新浪失败不影响，后面有池子补扫
    
    return candidates


def get_pool_candidates():
    """池子补扫: 从 band/core/growth 池中扫描涨幅≥5%的标的"""
    pool = []
    try:
        wl_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "watchlist.json")
        wl = json.load(open(wl_path))
        for gn in ("band", "core", "growth"):
            group = wl.get("groups", {}).get(gn, {})
            for s in group.get("stocks", []):
                code = s["code"]
                if code.startswith(("60", "00")) and not code.startswith("688"):
                    pool.append((code, s.get("name", "")))
    except Exception as e:

        _log(f"{type(e).__name__}: {e}")  # auto-logged
        return []
    
    pool = list(dict.fromkeys(pool))  # 去重
    results = []
    
    # 批量查询 (每批40只)
    for i in range(0, len(pool), 40):
        batch = pool[i:i+40]
        bs = ','.join([f'sh{c}' if c.startswith('6') else f'sz{c}' for c,_ in batch])
        try:
            req = urllib.request.Request(f'https://qt.gtimg.cn/q={bs}')
            raw = urllib.request.urlopen(req, timeout=5).read().decode('gbk')
            for ln in raw.strip().split('\n'):
                d = ln.split('~')
                if len(d) < 40: continue
                try:
                    chg = float(d[32])
                    price = float(d[3])
                    if chg >= 5.0 and price <= MAX_PRICE and "ST" not in d[1] and "退" not in d[1]:
                        results.append({
                            "code": d[2], "name": d[1],
                            "changepercent": chg, "trade": price,
                            "source": "pool_scan"
                        })
                except Exception as e:

                    _log(f"{type(e).__name__}: {e}")  # auto-logged
                    pass
            time.sleep(0.3)  # 限流
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            pass
    
    return results


def merge_candidates(sina, pool):
    """合并新浪+池子结果, 去重"""
    seen = set()
    merged = []
    for s in sina + pool:
        code = s.get("code", "")
        if code and code not in seen:
            seen.add(code)
            merged.append(s)
    return merged


def get_stock_detail(code):
    """腾讯行情 → 个股详情"""
    try:
        prefix = "sz" if code.startswith(("0", "3", "2")) else "sh"
        url = f"https://qt.gtimg.cn/q={prefix}{code}"
        raw = urllib.request.urlopen(urllib.request.Request(url), timeout=5).read().decode("gbk")
        parts = raw.split("~")
        if len(parts) < 50: return None
        return {
            "name": parts[1], "price": float(parts[3]),
            "chg": float(parts[32]) if parts[32] else 0,
            "high": float(parts[33]) if parts[33] else 0,
            "low": float(parts[34]) if parts[34] else 0,
            "open": float(parts[5]) if parts[5] else 0,
            "volume": float(parts[6]) if parts[6] else 0,
            "amount": float(parts[37]) if parts[37] else 0,
            "turnover": float(parts[38]) if parts[38] else 0,
            "volume_ratio": float(parts[46]) if len(parts) > 46 and parts[46] else 1,
        }
    except Exception as e:

        _log(f"{type(e).__name__}: {e}")  # auto-logged
        return None


def get_sector_leaders(candidates):
    """检测板块联动：同一板块有多只涨停 → 龙头效应"""
    from collections import Counter
    sectors = Counter()
    for s in candidates:
        code = s.get("code", "")
        # 同行业近似：代码前3位
        sector = code[:3]
        if float(s.get("changepercent", 0)) >= 9.5:
            sectors[sector] += 1
    return {k: v for k, v in sectors.items() if v >= 2}


def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"date": datetime.now().strftime("%Y-%m-%d"), "scanned": [], "alerts_sent": []}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)  # 原子替换, 读不到半截文件



def auto_trade_board(code, name, price, qty, dry_run=True):
    """打板自动下单 → 华泰"""
    if dry_run:
        return True, f"📋 打板 {name}({code}) {qty}股 @¥{price:.2f}"
    try:
        import subprocess
        HTSC = os.path.expanduser("~/.openclaw-autoclaw/skills/a-share-paper-trading/a_share_paper_trading.py")
        cmd = [sys.executable, HTSC, "submitOrder", "--symbol", str(code),
               "--side", "buy", "--quantity", str(qty), "--price", str(price)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        resp = json.loads(r.stdout) if r.stdout else {}
        return resp.get("ok", False), resp
    except Exception as e:
        return False, {"error": str(e)[:80]}
def queue_alert(code, name, price, chg, grade, risk, strategy, reason, sector_ok, vol_ok):
    alerts = []
    if os.path.exists(ALERT_FILE):
        try: alerts = json.load(open(ALERT_FILE))
        except: pass
    alerts.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "action": "BOARD",
        "code": code, "name": name, "price": price, "chg": chg,
        "grade": grade, "risk": risk, "strategy": strategy,
        "sector_ok": sector_ok, "vol_ok": vol_ok,
        "message": f"🔥 {grade} {name}({code}) ¥{price:.2f} +{chg:.1f}% | {strategy}",
        "sent": False
    })
    with open(ALERT_FILE, "w") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)


def scan():
    now = datetime.now()
    hour = now.hour * 100 + now.minute
    
    if hour < 925:
        return "⏰ 等待开盘 (9:25竞价后)"
    
    state = load_state()
    if state.get("date") != now.strftime("%Y-%m-%d"):
        state = {"date": now.strftime("%Y-%m-%d"), "scanned": [], "alerts_sent": [], "today_buys": 0}
    
    sina = get_board_candidates()
    pool = get_pool_candidates()
    candidates = merge_candidates(sina, pool)
    if not candidates:
        return "📡 无候选"
    
    print(f"  📡 新浪{len(sina)}只 + 池子{len(pool)}只 → 合并{len(candidates)}只")
    
    # 板块联动检测
    sector_leaders = get_sector_leaders(candidates)
    
    analyzer = BoardAnalyzer()
    results = []
    last_chg = {}
    newly_alerted = 0
    
    for stock in candidates:
        code = stock.get("code", "")
        name = stock["name"]
        chg = float(stock.get("changepercent", 0))
        
        if code in state["scanned"]:
            continue
        
        detail = get_stock_detail(code)
        if not detail:
            continue
        
        price = detail["price"]
        vol_ratio = detail.get("volume_ratio", 1)
        turnover = detail.get("turnover", 0)
        
        # 板块联动检查
        sector_code = code[:3]
        sector_ok = sector_code in sector_leaders
        
        # 量比检查
        vol_ok = vol_ratio >= VOL_MIN
        
        # 封板时间估算
        open_time = now.strftime('%H:%M')
        
        # 竞价匹配度加成
        match_scores = get_prematch_scores()
        match_bonus = match_scores.get(code, 0)
        
        # 分类
        grade = analyzer.classify_board(open_time, turnover, vol_ratio, 1 if sector_ok else 5)
        risk = analyzer.break_risk(price, detail["high"], turnover, detail.get("amount", 0))
        strat = analyzer.strategy(grade, risk, price)
        
        # ── 时间权重: 早盘>午盘>尾盘 ──
        import datetime as _dt
        hour = _dt.datetime.now().hour
        time_weight = 1.0
        if hour < 10: time_weight = 1.2  # 早盘最优
        elif hour < 11: time_weight = 1.0
        elif hour < 14: time_weight = 0.8  # 午盘警惕
        else: time_weight = 0.6  # 尾盘最弱
        
        # ── 市场温度权重 ──
        temp_weight = 1.0
        try:
            from market_thermometer_v2 import get_thermometer
            t = get_thermometer()
            if '进攻占优' in t.get('level', ''): temp_weight = 1.2
            elif '防御抬头' in t.get('level', ''): temp_weight = 0.7
            elif '防御主导' in t.get('level', ''): temp_weight = 0.4
        except: pass
        
        # ===== 打板决策 =====
        can_board = False
        reason = ""
        
        if chg >= PRE_MAX:  # >=9.5% 已封板
            if grade in ("💎 钻石板", "🥇 黄金板") and risk == "🟢 低风险":
                can_board = True
                reason = f"T{time_weight:.1f}xM{temp_weight:.1f}x条件通过"
            elif grade in ("💎 钻石板", "🥇 黄金板", "🥈 白银板"):
                can_board = True
                reason = "排板轻仓"
            else:
                reason = f"封板质量差({grade})"
        
        elif chg >= PRE_MIN:  # 7-9.5% 抢板区
            if vol_ok and sector_ok:
                can_board = True
                reason = "抢板✅量比+" + ("板块联动" if sector_ok else "")
            elif vol_ok:
                can_board = True
                reason = "抢板⚠️无量比确认"
            else:
                reason = f"量比{vol_ratio:.1f}x不足"
        
        else:  # 5-7% 预警区
            if vol_ok:
                reason = f"🔔预警(量比{vol_ratio:.1f}x 提前关注)"
            else:
                reason = f"涨幅{chg:.1f}%偏低"
        
        results.append({
            "code": code, "name": name, "price": price, "chg": chg,
            "grade": grade, "risk": risk, "strategy": strat,
            "can_board": can_board, "reason": reason,
            "vol_ratio": vol_ratio, "sector_ok": sector_ok,
            "match_score": match_bonus,
            "zone": "封板" if chg >= PRE_MAX else "抢板" if chg >= PRE_MIN else "预警"
        })
        
        # 急拉加速检测
        if code in last_chg:
            delta_chg = chg - last_chg[code]
            if delta_chg >= 2.0:
                reason += f" 急拉+{delta_chg:.1f}%"
        last_chg[code] = chg
        state["scanned"].append(code)
        
        if can_board and code not in state["alerts_sent"]:
            queue_alert(code, name, price, chg, grade, risk, strat, reason, sector_ok, vol_ok)
            state["alerts_sent"].append(code)
            newly_alerted += 1
    
    # 写入候选列表供 board_reopen 读取
    state["candidates"] = results  # 完整结果列表(含zone/grade等)
    save_state(state)
    
    # 报告
    lines = [f"🎯 打板雷达 {now.strftime('%H:%M')} | {len(candidates)}只候选 | {newly_alerted}提醒"]
    
    # 封板区 → 参考(散户买不到)
    sealed = [r for r in results if r["zone"] == "封板"]
    if sealed:
        lines.append(f"\n📋 已封板·板块参考({len(sealed)}只) — 买不到，看板块强度:")
        for r in sorted(sealed, key=lambda x: -x["chg"])[:5]:
            lines.append(f"  {'🔒' if r['can_board'] else '  '} {r['name']} ¥{r['price']:.2f} +{r['chg']:.1f}% {r['grade']}")
    
    # 抢板区 → 可交易信号
    rushing = [r for r in results if r["zone"] == "抢板"]
    if rushing:
        lines.append(f"\n⚡ 抢板·可交易({len(rushing)}只) — 7%-9.5%区间，可执行:")
        for r in sorted(rushing, key=lambda x: (-x["can_board"], -x["chg"]))[:8]:
            tag = "🎯" if r["can_board"] else "  "
            checks = f"量{r['vol_ratio']:.1f}x" + (" 板块✅" if r["sector_ok"] else "")
            lines.append(f"  {tag} {r['name']} ¥{r['price']:.2f} +{r['chg']:.1f}% {checks} → {r['reason']}")
    
    # 观察区
    watching = [r for r in results if r["zone"] == "观察"]
    if watching:
        lines.append(f"\n👀 观察区({len(watching)}只):")
        for r in sorted(watching, key=lambda x: (-x["vol_ratio"], -x["chg"]))[:5]:
            lines.append(f"  👀 {r['name']} ¥{r['price']:.2f} +{r['chg']:.1f}% 量{r['vol_ratio']:.1f}x")
    
    if sector_leaders:
        lines.append(f"\n📈 板块联动: {dict(sector_leaders)}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    auto_exec = "--real" in sys.argv
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        os.remove(STATE_FILE) if os.path.exists(STATE_FILE) else None
        print("✅ 状态已重置")
    else:
        print(scan())
