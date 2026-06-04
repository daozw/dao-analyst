#!/usr/bin/env python3
"""双模型交叉验证引擎 — Qwen3快 + R1深 → 决策置信度"""
import subprocess, json, time

OLLAMA = "/Users/sound/.local/bin/ollama"

def query(model, prompt, timeout=90):
    """调用 Ollama 模型"""
    start = time.time()
    try:
        r = subprocess.run([OLLAMA, "run", model, prompt],
                          capture_output=True, text=True, timeout=timeout)
        elapsed = time.time() - start
        text = r.stdout.strip()
        # 提取关键判断词
        keywords = {"买": 0, "观望": 0, "卖": 0, "空仓": 0}
        for k in keywords:
            if k in text:
                keywords[k] = 1
        return {"model": model, "text": text[:200], "verdict": keywords,
                "time": elapsed, "success": True}
    except Exception as e:
        return {"model": model, "text": str(e)[:100], "verdict": {},
                "time": time.time()-start, "success": False}

def cross_validate(stock_name, stock_code, context=""):
    """双模型交叉验证"""
    prompt = f"""分析{stock_name}({stock_code})当前是否值得买入。
{context}
请用一句话给出最终判断：买/观望/卖，并简要说明理由。"""
    
    print(f"🔍 交叉验证: {stock_name}({stock_code})")
    
    # 并行查询（实际是串行，Ollama不支持并行）
    qwen = query("qwen3:14b", prompt, timeout=45)
    print(f"  Qwen3: {'✅' if qwen['success'] else '❌'} ({qwen['time']:.0f}s)")
    
    r1 = query("deepseek-r1:14b", prompt, timeout=90)
    print(f"  R1:    {'✅' if r1['success'] else '❌'} ({r1['time']:.0f}s)")
    
    # 计算共识
    if qwen["success"] and r1["success"]:
        agree = qwen["verdict"] == r1["verdict"]
        confidence = "高" if agree else "中"
        verdict = qwen["verdict"] if agree else "分歧"
        print(f"  📊 共识: {'一致' if agree else '分歧'} → 置信度:{confidence}")
    else:
        agree = False
        confidence = "低"
        verdict = {"观望": 1}
        print(f"  ⚠️ 模型调用失败 置信度:低")
    
    return {
        "stock": f"{stock_name}({stock_code})",
        "qwen": qwen,
        "r1": r1,
        "agree": agree,
        "confidence": confidence,
        "verdict": verdict,
    }

if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "浙江世宝"
    code = sys.argv[2] if len(sys.argv) > 2 else "002703"
    ctx = sys.argv[3] if len(sys.argv) > 3 else ""
    
    result = cross_validate(name, code, ctx)
    
    # 输出 JSON
    print(f"\n{json.dumps({k:v for k,v in result.items() if k not in ('qwen','r1')}, ensure_ascii=False, indent=2)}")
    print(f"\nQwen3: {result['qwen']['text'][:100]}")
    print(f"R1:    {result['r1']['text'][:100]}")
