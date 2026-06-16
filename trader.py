#!/usr/bin/env python3
"""
统一交易适配器 V2.1 — 华泰实盘(QMT) + 华泰模拟 + MX模拟
"""
import json, os, sys, urllib.request, ssl, subprocess
from datetime import datetime
ssl._create_default_https_context = ssl._create_unverified_context

def _log(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime("%H:%M:%S")}] {msg}", file=__import__("sys").stderr)

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE, "data", "trade_config.json")
LOG_FILE = os.path.join(BASE, "data", "trade_log.json")

DEFAULT_CONFIG = {
    "board_mode": "PAPER",   # 打板→华泰模拟
    "band_mode": "MX",       # 波段→妙想模拟
    "mode": "PAPER",         # 兼容旧版
    "max_amount": 20000,
    "max_single": 5000,
    "confirm_real": True,
    "qmt_path": "/Applications/QMT",
    "account_id": "",
    "ht_apikey": os.environ.get("HT_APIKEY", ""),
    "mx_apikey": "mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8",
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        cfg = json.load(open(CONFIG_FILE))
        return {**DEFAULT_CONFIG, **cfg}
    return DEFAULT_CONFIG


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════
# 华泰模拟交易 (a-share-paper-trading)
# ═══════════════════════════════════
class PaperTrader:
    def __init__(self, apikey):
        self.apikey = apikey
        self.skill = os.path.expanduser(
            "~/.openclaw-autoclaw/skills/a-share-paper-trading/a_share_paper_trading.py"
        )
    
    def _run(self, *args):
        env = {**os.environ, "HT_APIKEY": self.apikey}
        r = subprocess.run([sys.executable, self.skill] + list(args),
                         capture_output=True, text=True, env=env, timeout=15)
        return json.loads(r.stdout) if r.stdout else {}
    
    def quote_snapshot(self, code):
        """获取Level-2盘口快照(5档买卖+逐笔)"""
        try:
            resp = self._call('GET', f'/api/quote/snapshot?code={code}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_snapshot failed"}
    
    def quote_depth(self, code):
        """获取委托队列深度"""
        try:
            resp = self._call('GET', f'/api/quote/depth?code={code}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_depth failed"}
    
    def quote_ticks(self, code, count=100):
        """获取最近逐笔成交"""
        try:
            resp = self._call('GET', f'/api/quote/ticks?code={code}&count={count}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_ticks failed"}
    
    def buy(self, code, price, quantity):
        return self._run("submitOrder", "--stock-code", str(code),
                        "--direction", "buy", "--quantity", str(quantity),
                        "--price", str(price), "--exchange", "SZ" if code.startswith(("0","3","2")) else "SH")
    
    def sell(self, code, price, quantity):
        return self._run("submitOrder", "--stock-code", str(code),
                        "--direction", "sell", "--quantity", str(quantity),
                        "--price", str(price), "--exchange", "SZ" if code.startswith(("0","3","2")) else "SH")
    
    def cancel_all(self):
        return self._run("cancelAllPendingOrders")
    
    def balance(self):
        return self._run("getAccountBalance")
    
    def positions(self):
        return self._run("getPositions")
    
    def orders(self):
        return self._run("listPendingOrders", "--stock-code", "")


# ═══════════════════════════════════
# 华泰实盘交易 (QMT/xtquant)
# ═══════════════════════════════════
class QMTTrader:
    def __init__(self, qmt_path, account_id):
        self.qmt_path = qmt_path
        self.account_id = account_id
        self.connected = False
        self._xt = None
        
        # 添加QMT的xtquant到Python路径
        xt_path = os.path.join(qmt_path, "bin.x64", "Lib", "site-packages")
        if os.path.exists(xt_path):
            sys.path.insert(0, xt_path)
        
        try:
            import xtquant.xttrader as xttrader
            import xtquant.xtdata as xtdata
            import xtquant.xtconstant as xtconstant
            
            self._xt = xttrader
            self._xtdata = xtdata
            self._xtconst = xtconstant
            
            # 创建交易实例
            session_id = int(datetime.now().timestamp() % 100000)
            self._trader = xttrader.XtQuantTrader(qmt_path, session_id)
            
            # 注册回调
            self._trader.start()
            
            # 连接账户
            if account_id:
                connect_result = self._trader.connect()
                if connect_result == 0:
                    # 订阅账户
                    self._trader.subscribe(account_id)
                    self.connected = True
                    print(f"✅ QMT已连接: {account_id}")
                else:
                    print(f"⚠️ QMT连接失败: code={connect_result}")
            else:
                print("⚠️ 未配置account_id, 跳过QMT连接")
        except ImportError:
            print("⚠️ xtquant未安装。请先安装华泰QMT客户端。")
            print("   下载: https://qmt.htsc.com")
        except Exception as e:
            print(f"⚠️ QMT初始化失败: {e}")
    
    def _ensure_connected(self):
        if not self.connected:
            return {"error": "QMT未连接"}
        return None
    
    def _get_account(self):
        """获取账户对象"""
        if not self.connected:
            return None
        # QMT返回的是列表
    
    def quote_snapshot(self, code):
        """获取Level-2盘口快照(5档买卖+逐笔)"""
        try:
            resp = self._call('GET', f'/api/quote/snapshot?code={code}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_snapshot failed"}
    
    def quote_depth(self, code):
        """获取委托队列深度"""
        try:
            resp = self._call('GET', f'/api/quote/depth?code={code}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_depth failed"}
    
    def quote_ticks(self, code, count=100):
        """获取最近逐笔成交"""
        try:
            resp = self._call('GET', f'/api/quote/ticks?code={code}&count={count}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_ticks failed"}
    
    def buy(self, code, price, quantity):
        err = self._ensure_connected()
        if err: return err
        
        try:
            # QMT下单: 固定价格买入
            order_id = self._trader.order_stock(
                code, 
                self._xtconst.STOCK_BUY, 
                quantity, 
                self._xtconst.FIX_PRICE, 
                price,
                '深圳' if code.startswith(('0','3','2')) else '上海',
                '科创板' if code.startswith('688') else 'A股'
            )
            if order_id > 0:
                return {"ok": True, "data": {"order_id": order_id}}
            else:
                return {"ok": False, "error": {"message": f"下单失败 code={order_id}"}}
        except Exception as e:
            return {"ok": False, "error": {"message": str(e)[:100]}}
    
    def sell(self, code, price, quantity):
        err = self._ensure_connected()
        if err: return err
        
        try:
            order_id = self._trader.order_stock(
                code,
                self._xtconst.STOCK_SELL,
                quantity,
                self._xtconst.FIX_PRICE,
                price,
                '深圳' if code.startswith(('0','3','2')) else '上海',
                '科创板' if code.startswith('688') else 'A股'
            )
            if order_id > 0:
                return {"ok": True, "data": {"order_id": order_id}}
            else:
                return {"ok": False, "error": {"message": f"下单失败 code={order_id}"}}
        except Exception as e:
            return {"ok": False, "error": {"message": str(e)[:100]}}
    
    def cancel(self, order_id):
        err = self._ensure_connected()
        if err: return err
        try:
            result = self._trader.cancel_order_stock(order_id)
            return {"ok": True, "data": {"cancelled": result}}
        except Exception as e:
            return {"ok": False, "error": {"message": str(e)[:100]}}
    
    def balance(self):
        err = self._ensure_connected()
        if err: return err
        try:
            asset = self._trader.query_stock_asset(self.account_id)
            return {"ok": True, "data": asset}
        except Exception as e:
            return {"ok": False, "error": {"message": str(e)[:100]}}
    
    def positions(self):
        err = self._ensure_connected()
        if err: return err
        try:
            pos = self._trader.query_stock_positions(self.account_id)
            return {"ok": True, "data": pos}
        except Exception as e:
            return {"ok": False, "error": {"message": str(e)[:100]}}


# ═══════════════════════════════════
# MX模拟交易
# ═══════════════════════════════════
class MXTrader:
    def __init__(self, apikey):
        self.apikey = apikey
        self.api = "https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading"
    
    def _call(self, endpoint, data):
        req = urllib.request.Request(f"{self.api}/{endpoint}",
            data=json.dumps(data).encode(),
            headers={"apikey": self.apikey, "Content-Type": "application/json"})
        return json.loads(urllib.request.urlopen(req, timeout=10).read())
    
    def quote_snapshot(self, code):
        """获取Level-2盘口快照(5档买卖+逐笔)"""
        try:
            resp = self._call('GET', f'/api/quote/snapshot?code={code}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_snapshot failed"}
    
    def quote_depth(self, code):
        """获取委托队列深度"""
        try:
            resp = self._call('GET', f'/api/quote/depth?code={code}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_depth failed"}
    
    def quote_ticks(self, code, count=100):
        """获取最近逐笔成交"""
        try:
            resp = self._call('GET', f'/api/quote/ticks?code={code}&count={count}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_ticks failed"}
    
    def buy(self, code, price, quantity):
        return self._call("trade", {"type": "buy", "stockCode": code,
                                     "price": price, "quantity": quantity})
    
    def sell(self, code, price, quantity):
        return self._call("trade", {"type": "sell", "stockCode": code,
                                     "price": price, "quantity": quantity})
    
    def balance(self):
        return self._call("balance", {"moneyUnit": 1})
    
    def positions(self):
        return self._call("positions", {"moneyUnit": 1})


# ═══════════════════════════════════
# 统一接口
# ═══════════════════════════════════

# ── 单例: 统一入口(HTSC/MX/PAPER) ──
_trader_instance = None

def get_trader():
    """获取交易器单例,自动选择模式"""
    global _trader_instance
    if _trader_instance is None:
        cfg = load_config()
        mode = cfg.get('mode', 'PAPER')
        if mode == 'PAPER':
            from trader import UnifiedTrader
            _trader_instance = UnifiedTrader()
        elif mode == 'MX':
            from pipeline.autotrade import MXTrader
            _trader_instance = MXTrader()
        else:
            from trader import UnifiedTrader
            _trader_instance = UnifiedTrader()
    return _trader_instance


class UnifiedTrader:
    def __init__(self, strategy="auto"):
        """
        strategy: "board"(打板→华泰PAPER) | "band"(波段→MX) | "auto"(兼容旧版)
        打板和波段资金/账户完全隔离
        """
        self.cfg = load_config()
        self.strategy = strategy
        
        if strategy == "board":
            mode = self.cfg.get("board_mode", "PAPER")
        elif strategy == "band":
            mode = self.cfg.get("band_mode", "MX")
        else:  # auto: 兼容旧版
            mode = self.cfg.get("mode", "PAPER")
        
        if mode == "QMT":
            self.engine = QMTTrader(self.cfg["qmt_path"], self.cfg["account_id"])
            self.mode = "QMT"
        elif mode == "MX":
            self.engine = MXTrader(self.cfg["mx_apikey"])
            self.mode = "MX"
        else:  # PAPER
            self.engine = PaperTrader(self.cfg["ht_apikey"])
            self.mode = "PAPER"
    
    def switch_mode(self, mode):
        self.cfg["mode"] = mode
        save_config(self.cfg)
        self.__init__()
        return self.mode
    
    def quote_snapshot(self, code):
        """获取Level-2盘口快照(5档买卖+逐笔)"""
        try:
            resp = self._call('GET', f'/api/quote/snapshot?code={code}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_snapshot failed"}
    
    def quote_depth(self, code):
        """获取委托队列深度"""
        try:
            resp = self._call('GET', f'/api/quote/depth?code={code}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_depth failed"}
    
    def quote_ticks(self, code, count=100):
        """获取最近逐笔成交"""
        try:
            resp = self._call('GET', f'/api/quote/ticks?code={code}&count={count}')
            return resp
        except Exception as e:

            _log(f"{type(e).__name__}: {e}")  # auto-logged
            return {"ok": False, "error": "quote_ticks failed"}
    
    def buy(self, code, price, quantity):
        return self.engine.buy(code, price, quantity)
    
    def sell(self, code, price, quantity):
        return self.engine.sell(code, price, quantity)
    
    def balance(self):
        return self.engine.balance()
    
    def positions(self):
        return self.engine.positions()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    
    trader = UnifiedTrader()
    
    if cmd == "status":
        print(f"🔄 交易模式: {trader.mode}")
        if trader.mode == "QMT":
            print(f"   QMT路径: {trader.cfg['qmt_path']}")
            print(f"   账号: {trader.cfg['account_id']}")
            print(f"   连接: {'✅ 已连接' if trader.engine.connected else '❌ 未连接'}")
        else:
            print(f"   模拟交易模式")
    
    elif cmd == "switch":
        mode = sys.argv[2] if len(sys.argv) > 2 else "PAPER"
        print(f"切换到: {trader.switch_mode(mode)}")
    
    elif cmd == "balance":
        print(json.dumps(trader.balance(), ensure_ascii=False, indent=2))
    
    elif cmd == "positions":
        print(json.dumps(trader.positions(), ensure_ascii=False, indent=2))
    
    elif cmd == "setup":
        print("华泰实盘(QMT)配置需要:")
        print("  1. 在华泰证券开通量化交易权限")
        print("  2. 下载QMT客户端: https://qmt.htsc.com")
        print("  3. 安装后运行:")
        print(f"     python3 trader.py switch QMT")
        print(f"  4. 配置账号:")
        print(f"     编辑 data/trade_config.json → account_id")
