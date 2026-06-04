# DAO分析师 V3.1
"""管道阶段5: PNG导出 + 管道编排器"""
import subprocess, fitz, os, sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.fetcher import fetch, fetch_market
from pipeline.signals import analyze
from pipeline.render import stock as render_stock, market as render_market, nightly as render_nightly

MOBILE_VIEWPORT = True  # 手机端优化

CHROME = "/Users/sound/.cache/puppeteer/chrome/mac_arm-149.0.7827.22/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"

def to_png(html, path):
    html_path = path.replace(".png",".html")
    with open(html_path,"w") as f: f.write(html)
    subprocess.run(["pkill","-9","-f","Chrome for Testing"],capture_output=True)
    pdf = "/tmp/_pipe.pdf"
    subprocess.run([CHROME,"--headless","--disable-gpu","--no-sandbox",
        "--window-size=430,900",
        f"--print-to-pdf={pdf}","--no-pdf-header-footer",f"--print-to-pdf-no-header",f"file://{html_path}"],
        capture_output=True,timeout=25)
    doc=fitz.open(pdf); th=0; mw=0; pxs=[]
    for pg in doc: px=pg.get_pixmap(dpi=144); pxs.append(px); th+=px.height; mw=max(mw,px.width)
    mg=fitz.open(); mp=mg.new_page(width=mw,height=th); y=0
    for px in pxs: mp.insert_image(fitz.Rect(0,y,px.width,y+px.height),pixmap=px); y+=px.height
    mp.get_pixmap(dpi=144).save(path)
    doc.close(); mg.close(); Path(pdf).unlink()
    return path

def run_stock(code, use_llm=True):
    """个股全周期操盘手册"""
    print(f"📊 {code} 全周期操盘手册...")
    d = fetch(code, full=True)
    if "error" in d: return print(f"❌ {d['error']}")
    a = analyze(d)
    llm = ""
    if use_llm:
        print("  🧠 LLM分析...")
        from pipeline.llm import analyze as llm_analyze
        llm = llm_analyze(d, a)
    html = render_stock(d, a, llm)
    png = to_png(html, f"/tmp/pipe_stock_{code}.png")
    print(f"  ✅ {os.path.getsize(png)//1024}KB | 积分:0")
    return png

def run_market():
    """市场全景"""
    print("📊 市场全景...")
    d = fetch_market()
    html = render_market(d)
    png = to_png(html, "/tmp/pipe_market.png")
    print(f"  ✅ {os.path.getsize(png)//1024}KB | 积分:0")
    return png

def run_nightly():
    """深夜情报站"""
    print("🌙 深夜情报站...")
    d = fetch_market()
    html = render_nightly(d)
    png = to_png(html, "/tmp/pipe_nightly.png")
    print(f"  ✅ {os.path.getsize(png)//1024}KB | 积分:0")
    return png

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "stock"
    code = sys.argv[2] if len(sys.argv) > 2 else "002241"
    
    if mode == "stock": run_stock(code)
    elif mode == "market": run_market()
    elif mode == "nightly": run_nightly()
    else: print("用法: run.py stock|market|nightly [code]")
