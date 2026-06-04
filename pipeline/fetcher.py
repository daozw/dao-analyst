"""管道阶段1: 数据获取 — 腾讯+东财+通达信+雪球 (全免费, 0积分)"""
import json, urllib.request, ssl, http.cookiejar
ssl._create_default_https_context = ssl._create_unverified_context
import time, os, json as _json
from pathlib import Path

# 简易缓存(5分钟有效期)
_CACHE_DIR = Path.home() / '.cache' / 'pipeline'
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _cached(key, ttl=300):
    f = _CACHE_DIR / (key + '.json')
    if f.exists() and time.time() - f.stat().st_mtime < ttl:
        return _json.loads(open(f).read())
    return None

def _cache_put(key, data):
    with open(_CACHE_DIR / (key + '.json'), 'w') as fp:
        _json.dump(data, fp, ensure_ascii=False)

def _retry(url, headers=None, timeout=8, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            return urllib.request.urlopen(req, timeout=timeout)
        except:
            if i < tries-1: time.sleep(1)
            else: raise

_xq_opener = None
def _xq():
    global _xq_opener
    if _xq_opener: return _xq_opener
    cj = http.cookiejar.CookieJar()
    _xq_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    headers = {"User-Agent": ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "zh-CN,zh;q=0.9"}
    try: _xq_opener.open(urllib.request.Request("https://xueqiu.com/", headers=headers), timeout=8)
    except: pass
    try: _xq_opener.open(urllib.request.Request("https://xueqiu.com/hq", headers=headers), timeout=8)
    except: pass
    return _xq_opener

def _raw_fetch(code, full=False, use_cache=True):
    # 检查缓存
    cache_key = f"stock_{code}_{'full' if full else 'basic'}"
    if use_cache:
        cached = _cached(cache_key)
        if cached: return cached
    """获取单只股票完整数据"""
    d = {"code": code}
    prefix = "sh" if code.startswith("6") else "sz"
    
    # 腾讯行情
    try:
        raw = urllib.request.urlopen(urllib.request.Request(
            f"https://qt.gtimg.cn/q={prefix}{code}"), timeout=8).read().decode("gbk")
        p = raw.split("~")
        d.update({"name":p[1],"price":float(p[3]),"chg":float(p[32]),"high":float(p[33]),
            "low":float(p[34]),"turnover":float(p[38]),"pe":float(p[39]) if p[39] else 0,
            "amount":float(p[37]),"pre_close":float(p[4]),"vol":float(p[6]) if p[6] else 0})
    except: return {"error":"腾讯行情失败"}
    
    # 东财资金 (仅full模式)
    if full:
        try:
            url = f"https://push2.eastmoney.com/api/qt/stock/fflow/kline/get?secid=0.{code}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55&klt=1&lmt=5"
            r = json.loads(_retry(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=8).read())
            if r.get("data",{}).get("klines"):
                ks = r["data"]["klines"]
                ti = sum(float(k.split(",")[1]) for k in ks); to = sum(float(k.split(",")[3]) for k in ks)
                d["fund"] = {"in":ti/1e4,"out":to/1e4,"net":(ti-to)/1e4}
        except: d["fund"] = None
    
    # 通达信K线
    try:
        from mootdx.quotes import Quotes
        cq = Quotes.factory(market='std'); dt = cq.bars(symbol=code, frequency=9, start=0, offset=20)
        if len(dt) >= 14:
            cs=[]; trs=[]; kls=[]
            for i in range(len(dt)):
                o,c,h,l=float(dt.iloc[i]['open']),float(dt.iloc[i]['close']),float(dt.iloc[i]['high']),float(dt.iloc[i]['low'])
                cs.append(c); kls.append({"o":o,"c":c,"h":h,"l":l})
                if i>0: trs.append(max(h-l,abs(h-cs[-2]),abs(l-cs[-2])))
            d["klines"]=kls[-8:]; d["ma5"]=sum(cs[-5:])/5; d["ma20"]=sum(cs[-20:])/20
            d["atr"]=sum(trs[-14:])/14
            d["support"]=min(kls[-5:],key=lambda x:x["l"])["l"]
            d["resistance"]=max(kls[-5:],key=lambda x:x["h"])["h"]
    except:
        d["atr"]=d["price"]*0.03; d["support"]=d["price"]*0.95
        d["resistance"]=d["price"]*1.05; d["klines"]=[]
    
    if use_cache: _cache_put(cache_key, d)
    return d


# === 内存缓存层 V1.0 ===
_cache = {}
_CACHE_TTL = 60

def _cached_fetch(code, use_cache=True):
    """带60s缓存的fetch，避免同1分钟内重复API调用"""
    import time
    if use_cache:
        now = time.time()
        if code in _cache and now - _cache[code]['ts'] < _CACHE_TTL:
            return _cache[code]['data']
    data = _raw_fetch(code, use_cache=False)
    if use_cache and 'error' not in data:
        _cache[code] = {'data': data, 'ts': time.time()}
    return data

def fetch_market():
    """市场全景数据 (指数+自选+热度)"""
    data = {}
    
    # 三大指数 (腾讯行情)
    try:
        raw = urllib.request.urlopen(urllib.request.Request(
            "https://qt.gtimg.cn/q=sh000001,sz399001,sz399006"), timeout=8).read().decode("gbk")
        for line in raw.split("\n"):
            if not line.strip() or "=" not in line: continue
            name_part = line.split("=")[0]
            p = line.split("~")
            if len(p) < 38: continue
            if "sh000001" in name_part:
                data["index"] = {"name":"上证指数","price":float(p[3]),"chg":float(p[32]),
                    "high":float(p[33]),"low":float(p[34]),"amount":float(p[37])}
            elif "sz399001" in name_part:
                data["sz_index"] = {"name":"深证成指","price":float(p[3]),"chg":float(p[32])}
            elif "sz399006" in name_part:
                data["cy_index"] = {"name":"创业板指","price":float(p[3]),"chg":float(p[32])}
    except: pass
    
    # 热门板块 (腾讯行情 - 行业板块涨跌幅)
    try:
        sectors = [
        "pt01801011","pt01801040","pt01801041","pt01801074","pt01801085",
        "pt01801014","pt01801038","pt01801001","pt01801082","pt01801034",
        "pt01801121","pt01801042","pt01801019","pt01801193","pt01801088",
        "pt01801027","pt01801055","pt01801066","pt01801083","pt01801080",
        "pt01801061","pt01801046","pt01801057","pt01801072","pt01801008"
    ]
        raw = urllib.request.urlopen(urllib.request.Request(
            "https://qt.gtimg.cn/q="+",".join(sectors)), timeout=8).read().decode("gbk")
        data["hot"] = []
        for line in raw.split("\n"):
            if not line.strip() or "=" not in line: continue
            p = line.split("~")
            if len(p) > 3:
                data["hot"].append({"code":p[2],"name":p[1],"chg":float(p[32]) if len(p)>32 else 0})
        data["hot"].sort(key=lambda x: abs(x["chg"]), reverse=True)
        data["hot"] = data["hot"][:10]
    except: pass
    
    # 核心资产涨跌 (Sina行情)
    try:
        bluechips = ["sh601318,sh600519,sh600036,sh601398,sh600900,sz000858,sh601166,sz300750,sh600276,sz002415"]
        raw = urllib.request.urlopen(urllib.request.Request(
            "https://hq.sinajs.cn/list=" + ",".join(bluechips),
            headers={"Referer":"https://finance.sina.com.cn"}), timeout=8).read().decode("gbk")
        data["popular"] = []
        for line in raw.split("\n"):
            if "=" not in line: continue
            name, rest = line.split("=",1)
            code_part = name.replace("var hq_str_","").strip()
            p = rest.strip('";').split(",")
            if len(p) > 3:
                price = float(p[3]); prev = float(p[2])
                chg = (price - prev) / prev * 100 if prev > 0 else 0
                data["popular"].append({"code":code_part,"name":p[0],"chg":chg})
        data["popular"].sort(key=lambda x: abs(x["chg"]), reverse=True)
        data["popular"] = data["popular"][:10]
    except: pass
    
    # 人气排行 (Sina成交量榜)
    try:
        r = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=12&sort=volume&asc=0&node=hs_a&symbol=",
            headers={"Referer":"https://finance.sina.com.cn","User-Agent":"Mozilla/5.0"}), timeout=8).read())
        data["popular_stocks"] = []
        for item in r[:12]:
            code = str(item.get("code",""))
            name = item.get("name","")
            vol = float(item.get("volume",0)) / 10000  # 转万手
            chg = float(item.get("changepercent",0))
            # Filter out BJ stocks
            if not code.startswith("9") and len(code)==6:
                data["popular_stocks"].append({"code":code,"name":name,"vol":vol,"chg":chg})
        data["popular_stocks"] = data["popular_stocks"][:10]
    except: pass
    
    # 雪球热榜 + Sina涨幅榜fallback
    try:
        r = json.loads(_xq().open(urllib.request.Request(
            "https://stock.xueqiu.com/v5/stock/hot_stock/list.json?size=15&_type=12&type=12",
            headers={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                     "Accept":"application/json","X-Requested-With":"XMLHttpRequest",
                     "Referer":"https://xueqiu.com/hq"}), timeout=8).read())
        data["hot_stocks"] = []
        for item in r.get("data",{}).get("items",[])[:10]:
            code = str(item.get("code","")).replace("SH","").replace("SZ","")
            if len(code)==6:
                data["hot_stocks"].append({"code":code,"name":item.get("name",""),"chg":item.get("percent",0)})
    except:
        # fallback: Sina涨幅榜
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(
                "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=12&sort=changepercent&asc=0&node=hs_a&symbol=",
                headers={"Referer":"https://finance.sina.com.cn","User-Agent":"Mozilla/5.0"}), timeout=8).read())
            data["hot_stocks"] = []
            for item in r[:12]:
                code = str(item.get("code",""))
                if not code.startswith("9") and len(code)==6:
                    data["hot_stocks"].append({"code":code,"name":item.get("name",""),"chg":float(item.get("changepercent",0))})
            data["hot_stocks"] = data["hot_stocks"][:8]
        except: pass
    
    # 概念人气 (Sina换手率榜)
    try:
        r = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=12&sort=turnoverratio&asc=0&node=hs_a&symbol=",
            headers={"Referer":"https://finance.sina.com.cn","User-Agent":"Mozilla/5.0"}), timeout=8).read())
        data["concept_hot"] = []
        for item in r[:12]:
            code = str(item.get("code",""))
            turnover = float(item.get("turnoverratio",0))
            chg = float(item.get("changepercent",0))
            if not code.startswith("9") and len(code)==6:
                data["concept_hot"].append({"code":code,"name":item.get("name",""),"turnover":turnover,"chg":chg})
        data["concept_hot"] = data["concept_hot"][:8]
    except: pass
    
    # 退市风险
    try:
        from pipeline.delist_risk import scan_risks, summary as risk_summary
        data["risk"] = risk_summary(scan_risks())
    except Exception:
        pass
    return data


# 公开接口：优先走缓存
def fetch(code, full=False, use_cache=True):
    return _cached_fetch(code, use_cache)
