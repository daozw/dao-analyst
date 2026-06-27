#!/usr/bin/env python3
"""TradingAgents 集成 — 对候选池做AI验证打分"""
import os, sys, json
from datetime import date

sys.path.insert(0, os.path.expanduser("~/dao-analyst/astock"))
os.environ["OPENAI_API_KEY"] = "ollama"
os.environ["TRADINGAGENTS_LLM_PROVIDER"] = "ollama"
os.environ["TRADINGAGENTS_QUICK_THINK_LLM"] = "qwen2.5:3b"
os.environ["TRADINGAGENTS_DEEP_THINK_LLM"] = "qwen2.5:3b"
os.environ["TRADINGAGENTS_BACKEND_URL"] = "http://localhost:11434/v1"
os.environ["TRADINGAGENTS_OUTPUT_LANGUAGE"] = "Chinese"

from tradingagents.graph.trading_graph import TradingAgentsGraph

STATE_FILE = os.path.expanduser("~/dao-analyst/data/state/ta_scores.json")

def analyze_candidates(candidates, max_stocks=3):
    """对候选池跑多分析师验证,返回评分"""
    graph = TradingAgentsGraph()
    results = {}
    
    for i, c in enumerate(candidates[:max_stocks]):
        code = c.get('code', '')
        name = c.get('name', code)
        print(f"[{i+1}/{min(len(candidates),max_stocks)}] 分析 {name}({code})...")
        try:
            result = graph.propagate(
                company_name=name,
                trade_date=date.today().isoformat(),
                
            )
            results[code] = {
                'name': name,
                'score': result.get('final_decision', {}).get('score', 0),
                'decision': str(result.get('final_decision', {}))[:200],
                'time': date.today().isoformat()
            }
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            results[code] = {'name': name, 'score': 0, 'error': str(e)[:100]}
    
    # Save
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump({'date': date.today().isoformat(), 'results': results}, f, ensure_ascii=False, indent=2)
    
    return results

if __name__ == '__main__':
    # Get candidates from signal pool or pywencai
    candidates = []
    # Try pywencai first
    try:
        wc = json.load(open(os.path.expanduser('~/dao-analyst/data/state/pywencai_candidates.json')))
        band = wc.get('band', [])[:5]
        for code in band:
            candidates.append({'code': code, 'name': code})
    except:
        pass
    
    if not candidates:
        print("无候选,使用默认测试: 贵州茅台")
        candidates = [{'code': '600519', 'name': '贵州茅台'}]
    
    results = analyze_candidates(candidates, max_stocks=3)
    print(f"\n✅ 完成: {len(results)}只")
    for code, r in results.items():
        print(f"  {r['name']}({code}): 评分={r.get('score','?')}")
