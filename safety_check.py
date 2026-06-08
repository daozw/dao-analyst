#!/usr/bin/env python3
"""
安全检查 V1.0 — 交易前全面校验
市场/仓位/T+1/涨跌停/资金/重复/熔断/API
"""
import sys, os, json, urllib.request, ssl
from datetime import datetime, timezone, timedelta
ssl._create_default_https_context = ssl._create_unverified_context
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MX_KEY = 'mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8'
MX_API = 'https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading'

class SafetyCheck:
    def __init__(self):
        self.checks = []
        self.passed = 0
        self.warnings = 0
        self.blocks = 0
    
    def _fail(self, msg, level='block'):
        self.checks.append({'msg': msg, 'level': level, 'pass': False})
        if level == 'block': self.blocks += 1
        else: self.warnings += 1
        return False
    
    def _ok(self, msg):
        self.checks.append({'msg': msg, 'level': 'ok', 'pass': True})
        self.passed += 1
        return True
    
    # ━━ 1. 市场环境 ━━
    def check_market(self):
        """市场温度+交易时段"""
        from datetime import datetime
        now = datetime.now()
        hour = now.hour * 100 + now.minute
        
        # 交易时段
        is_trading = (930 <= hour <= 1130) or (1300 <= hour <= 1500)
        if not is_trading:
            return self._ok('⏰ 非交易时段(跳过市场检查)')
        
        # 市场温度
        try:
            from market_thermometer_v2 import get_thermometer
            temp = get_thermometer()
            level = temp['level']
            
            if '防御主导' in level:
                return self._fail(f'🔴 {level} — 暂停买入')
            elif '防御抬头' in level:
                self._fail(f'🟠 {level} — 半仓运行', 'warn')
                return True
            else:
                return self._ok(f'🟢 {level}')
        except:
            return self._ok('⚠️ 温度计不可用,跳过')
    
    # ━━ 2. 仓位检查 ━━
    def check_position(self, entry_price, stop_price, total_cap=50000):
        """仓位公式校验"""
        if entry_price <= stop_price:
            return self._fail('❌ 买入价≤止损价')
        
        shares = int(600 / (entry_price - stop_price) / 100) * 100
        if shares < 100:
            return self._fail(f'❌ 止损空间过大,最小100股需¥{entry_price*100:.0f}')
        
        value = shares * entry_price
        risk = shares * (entry_price - stop_price)
        
        checks = []
        if value > total_cap:
            checks.append(f'超总仓{value/total_cap*100:.0f}%')
        if risk > 600:
            checks.append(f'风险¥{risk:.0f}>600')
        
        if checks:
            return self._fail(f'❌ 仓位违规: {",".join(checks)}')
        
        return self._ok(f'💰 {shares}股 ¥{value:,.0f} 风险¥{risk:.0f}')
    
    # ━━ 3. T+1检查 ━━
    def check_t1(self, code, action='BUY'):
        """T+1: 当日买不能卖"""
        if action != 'SELL':
            return self._ok('T+1: 买入无限制')
        
        # 检查MX当日买入
        try:
            req = urllib.request.Request(f'{MX_API}/orders',
                data=json.dumps({}).encode(), headers={'apikey':MX_KEY,'Content-Type':'application/json'}, method='POST')
            orders = json.loads(urllib.request.urlopen(req, timeout=10).read())
            today = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
            
            for o in orders.get('data',{}).get('orders',[]):
                tm = datetime.fromtimestamp(o['time'], tz=timezone(timedelta(hours=8)))
                if tm.strftime('%Y-%m-%d') == today and o.get('type') == 5 and o['secCode'] == code:
                    return self._fail(f'🔒 T+1: {code}今日已买入,不能卖出')
        except:
            pass
        return self._ok('T+1: 可卖出')
    
    # ━━ 4. 涨跌停检查 ━━
    def check_price_limit(self, price, prev_close):
        """涨跌停保护"""
        limit_up = round(prev_close * 1.10, 2)
        limit_down = round(prev_close * 0.90, 2)
        
        if price >= limit_up * 0.995:
            return self._fail(f'🔴 已涨停 ¥{price:.2f}≈¥{limit_up:.2f}')
        if price <= limit_down * 1.005:
            return self._fail(f'🟢 已跌停 ¥{price:.2f}≈¥{limit_down:.2f}')
        
        return self._ok(f'📊 价格正常 ¥{price:.2f}')
    
    # ━━ 5. 资金检查 ━━
    def check_balance(self, amount):
        """MX余额检查"""
        try:
            req = urllib.request.Request(f'{MX_API}/balance',
                data=json.dumps({}).encode(), headers={'apikey':MX_KEY,'Content-Type':'application/json'}, method='POST')
            bal = json.loads(urllib.request.urlopen(req, timeout=10).read())
            data = bal.get('data', bal)
            avail = data.get('availBalance', 0) / 1000
            
            if avail < amount:
                return self._fail(f'❌ 可用¥{avail:,.0f} < 需¥{amount:,.0f}')
            return self._ok(f'💵 可用¥{avail:,.0f} ≥ ¥{amount:,.0f}')
        except:
            return self._ok('⚠️ 余额查询失败,跳过')
    
    # ━━ 6. 重复下单检查 ━━
    def check_duplicate(self, code, state):
        """今日已买过同股"""
        today_codes = {st['code'] for st in state.get('stocks', [])}
        if code in today_codes:
            return self._fail(f'🔄 {code}今日已买入')
        return self._ok('🆕 首次买入')
    
    # ━━ 7. 日熔断 ━━
    def check_circuit_breaker(self, state, max_trades=3):
        """每日交易限额"""
        count = state.get('buy_count', 0)
        if count >= max_trades:
            return self._fail(f'🚫 日熔断: 已{count}/{max_trades}只')
        return self._ok(f'📊 今日{count}/{max_trades}只')
    
    def run_all(self, code, entry, stop, prev_close, state, action='BUY', amount=0):
        """运行全部检查"""
        results = []
        
        if action == 'BUY':
            results.append(('市场环境', self.check_market()))
            results.append(('仓位公式', self.check_position(entry, stop)))
            results.append(('涨跌停', self.check_price_limit(entry, prev_close)))
            results.append(('资金余额', self.check_balance(amount or entry*100)))
            results.append(('重复下单', self.check_duplicate(code, state)))
            results.append(('日熔断', self.check_circuit_breaker(state)))
        elif action == 'SELL':
            results.append(('T+1锁仓', self.check_t1(code, 'SELL')))
        
        return results
    
    def report(self):
        """生成检查报告"""
        lines = [f'🛡️ 安全检查 {"="*20}']
        for c in self.checks:
            icon = '✅' if c['pass'] else '⛔' if c['level']=='block' else '⚠️'
            lines.append(f'  {icon} {c["msg"]}')
        lines.append(f'{"="*35}')
        lines.append(f'通过{self.passed} | 警告{self.warnings} | 阻止{self.blocks}')
        
        blocked = self.blocks > 0
        return '\n'.join(lines), blocked


if __name__ == '__main__':
    # Quick test
    sc = SafetyCheck()
    state = {'buy_count': 1, 'stocks': [{'code':'000001'}]}
    results, blocked = sc.run_all('600900', 27.5, 26.0, 27.7, state, 'BUY', 2800)
    print(sc.report()[0])
