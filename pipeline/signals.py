"""管道阶段2: 信号计算 — 价位/信号/风险评分"""
import math

def analyze(d):
    """输入fetcher数据, 输出信号+价位+判定"""
    p=d["price"]; chg=d["chg"]; pe=d.get("pe",0); to=d.get("turnover",0)
    ma5=d.get("ma5",p); ma20=d.get("ma20",p); atr=d.get("atr",p*0.03)
    fund=d.get("fund")
    
    sigs=[]
    # PE
    if 0<pe<30: sigs.append({"label":"PE估值","val":f"{pe:.0f}","tag":"低估","lv":"g"})
    elif 30<=pe<60: sigs.append({"label":"PE估值","val":f"{pe:.0f}","tag":"合理","lv":"y"})
    elif pe>=60: sigs.append({"label":"PE估值","val":f"{pe:.0f}","tag":"偏高","lv":"r"})
    else: sigs.append({"label":"PE估值","val":"-","tag":"无数据","lv":"n"})
    # 趋势
    if chg>=3: sigs.append({"label":"价格趋势","val":f"{chg:+.1f}%","tag":"强势","lv":"g"})
    elif chg>=0: sigs.append({"label":"价格趋势","val":f"{chg:+.1f}%","tag":"震荡","lv":"y"})
    else: sigs.append({"label":"价格趋势","val":f"{chg:+.1f}%","tag":"走弱","lv":"r"})
    # 换手
    if 3<=to<=8: sigs.append({"label":"换手率","val":f"{to:.1f}%","tag":"活跃","lv":"g"})
    elif to>15: sigs.append({"label":"换手率","val":f"{to:.1f}%","tag":"异常","lv":"r"})
    else: sigs.append({"label":"换手率","val":f"{to:.1f}%","tag":"正常","lv":"y"})
    # MA5
    if p>ma5: sigs.append({"label":"MA5均线","val":f"¥{ma5:.2f}","tag":"短多","lv":"g"})
    else: sigs.append({"label":"MA5均线","val":f"¥{ma5:.2f}","tag":"短空","lv":"r"})
    # MA20
    if p>ma20: sigs.append({"label":"MA20均线","val":f"¥{ma20:.2f}","tag":"中多","lv":"g"})
    else: sigs.append({"label":"MA20均线","val":f"¥{ma20:.2f}","tag":"中空","lv":"y"})
    # 主力
    if fund:
        n=fund["net"]
        if n>5000: sigs.append({"label":"主力资金","val":f"+{n:.0f}万","tag":"做多","lv":"g"})
        elif n>0: sigs.append({"label":"主力资金","val":f"+{n:.0f}万","tag":"小幅流入","lv":"y"})
        elif n>-5000: sigs.append({"label":"主力资金","val":f"{n:.0f}万","tag":"小幅流出","lv":"y"})
        else: sigs.append({"label":"主力资金","val":f"{n:.0f}万","tag":"出逃","lv":"r"})
    else: sigs.append({"label":"主力资金","val":"-","tag":"待更新","lv":"n"})
    
    gn=sum(1 for s in sigs if s["lv"]=="g"); rn=sum(1 for s in sigs if s["lv"]=="r")
    if gn>=4 and rn==0: v,vc="强烈推荐","#dc2626"
    elif gn>=3: v,vc="推荐关注","#2563eb"
    elif gn>=2: v,vc="谨慎观望","#d97706"
    else: v,vc="暂不建议","#059669"
    
    sl=round(p-2*atr,2); tp1=round(p*1.08,2); tp2=round(p*1.15,2)
    
    return {
        "signals":sigs,"verdict":v,"verdict_color":vc,
        "g":gn,"r":rn,"total":len(sigs),
        "prices":{
            "high_sell":round(d["resistance"],2),
            "breakthrough":round(d["resistance"]*1.02,2),
            "current":p,
            "first_entry":round(d["support"],2),
            "golden_pit":round(d["support"]*0.97,2),
            "stop_loss":sl,
            "take_profit_1":tp1,"take_profit_2":tp2
        }
    }
