#!/usr/bin/env python3
"""本地全自动报告管线 — 零积分消耗"""
import subprocess, json, sys, os, tempfile, time
from datetime import datetime
from pathlib import Path

SCRIPTS = Path.home() / ".openclaw-autoclaw/skills/a-stock-analysis/scripts"
CHROME = "/Users/sound/.cache/puppeteer/chrome/mac_arm-149.0.7827.22/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
OLLAMA = Path.home() / ".local/bin/ollama"
OUTDIR = Path.home() / ".openclaw-autoclaw/workspace/reports"
OUTDIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = Path.home() / "dao-analyst/cache/data_cache.json"
CACHE_TTL = 300  # 5分钟缓存

def load_cache():
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text())
            if time.time() - data.get("ts", 0) < CACHE_TTL:
                return data.get("stocks", {})
        except: pass
    return {}

def save_cache(stocks):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps({"ts": time.time(), "stocks": stocks}, ensure_ascii=False))

def get_price(ticker, use_cache=True):
    """获取价格（带缓存）"""
    cache = load_cache() if use_cache else {}
    if ticker in cache:
        return cache[ticker]
    try:
        r = subprocess.run(["python3", str(SCRIPTS/"analyze.py"), ticker, "--json"],
                          capture_output=True, text=True, timeout=30)
        data = json.loads(r.stdout)[0]
        rt = data["realtime"]
        return {"name": data["name"], "price": rt["price"], "change": rt["change_pct"],
                "open": rt["open"], "high": rt["high"], "low": rt["low"],
                "volume": rt["volume"], "amount": rt["amount"]}
    except:
        return None

def batch_analyze(tickers, use_cache=True):
    """批量获取价格并缓存"""
    results = {}
    for t in tickers:
        print(f"  📡 {t}...", end=" ", flush=True)
        d = get_price(t, use_cache)
        if d:
            results[t] = d
            print(f"¥{d['price']} ({d['change']:+.1f}%)")
        else:
            print("❌")
    save_cache(results)
    return results

def ollama_analyze(stocks_data, model="qwen3:14b"):
    """本地 Ollama 快速分析"""
    if not stocks_data:
        return ""
    lines = []
    for ticker, d in stocks_data.items():
        lines.append(f"{d['name']}({ticker}): ¥{d['price']} {d['change']:+.1f}% 量{d['volume']}手")
    summary = "\n".join(lines)
    
    prompt = f"""你是A股分析师。以下是最新行情数据，请用3句话总结：
1. 整体市场情绪（看多/看空/震荡）
2. 最值得关注的1-2只
3. 主要风险提示

数据：
{summary}
"""
    try:
        r = subprocess.run([str(OLLAMA), "run", model, prompt],
                          capture_output=True, text=True, timeout=60)
        return r.stdout.strip()
    except:
        return "⚠️ 本地模型超时，请稍后重试"

def data_render(tickers_data, analysis_text, output_name="report"):
    """渲染HTML报告并截图"""
    now = datetime.now().strftime("%m-%d %H:%M")
    
    rows = ""
    for ticker, d in tickers_data.items():
        arrow = "🔺" if d["change"] > 0 else "🔻" if d["change"] < 0 else "➖"
        rows += f"""<tr><td>{arrow} {d['name']}</td><td>{ticker}</td>
        <td style='color:{"#3fb950" if d["change"]>0 else "#f85149"}'>{d['price']:.2f}</td>
        <td style='color:{"#3fb950" if d["change"]>0 else "#f85149"}'>{d['change']:+.2f}%</td>
        <td>{d['volume']:,}</td><td>{d['amount']/1e8:.1f}亿</td></tr>"""
    
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
:root{{--bg:#0d1117;--card:#161b22;--text:#e6edf3;--t2:#8b949e;--g:#3fb950;--r:#f85149}}
body{{background:var(--bg);color:var(--text);font:15px/1.6 -apple-system,sans-serif;padding:20px;max-width:700px;margin:0 auto}}
h1{{font-size:1.2em;border-bottom:1px solid #30363d;padding-bottom:8px}}
table{{width:100%;border-collapse:collapse;font-size:.85em;margin:12px 0}}
th{{background:#21262d;color:var(--t2);padding:8px;text-align:left;border-bottom:2px solid #30363d}}
td{{padding:8px;border-bottom:1px solid #30363d}}
.card{{background:var(--card);border:1px solid #30363d;border-radius:6px;padding:14px;margin:10px 0}}
.analysis{{font-size:.88em;line-height:1.7;white-space:pre-wrap}}
.footer{{text-align:center;color:var(--t2);font-size:.7em;margin-top:16px;padding-top:8px;border-top:1px solid #30363d}}
</style></head><body>
<h1>📊 本地报告 | {now}</h1>
<div class="card"><table>
<tr><th>股票</th><th>代码</th><th>价格</th><th>涨跌</th><th>成交量</th><th>成交额</th></tr>
{rows}</table></div>
<div class="card"><div class="analysis">{analysis_text}</div></div>
<div class="footer">本地 Ollama 生成 | DAO量化助手 | ⚠️不构成投资建议</div>
</body></html>"""
    
    html_path = OUTDIR / f"{output_name}.html"
    png_path = OUTDIR / f"{output_name}.png"
    html_path.write_text(html)
    
    # 渲染截图
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox",
                    f"--screenshot={png_path}", f"--window-size=720,800",
                    f"file://{html_path}"], capture_output=True, timeout=30)
    
    return str(png_path) if png_path.exists() else None

# === CLI ===
if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["002015","000600","000733"]
    
    print("🚀 本地管线启动\n")
    
    # 1. 批量获取价格
    print("📡 拉取行情...")
    data = batch_analyze(tickers)
    if not data:
        print("❌ 数据获取失败")
        sys.exit(1)
    
    # 2. 本地 Ollama 分析
    print("\n🧠 本地 Ollama 分析...")
    analysis = ollama_analyze(data)
    print(f"  ✅ {len(analysis)} 字符")
    
    # 3. 渲染报告
    print("\n📸 渲染报告...")
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    png = data_render(data, analysis, f"local_{ts}")
    if png:
        print(f"  ✅ {png}")
    else:
        print("  ⚠️ 截图失败，HTML 已保存")
    
    print(f"\n💰 本次消耗: 0 积分 | 全部本地运行")

# 修复：用 PDF→PNG 两步法替代截图
from render_png import batch_render, html_to_png
