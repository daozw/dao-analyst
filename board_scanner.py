#!/usr/bin/env python3
"""打板雷达 V1.2 — 早盘+午后 — 7%抢板 + 量比确认 + 板块联动"""
import sys, os, json, time, warnings, urllib.request, ssl
from datetime import datetime
from collections import defaultdict
warnings.filterwarnings('ignore')
ssl._create_default_https_context = ssl._create_unverified_context

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from board_tracker import BoardAnalyzer

# 加载配置
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "strategy", "board", "config.json")
with open(CONFIG_FILE) as f:
    CONFIG = json.load(f)

ALERT_FILE = "/tmp/dao_trade_alerts.json"
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "board_scan.json")

PRE_MIN = CONFIG["buy_conditions"]["pre_board_chg_min"]   # 7%
PRE_MAX = CONFIG["buy_conditions"]["pre_board_chg_max"]    # 9.5%
VOL_MIN = CONFIG["buy_conditions"]["min_volume_ratio"]     # 2x
MAX_PRICE = CONFIG["buy_conditions"]["max_price"]          # ¥30



def get_prematch_scores():
    """读取竞价匹配度，用于优先扫描"""
    state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "state", "premarket.json")
    if os.path.exists(state_file):
        try:
            state = json.load(open(state_file))
            return state.get("match_scores", {})
        except:
            pass
    return {}

def get_board_candidates():
    """新浪API → 涨幅≥5% → 过滤主板 → ≤MAX_PRICE"""
    try:
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=80&sort=changepercent&asc=0&node=hs_a&symbol="
        req = urllib.request.Request(url, headers={
            "Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"
        })
        raw = urllib.request.urlopen(req, timeout=10).read().decode("gbk")
        stocks = json.loads(raw)
        # 主板 + 非ST + ≤MAX_PRICE
        return [s for s in stocks 
                if s.get("code", "").startswith(("60", "00"))
                and not s.get("code", "").startswith("688")
                and float(s.get("changepercent", 0)) >= 5.0
                and float(s.get("trade", 0)) <= MAX_PRICE
                and "ST" not in s.get("name", "")
                and "退" not in s.get("name", "")]
    except:
        return []


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
    except:
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
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)



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
    
    if hour < 930 or hour > 1025:
        return "⏰ 打板扫描 9:30-10:30"
    
    state = load_state()
    if state.get("date") != now.strftime("%Y-%m-%d"):
        state = {"date": now.strftime("%Y-%m-%d"), "scanned": [], "alerts_sent": []}
    
    candidates = get_board_candidates()
    if not candidates:
        return "📡 无候选"
    
    # 板块联动检测
    sector_leaders = get_sector_leaders(candidates)
    
    analyzer = BoardAnalyzer()
    results = []
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
        open_time = "09:35" if hour < 935 else "10:00" if hour < 1000 else "11:00"
        
        # 竞价匹配度加成
        match_scores = get_prematch_scores()
        match_bonus = match_scores.get(code, 0)
        
        # 分类
        grade = analyzer.classify_board(open_time, turnover, vol_ratio, 1 if sector_ok else 5)
        risk = analyzer.break_risk(price, detail["high"], turnover, detail.get("amount", 0))
        strat = analyzer.strategy(grade, risk, price)
        
        # ===== 打板决策 =====
        can_board = False
        reason = ""
        
        if chg >= PRE_MAX:  # >=9.5% 已封板
            if grade in ("💎 钻石板", "🥇 黄金板") and risk == "🟢 低风险":
                can_board = True
                reason = "排板"
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
        
        else:  # 5-7% 观察区
            if vol_ok:
                reason = f"观察👀(量比{vol_ratio:.1f}x)"
            else:
                reason = f"涨幅{chg:.1f}%偏低"
        
        results.append({
            "code": code, "name": name, "price": price, "chg": chg,
            "grade": grade, "risk": risk, "strategy": strat,
            "can_board": can_board, "reason": reason,
            "vol_ratio": vol_ratio, "sector_ok": sector_ok,
            "match_score": match_bonus,
            "zone": "封板" if chg >= PRE_MAX else "抢板" if chg >= PRE_MIN else "观察"
        })
        
        state["scanned"].append(code)
        
        if can_board and code not in state["alerts_sent"]:
            queue_alert(code, name, price, chg, grade, risk, strat, reason, sector_ok, vol_ok)
            state["alerts_sent"].append(code)
            newly_alerted += 1
    
    save_state(state)
    
    # 报告
    lines = [f"🎯 打板雷达 {now.strftime('%H:%M')} | {len(candidates)}只候选 | {newly_alerted}提醒"]
    
    # 封板区
    sealed = [r for r in results if r["zone"] == "封板"]
    if sealed:
        lines.append(f"\n🔒 已封板({len(sealed)}只):")
        for r in sorted(sealed, key=lambda x: -x["chg"])[:5]:
            tag = "🔥" if r["can_board"] else "  "
            lines.append(f"  {tag} {r['name']} ¥{r['price']:.2f} +{r['chg']:.1f}% {r['grade']}" + (f" 竞价{r['match_score']}分" if r.get('match_score',0) >= 70 else ""))
    
    # 抢板区
    rushing = [r for r in results if r["zone"] == "抢板"]
    if rushing:
        lines.append(f"\n⚡ 冲击涨停({len(rushing)}只):")
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
