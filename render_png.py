#!/usr/bin/env python3
"""HTML → PDF → PNG 长图 (多页合并，完整渲染)"""
import subprocess, tempfile
from pathlib import Path
import fitz

CHROME = "/Users/sound/.cache/puppeteer/chrome/mac_arm-149.0.7827.22/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"

def html_to_png(html_path, output_path, scale=2.0):
    """HTML→PDF→PNG 多页合并长图"""
    html_path = Path(html_path)
    output_path = Path(output_path)
    
    # 清理 Chrome 僵尸进程
    subprocess.run(["pkill", "-9", "-f", "Chrome for Testing"], capture_output=True)
    
    # Step 1: HTML→PDF
    pdf_path = output_path.with_suffix('.pdf')
    r = subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox",
                        f"--print-to-pdf={pdf_path}", "--no-pdf-header-footer",
                        f"file://{html_path}"],
                       capture_output=True, timeout=25)
    
    if not pdf_path.exists() or pdf_path.stat().st_size < 1000:
        raise RuntimeError(f"PDF生成失败")
    
    # Step 2: 全部页面渲染并竖向合并
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat)
        pages.append(pix)
    
    if len(pages) == 1:
        pages[0].save(str(output_path))
    else:
        # 竖向拼接
        total_height = sum(p.height for p in pages)
        max_width = max(p.width for p in pages)
        
        # 直接用第一个pixmap的方式拼
        import numpy as np
        full = np.zeros((total_height, max_width, pages[0].n), dtype=np.uint8)
        y = 0
        for pix in pages:
            samples = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            full[y:y+pix.height, :pix.width] = samples
            y += pix.height
        
        # 写入
        merged = fitz.Pixmap(fitz.csRGB, max_width, total_height, full.tobytes(), False)
        merged.save(str(output_path))
    
    doc.close()
    pdf_path.unlink()  # 清理PDF
    
    # 验证
    info = f"{len(pages)}页合并 → {max_width if len(pages)>1 else pages[0].width}x{total_height if len(pages)>1 else pages[0].height}"
    return str(output_path), info

def batch_render(stocks_data, title, output_name):
    rows = ""
    for ticker, d in stocks_data.items():
        color = "#3fb950" if d["change"] > 0 else "#f85149"
        arrow = "▲" if d["change"] > 0 else ("▼" if d["change"] < 0 else "—")
        rows += f'<tr><td>{arrow} {d["name"]}</td><td>{ticker}</td><td style="color:{color}">{d["price"]:.2f}</td><td style="color:{color}">{d["change"]:+.2f}%</td><td>{d["volume"]:,}</td></tr>'
    
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{{background:#0d1117;color:#e6edf3;font:16px -apple-system,sans-serif;padding:24px;max-width:600px;margin:0 auto}}
h1{{font-size:1.2em;border-bottom:1px solid #30363d;padding-bottom:8px}}
table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:.9em}}
th{{background:#21262d;color:#8b949e;padding:8px;text-align:left}}
td{{padding:8px;border-bottom:1px solid #30363d}}
.f{{text-align:center;color:#8b949e;font-size:.7em;margin-top:12px}}
</style></head><body>
<h1>{title}</h1><table><tr><th>股票</th><th>代码</th><th>价格</th><th>涨跌</th><th>成交量</th></tr>{rows}</table>
<div class="f">DAO量化助手 | 本地Ollama | 不构成投资建议</div>
</body></html>"""
    
    html_path = Path("/tmp") / f"bt_{output_name}.html"
    png_path = Path.home() / ".openclaw-autoclaw/workspace/reports" / f"{output_name}.png"
    html_path.write_text(html)
    result, info = html_to_png(html_path, png_path)
    html_path.unlink()
    print(f"✅ {result} ({info})")
    return result

if __name__ == "__main__":
    r, info = html_to_png(
        str(Path.home() / ".openclaw-autoclaw/workspace/reports/xnk.html"),
        str(Path.home() / ".openclaw-autoclaw/workspace/reports/xnk_full.png"),
        scale=2.0
    )
    print(f"✅ {r} ({info})")
