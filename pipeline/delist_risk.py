"""管道模块: 退市风险监测 — 基于 Sina 行情 API"""
import urllib.request, json, time

# 常见 ST/*ST/退市 股票池（通过 Sina API 实时验证）
RISK_WATCHLIST = [
    "sh600275","sh600306","sh600462","sh600734","sh600289","sh600365",
    "sh600385","sh600393","sh600421","sh600518","sh600530","sh600543",
    "sh600556","sh600599","sh600615","sh600617","sh600634","sh600666",
    "sh600671","sh600696","sh600701","sh600715","sh600766","sh600804",
    "sh600807","sh600823","sh600890","sh600891","sh603001","sh603003",
    "sh603030","sh603133","sh603157","sh603196","sh603377","sh603421",
    "sh603555","sh603557","sh603559","sh603598","sh603603","sh603608",
    "sh603616","sh603637","sh603665","sh603778","sh603779","sh603789",
    "sh603797","sh603800","sh603808","sh603825","sh603828","sh603838",
    "sh603843","sh603869","sh603879","sh603880","sh603885","sh603903",
    "sh603908","sh603918","sh603936","sh603958","sh603959","sh603969",
    "sh603977","sh603978","sh603980","sh603983","sh603987","sh603988",
    "sh603989","sh603990","sh603991","sh603993","sh603997","sh605001",
    "sh605006","sh605008","sh605018","sh605050","sh605055",
    "sh688020","sh688086","sh688108","sh688260","sh688272","sh688287",
    "sh688296","sh688315","sh688316","sh688345","sh688373","sh688393",
    "sz000005","sz000007","sz000017","sz000023","sz000029","sz000034",
    "sz000037","sz000038","sz000039","sz000040","sz000042","sz000046",
    "sz000048","sz000049","sz000055","sz000056","sz000058","sz000061",
    "sz000062","sz000063","sz000065","sz000068","sz000070","sz000078",
    "sz000150","sz000403","sz000408","sz000409","sz000413","sz000416",
    "sz000430","sz000502","sz000506","sz000509","sz000514","sz000518",
    "sz000523","sz000525","sz000526","sz000536","sz000540","sz000545",
    "sz000546","sz000550","sz000558","sz000564","sz000566","sz000567",
    "sz000571","sz000572","sz000584","sz000585","sz000587","sz000592",
    "sz000595","sz000598","sz000599","sz000606","sz000607","sz000608",
    "sz000609","sz000611","sz000613","sz000615","sz000616","sz000620",
    "sz000622","sz000623","sz000626","sz000628","sz000632","sz000633",
    "sz000635","sz000637","sz000638","sz000656","sz000659","sz000662",
    "sz000663","sz000665","sz000668","sz000669","sz000670","sz000671",
    "sz000676","sz000679","sz000681","sz000688","sz000691","sz000692",
    "sz000695","sz000698","sz000700","sz000701","sz000707","sz000710",
    "sz000711","sz000712","sz000716","sz000717","sz000720","sz000721",
    "sz000722","sz000723","sz000725","sz000726","sz000728","sz000731",
    "sz000732","sz000733","sz000735","sz000736","sz000738","sz000739",
    "sz000750","sz000752","sz000753","sz000755","sz000756","sz000757",
    "sz000758","sz000759","sz000761","sz000762","sz000766","sz000767",
    "sz000768","sz000776","sz000777","sz000778","sz000779","sz000780",
    "sz000782","sz000785","sz000786","sz000788","sz000789","sz000790",
    "sz000791","sz000792","sz000793","sz000795","sz000796","sz000797",
    "sz000798","sz000799","sz000800","sz000801","sz000802","sz000803",
    "sz000806","sz000807","sz000809","sz000810","sz000811","sz000812",
    "sz000813","sz000815","sz000816","sz000818","sz000819","sz000820",
    "sz000821","sz000822","sz000823","sz000825","sz000826","sz000828",
    "sz000829","sz000830","sz000831","sz000832","sz000833","sz000835",
    "sz000836","sz000837","sz000838","sz000839","sz000848","sz000850",
    "sz000851","sz000852","sz000856","sz000858","sz000859","sz000860",
    "sz000861","sz000862","sz000863","sz000868","sz000869","sz000875",
    "sz000876","sz000877","sz000878","sz000880","sz000881","sz000882",
    "sz000883","sz000885","sz000886","sz000887","sz000888","sz000889",
    "sz000890","sz000892","sz000893","sz000895","sz000897","sz000898",
    "sz000899","sz000900","sz000901","sz000902","sz000903","sz000905",
    "sz000906","sz000908","sz000909","sz000910","sz000911","sz000912",
    "sz000913","sz000915","sz000917","sz000918","sz000919","sz000920",
    "sz000921","sz000922","sz000923","sz000925","sz000926","sz000927",
    "sz000928","sz000929","sz000930","sz000931","sz000932","sz000933",
    "sz000935","sz000936","sz000937","sz000938","sz000939","sz000948",
    "sz000949","sz000950","sz000951","sz000952","sz000953","sz000955",
    "sz000957","sz000958","sz000959","sz000960","sz000961","sz000962",
    "sz000963","sz000965","sz000966","sz000967","sz000968","sz000969",
    "sz000970","sz000971","sz000972","sz000973","sz000975","sz000976",
    "sz000977","sz000978","sz000979","sz000980","sz000981","sz000982",
    "sz000983","sz000985","sz000987","sz000988","sz000989","sz000990",
    "sz000993","sz000995","sz000996","sz000997","sz000998","sz000999",
]

def scan_risks(batch_size=80):
    """扫描退市风险股票"""
    codes = RISK_WATCHLIST
    results = {"extreme": [], "high": [], "ok": 0, "err": 0}
    
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        try:
            url = "https://hq.sinajs.cn/list=" + ",".join(batch)
            raw = urllib.request.urlopen(urllib.request.Request(
                url, headers={"Referer": "https://finance.sina.com.cn"}), 
                timeout=10).read().decode("gbk")
            
            for line in raw.strip().split("\n"):
                if "=" not in line: continue
                code = line.split("=")[0].replace("var hq_str_","").strip()
                q = line.split('"')[1] if '"' in line else ""
                p = q.split(",")
                if len(p) < 4: results["err"] += 1; continue
                
                name, price = p[0], float(p[3]) if p[3] else 0
                
                if name.startswith("*ST"):
                    results["extreme"].append({"code":code,"name":name,"price":price,"risk":"退市风险警示(*ST)"})
                elif name.startswith("ST"):
                    results["high"].append({"code":code,"name":name,"price":price,"risk":"其他风险警示(ST)"})
                elif "退市" in name:
                    results["extreme"].append({"code":code,"name":name,"price":price,"risk":"已退市"})
                else:
                    results["ok"] += 1
            time.sleep(0.2)
        except Exception as e:
            results["err"] += 1
    
    results["total"] = results["ok"] + len(results["extreme"]) + len(results["high"]) + results["err"]
    return results

def summary(r):
    return {
        "total": r["total"],
        "extreme": len(r["extreme"]),
        "extreme_list": r["extreme"][:10],
        "high": len(r["high"]),
        "high_list": r["high"][:5],
        "ok": r["ok"],
        "err": r["err"]
    }

if __name__ == "__main__":
    r = scan_risks()
    s = summary(r)
    print(f"扫描 {s['total']} 只: 🔴{s['extreme']} 🟡{s['high']} 🟢{s['ok']} ❌{s['err']}")
    if s['extreme_list']:
        print("\n🔴 极高风险:")
        for item in s['extreme_list']:
            print(f"  {item['code']} {item['name']} ¥{item['price']:.2f}")
