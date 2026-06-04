#!/usr/bin/env python3
"""
专业报告模板引擎 V2.0
设计语言: Bloomberg Terminal × McKinsey Blue
布局: 卡片式分层 | 配色: 蓝灰主调 | 图表: 简洁叙事
"""
import json, os, sys, subprocess
from datetime import datetime
from pathlib import Path

class ReportTemplate:
    """专业金融报告HTML生成器"""
    
    CSS = """
    :root {
      --bg: #f5f7fa;
      --card-bg: #ffffff;
      --primary: #1a56db;
      --primary-light: #e8f0fe;
      --text: #1f2937;
      --text-secondary: #6b7280;
      --border: #e5e7eb;
      --green: #059669;
      --green-bg: #ecfdf5;
      --red: #dc2626;
      --red-bg: #fef2f2;
      --yellow: #d97706;
      --yellow-bg: #fffbeb;
      --blue: #2563eb;
      --blue-bg: #eff6ff;
      --radius: 10px;
      --shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    *{margin:0;padding:0;box-sizing:border-box}
    body{
      background:var(--bg);color:var(--text);
      font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','PingFang SC','Microsoft YaHei',sans-serif;
      font-size:14px;line-height:1.65;padding:0;max-width:680px;margin:0 auto;
    }
    .header{
      background:linear-gradient(135deg,#1e3a5f,#1a56db);
      color:#fff;padding:28px 24px 22px;text-align:center;
    }
    .header h1{font-size:20px;font-weight:700;margin-bottom:4px;letter-spacing:-0.3px}
    .header .meta{font-size:11px;opacity:0.75;margin-top:4px}
    .header .status-row{display:flex;justify-content:center;gap:16px;margin-top:12px}
    .header .status-badge{
      display:inline-flex;align-items:center;gap:4px;
      background:rgba(255,255,255,0.15);padding:3px 10px;border-radius:12px;font-size:11px;
      backdrop-filter:blur(4px);
    }
    .content{padding:20px 16px 30px}
    .card{
      background:var(--card-bg);border-radius:var(--radius);box-shadow:var(--shadow);
      padding:18px;margin-bottom:14px;border:1px solid var(--border);
    }
    .card-header{
      display:flex;align-items:center;gap:8px;margin-bottom:12px;
      padding-bottom:10px;border-bottom:1px solid var(--border);
    }
    .card-icon{font-size:18px}
    .card-title{font-size:15px;font-weight:700;color:var(--text)}
    .card-subtitle{font-size:11px;color:var(--text-secondary);margin-left:auto}
    
    /* 表格 */
    .table-wrap{overflow-x:auto}
    table{width:100%;border-collapse:collapse;font-size:13px}
    th{
      background:var(--primary-light);color:var(--primary);
      text-align:left;padding:9px 10px;font-weight:600;font-size:11px;
      text-transform:uppercase;letter-spacing:0.5px;
    }
    td{padding:8px 10px;border-bottom:1px solid var(--border)}
    tr:last-child td{border-bottom:none}
    tr:hover td{background:#f9fafb}
    .num{text-align:right;font-variant-numeric:tabular-nums}
    
    /* 颜色标记 */
    .up{color:var(--green);font-weight:600}
    .down{color:var(--red);font-weight:600}
    .neutral{color:var(--text-secondary)}
    .limit-up{color:var(--red);font-weight:700}
    .limit-down{color:var(--green);font-weight:700}
    
    /* 标签 */
    .badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600}
    .badge-green{background:var(--green-bg);color:var(--green)}
    .badge-red{background:var(--red-bg);color:var(--red)}
    .badge-yellow{background:var(--yellow-bg);color:var(--yellow)}
    .badge-blue{background:var(--blue-bg);color:var(--blue)}
    
    /* KPI 指标卡 */
    .kpi-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:8px 0}
    .kpi-card{
      background:var(--card-bg);border:1px solid var(--border);border-radius:8px;
      padding:12px;text-align:center;
    }
    .kpi-value{font-size:20px;font-weight:800;letter-spacing:-0.5px}
    .kpi-label{font-size:10px;color:var(--text-secondary);margin-top:2px;text-transform:uppercase}
    .kpi-change{font-size:11px;margin-top:2px}
    
    /* 分隔线 */
    .divider{height:1px;background:var(--border);margin:14px 0}
    
    /* 建议框 */
    .advice{
      border-left:3px solid var(--primary);background:var(--primary-light);
      padding:12px 16px;border-radius:0 8px 8px 0;margin:12px 0;font-size:13px;
    }
    .advice-title{font-weight:700;color:var(--primary);margin-bottom:4px}
    
    /* 二维对比 */
    .dual-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    .mini-card{background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:12px}
    .mini-card .title{font-size:12px;font-weight:700;margin-bottom:6px}
    
    /* 信号指示 */
    .signal-row{display:flex;align-items:center;gap:6px;padding:4px 0;font-size:13px}
    .signal-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
    .dot-green{background:var(--green)}
    .dot-red{background:var(--red)}
    .dot-yellow{background:var(--yellow)}
    .dot-blue{background:var(--blue)}
    
    /* 页脚 */
    .footer{
      text-align:center;color:var(--text-secondary);font-size:10px;
      padding:20px;border-top:1px solid var(--border);margin-top:10px;
    }
    
    /* 进度条 */
    .progress-bar{height:5px;background:var(--border);border-radius:3px;overflow:hidden;margin:6px 0}
    .progress-fill{height:100%;border-radius:3px;transition:width 0.3s}
    
    @media(max-width:480px){
      .kpi-grid{grid-template-columns:repeat(2,1fr)}
      .dual-grid{grid-template-columns:1fr}
      body{font-size:13px}
    }
    """
    
    @classmethod
    def _doc_head(cls, title, date_str, subtitle=""):
        return f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>{cls.CSS}</style></head>
<body>
<div class="header">
  <h1>{title}</h1>
  <div class="meta">{date_str}{' · ' + subtitle if subtitle else ''}</div>
</div>
<div class="content">"""
    
    @classmethod
    def _doc_foot(cls):
        return """</div>
<div class="footer">DAO量化助手 V3.1 · 自动生成 · 数据仅供参考不构成投资建议</div>
</body></html>"""
    
    @classmethod
    def kpi_cards(cls, items):
        """items: [(value, label, change_str, change_class), ...]"""
        html = '<div class="kpi-grid">'
        for val, label, change, cls_name in items:
            html += f"""<div class="kpi-card">
  <div class="kpi-value">{val}</div>
  <div class="kpi-label">{label}</div>
  <div class="kpi-change {cls_name}">{change}</div>
</div>"""
        html += '</div>'
        return html
    
    @classmethod
    def card(cls, icon, title, content, subtitle=""):
        sub = f'<span class="card-subtitle">{subtitle}</span>' if subtitle else ''
        return f"""<div class="card">
<div class="card-header"><span class="card-icon">{icon}</span><span class="card-title">{title}</span>{sub}</div>
{content}</div>"""
    
    @classmethod
    def table(cls, headers, rows, alignments=None):
        """headers: [col_name], rows: [[val,...]], alignments: ['left'|'right'|'center']"""
        if not alignments:
            alignments = ['left'] * len(headers)
        html = '<div class="table-wrap"><table><thead><tr>'
        for h, a in zip(headers, alignments):
            html += f'<th style="text-align:{a}">{h}</th>'
        html += '</tr></thead><tbody>'
        for row in rows:
            html += '<tr>'
            for cell, a in zip(row, alignments):
                html += f'<td class="num" style="text-align:{a}">{cell}</td>' if a == 'right' else f'<td>{cell}</td>'
            html += '</tr>'
        html += '</tbody></table></div>'
        return html
    
    @classmethod
    def advice(cls, title, text):
        return f'<div class="advice"><div class="advice-title">{title}</div>{text}</div>'
    
    @classmethod
    def signal(cls, color, text):
        return f'<div class="signal-row"><span class="signal-dot dot-{color}"></span>{text}</div>'
    
    @classmethod
    def badge(cls, text, color="blue"):
        return f'<span class="badge badge-{color}">{text}</span>'

# ═══════════════════════════════════
# 市场报告生成
# ═══════════════════════════════════
def generate_market_report(data=None):
    """生成完整市场报告HTML"""
    now = datetime.now()
    R = ReportTemplate
    
    html = R._doc_head("📊 市场报告", now.strftime("%Y年%m月%d日"), "V3.1 · 五源数据")
    
    # KPI概览
    html += R.kpi_cards([
        ("-1.4%", "上周大盘", "震荡下行", "down"),
        ("65%", "建议仓位", "中性偏保守", "neutral"),
        ("5只", "候选通过", "雪球+腾讯验证", "up"),
        ("¥20,000", "可用资金", "2万上限", "neutral"),
        ("7/370", "积分余额", "充足", "up"),
        ("✅", "Cron管道", "5条就绪", "up"),
    ])
    
    # 大盘走势
    html += R.card("📈", "上周大盘 (5/25-5/29)", 
        R.table(
            ["日期", "上证指数", "涨跌", "信号"],
            [
                ["周一 5/25", "4,153", '<span class="up">+0.6%</span>', R.badge("偏强","green")],
                ["周二 5/26", "4,145", '<span class="up">+0.2%</span>', R.badge("震荡","yellow")],
                ["周三 5/27", "4,094", '<span class="down">-1.1%</span>', R.badge("回调","red")],
                ["周四 5/28", "4,099", '<span class="up">+0.4%</span>', R.badge("反弹","green")],
                ["周五 5/29", "4,069", '<span class="down">-1.0%</span>', R.badge("收阴","red")],
                ["<b>全周</b>", "<b>4,126→4,069</b>", '<span class="down"><b>-1.4%</b></span>', R.badge("偏弱","red")],
            ],
            ["left","right","right","center"]
        ),
        "震荡下行"
    )
    
    html += R.advice("📋 大盘研判", 
        "连续两周收阴，周五放量下跌。周一大概率低开或平开，关注4060支撑位。若开盘站稳4080上方可适度乐观，破4050需警惕加速下跌。建议65%仓位起跳，盘中根据市场温度调整。")
    
    # 自选股
    html += R.card("⭐", "自选股表现", 
        R.table(
            ["类型", "名称", "代码", "涨跌"],
            [
                ["📈", "金螳螂", "002081", '<span class="limit-up">+10.0% 涨停</span>'],
                ["📈", "华电能源", "600726", '<span class="limit-up">+10.0% 涨停</span>'],
                ["📈", "大唐发电", "601991", '<span class="up">+7.9%</span>'],
                ["📈", "浙能电力", "600023", '<span class="up">+6.1%</span>'],
                ["📈", "韶能股份", "000601", '<span class="up">+5.5%</span>'],
                ["📉", "华天科技", "002185", '<span class="limit-down">-10.0% 跌停</span>'],
                ["📉", "盈方微", "000670", '<span class="limit-down">-10.0% 跌停</span>'],
            ],
            ["left","left","left","right"]
        )
    )
    
    # 雪球热度
    html += R.card("🔥", "雪球社区热度",
        R.table(
            ["排名", "名称", "代码", "涨跌", "判定"],
            [
                ["🥇", "博杰股份", "002975", '<span class="up">+7.5%</span>', R.badge("PE过高","red")],
                ["🥈", "风华高科", "000636", '<span class="up">+9.0%</span>', R.badge("PE200","red")],
                ["🥉", "京东方A", "000725", '<span class="limit-down">-10.0%</span>', R.badge("跌停","red")],
                ["5", "生益科技", "600183", '<span class="up">+3.7%</span>', R.badge("备选","green")],
                ["6", "春秋电子", "603890", '<span class="limit-up">+10.0%</span>', R.badge("买入","green")],
                ["—", "长江电力", "600900", '<span class="up">+1.9%</span>', R.badge("买入","green")],
            ],
            ["center","left","left","right","center"]
        )
    )
    
    # 周一计划
    html += R.card("🎯", "周一建仓计划",
        '<div class="dual-grid">'
        f'<div class="mini-card"><div class="title">🏭 长江电力 600900</div>'
        f'<div class="signal-row"><span class="signal-dot dot-green"></span>¥27.75 × 200股 = ¥5,550 (28%)</div>'
        f'<div class="signal-row"><span class="signal-dot dot-blue"></span>PE=19 · 风险评分 0/10</div>'
        f'<div class="signal-row"><span class="signal-dot dot-yellow"></span>止损: 2×ATR动态</div>'
        f'</div>'
        f'<div class="mini-card"><div class="title">📱 春秋电子 603890</div>'
        f'<div class="signal-row"><span class="signal-dot dot-green"></span>¥24.81 × 300股 = ¥7,443 (37%)</div>'
        f'<div class="signal-row"><span class="signal-dot dot-blue"></span>PE=36 · 涨停次日谨慎</div>'
        f'<div class="signal-row"><span class="signal-dot dot-yellow"></span>止损: 2×ATR动态</div>'
        f'</div>'
        '</div>'
        '<div style="margin-top:10px;text-align:center;font-weight:700;color:var(--primary)">'
        '总仓: ¥12,993 (65%) · 备金: ¥7,007 · 止盈: +15%卖50%'
        '</div>'
    )
    
    # 系统状态
    html += R.card("⚙️", "V3.1 系统状态",
        '<div class="signal-row"><span class="signal-dot dot-green"></span>仓位管理: 市场温度动态 15-100%</div>'
        '<div class="signal-row"><span class="signal-dot dot-green"></span>止盈止损: 四维统一引擎(ATR+浮动+时间+大盘)</div>'
        '<div class="signal-row"><span class="signal-dot dot-green"></span>免费筛选: 五源全市场(雪球+腾讯+通达信+东财+妙想)</div>'
        '<div class="signal-row"><span class="signal-dot dot-green"></span>持仓调度: 当日有效+切换收益对比</div>'
        '<div class="signal-row"><span class="signal-dot dot-green"></span>Cron管道: 5条全就绪(08:30→23:00)</div>'
        '<div class="signal-row"><span class="signal-dot dot-yellow"></span>东财人气榜: 今晚限流(开盘恢复)</div>'
        '<div class="progress-bar"><div class="progress-fill" style="width:100%;background:var(--green)"></div></div>'
        '<div style="font-size:11px;color:var(--text-secondary)">系统健康度: 100% · 模块: 23个 · 积分: 7/370</div>'
    )
    
    html += R._doc_foot()
    return html


def render_to_png(html_path, output_path):
    """渲染HTML到PNG长图"""
    import subprocess, fitz
    from pathlib import Path
    
    chrome = "/Users/sound/.cache/puppeteer/chrome/mac_arm-149.0.7827.22/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
    
    subprocess.run(["pkill", "-9", "-f", "Chrome for Testing"], capture_output=True)
    
    pdf_path = Path(output_path).with_suffix('.pdf')
    r = subprocess.run([chrome, "--headless", "--disable-gpu", "--no-sandbox",
                        f"--print-to-pdf={pdf_path}", "--no-pdf-header-footer",
                        f"file://{html_path}"],
                       capture_output=True, timeout=25)
    
    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pix = page.get_pixmap(dpi=200)
        pages.append(pix.tobytes("png"))
    
    # 合并为长图
    from PIL import Image
    from io import BytesIO
    images = [Image.open(BytesIO(p)) for p in pages]
    total_height = sum(img.height for img in images)
    max_width = max(img.width for img in images)
    merged = Image.new("RGB", (max_width, total_height), "#f5f7fa")
    y = 0
    for img in images:
        merged.paste(img, (0, y))
        y += img.height
    merged.save(output_path, "PNG", optimize=True)
    doc.close()
    pdf_path.unlink()
    return True


if __name__ == "__main__":
    # 生成HTML
    html = generate_market_report()
    html_path = "/tmp/market_report_v2.html"
    with open(html_path, "w") as f:
        f.write(html)
    print(f"✅ HTML: {html_path}")
    
    # 渲染PNG
    if len(sys.argv) > 1 and sys.argv[1] == "--png":
        png_path = "/tmp/market_report_v2.png"
        render_to_png(html_path, png_path)
        print(f"✅ PNG: {png_path}")
