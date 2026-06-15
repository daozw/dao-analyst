#!/usr/bin/env python3
"""DAO分析师 系统自检 V1.0 — 全链路健康诊断"""
import sys, os, json, time, urllib.request, ssl, traceback
from datetime import datetime

ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RESULTS = {"time": datetime.now().isoformat(), "checks": [], "errors": [], "warnings": []}

def check(name, fn):
    try:
        fn()
        RESULTS["checks"].append(f"✅ {name}")
        return True
    except Exception as e:
        RESULTS["errors"].append(f"❌ {name}: {e}")
        return False

def warn(name, msg):
    RESULTS["warnings"].append(f"⚠️ {name}: {msg}")

def run():
    # ── 1. 行情API ──
    def test_quote():
        url = 'https://qt.gtimg.cn/q=sh000001,sz399001'
        raw = urllib.request.urlopen(url, timeout=8).read().decode('gbk')
        lines = raw.strip().split('\n')
        assert len(lines) >= 2, f"返回行数异常: {len(lines)}"
        for ln in lines:
            d = ln.split('~')
            if '000001' in ln:
                assert len(d) > 32, f"上证数据异常"
                chg = float(d[32])
                RESULTS["market"] = {"chg": chg, "price": float(d[3])}
        RESULTS["api_quote"] = "OK"
    check("腾讯行情API", test_quote)
    
    # ── 2. 持仓查询 ──
    def test_position():
        from pipeline.autotrade import get_mx_positions
        pos, total, profit = get_mx_positions()
        RESULTS["mx_positions"] = {"count": len(pos), "total": total, "profit": profit}
    check("MX持仓查询", test_position)
    
    # ── 3. 华泰API ──
    def test_htsc():
        from trader import UnifiedTrader
        trader = UnifiedTrader()
        resp = trader.balance()
        assert resp.get("code") == "200", f"HTSC不可用: {resp}"
        RESULTS["htsc_balance"] = resp['data'].get('availableBalance', 0)
    check("华泰余额查询", test_htsc)
    
    # ── 4. 市场温度 ──
    def test_temp():
        from market_thermometer_v2 import get_thermometer, get_rsi
        t = get_thermometer()
        rsi = get_rsi()
        RESULTS["market_temp"] = {"level": t.get("level"), "ratio": t.get("ratio"), "rsi": rsi}
    check("市场温度+RSI", test_temp)
    
    # ── 5. 信号系统 ──
    def test_signals():
        from pipeline.fetcher import fetch
        from pipeline.signals import analyze
        for code in ['600900', '000001']:
            d = fetch(code, use_cache=False)
            a = analyze(d)
            assert 0 <= a['g'] <= 6, f"{code}信号异常: {a['g']}"
    check("信号系统(2只样本)", test_signals)
    
    # ── 6. 关键文件完整性 ──
    for fname, desc in [
        ("data/watchlist.json", "自选股池"),
        ("data/state/board_scan.json", "打板扫描"),
        ("data/state/pool_state.json", "池子状态"),
    ]:
        try:
            if os.path.exists(fname):
                json.load(open(fname))
                RESULTS["checks"].append(f"✅ {desc} ({os.path.getsize(fname)}B)")
            else:
                warn(desc, "文件不存在")
        except Exception as e:
            warn(desc, str(e))
    
    # ── 7. 熔断状态 ──
    bf = '/tmp/circuit_breaker_state.json'
    if os.path.exists(bf):
        try:
            bs = json.load(open(bf))
            if bs.get('triggered'):
                RESULTS["errors"].append(f"⛔ 熔断已触发! {bs.get('reasons', [])}")
            else:
                RESULTS["checks"].append(f"✅ 熔断未触发 ({bs.get('level','?')})")
        except:
            warn("熔断状态", "文件损坏")
    else:
        RESULTS["checks"].append("✅ 熔断文件(首次运行后生成)")
    
    # ── 8. 实时监控进程 ──
    import subprocess
    r = subprocess.run(['pgrep', '-f', 'realtime_monitor'], capture_output=True, text=True)
    if r.stdout.strip():
        RESULTS["checks"].append(f"✅ 实时监控运行中 PID:{r.stdout.strip()}")
    else:
        now_h = datetime.now().hour
        if 9 <= now_h < 15:
            warn("实时监控", "未运行(交易时段!)")
        else:
            RESULTS["checks"].append("✅ 实时监控(非交易时段正常)")
    
    # ── 9. 交易冷却 ──
    cf = '/tmp/trade_cooldown'
    if os.path.exists(cf):
        try:
            cd = json.load(open(cf))
            last = cd.get('last_trade_time', 0)
            secs = time.time() - last
            if secs < 30:
                warn("交易冷却", f"上次交易{secs:.0f}秒前(冷却中)")
            else:
                RESULTS["checks"].append(f"✅ 交易冷却已过({secs:.0f}秒)")
        except:
            pass
    
    # ── 10. 综合评分 ──
    errors = len(RESULTS["errors"])
    warns = len(RESULTS["warnings"])
    passed = len([c for c in RESULTS["checks"] if c.startswith("✅")])
    
    if errors == 0 and warns == 0:
        RESULTS["verdict"] = "🟢 系统健康"
    elif errors == 0:
        RESULTS["verdict"] = f"🟡 {warns}个警告"
    else:
        RESULTS["verdict"] = f"🔴 {errors}个错误"
    
    RESULTS["score"] = f"{passed}通过/{errors}错误/{warns}警告"
    
    # 输出
    print(f"\n{'='*40}")
    print(f"  DAO分析师 自检 {datetime.now().strftime('%m/%d %H:%M')}")
    print(f"  {RESULTS['verdict']} | {RESULTS['score']}")
    print(f"{'='*40}")
    for c in RESULTS["checks"][-15:]:
        print(f"  {c}")
    for e in RESULTS["errors"]:
        print(f"  {e}")
    for w in RESULTS["warnings"]:
        print(f"  {w}")
    print()
    
    # 存报告
    os.makedirs('/tmp', exist_ok=True)
    with open('/tmp/self_check_report.json', 'w') as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=2, default=str)
    
    return 0 if errors == 0 else 1

if __name__ == '__main__':
    sys.exit(run())
