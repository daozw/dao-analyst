#!/usr/bin/env python3
"""A股交易报告 V5 — 黑体加粗，完整无缺失"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from datetime import datetime

W = 1050
BG = (13, 17, 23)
CARD_BG = (22, 27, 34)
BORDER = (48, 54, 61)
TEXT = (230, 237, 243)
T2 = (139, 148, 158)
RED = (248, 81, 73)
GREEN = (63, 185, 80)
BLUE = (88, 166, 255)
YELLOW = (210, 153, 29)

P, GAP = 22, 14  # 边距, 卡片间距

def _f(size):
    try:
        return ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", size)
    except:
        return ImageFont.load_default()

def _card(draw, y, h):
    draw.rectangle([P, y, W-P, y+h], fill=CARD_BG, outline=BORDER, width=1)

def _section(draw, y, title):
    f = _f(26)
    tw = draw.textbbox((0,0), title, font=f)[2]
    draw.rectangle([P, y, P+5, y+32], fill=BLUE)
    draw.text((P+18, y-2), title, fill=BLUE, font=f)
    draw.line([P+16+tw+12, y+12, W-P, y+12], fill=BORDER, width=1)
    return y + 40, 40  # 返回新y和已用高度

def make_report(name, ticker, data):
    up = data["change"] > 0
    clr, arrow = (RED, "▲") if up else (GREEN, "▼") if data["change"] < 0 else (TEXT, "—")
    
    # === 精确计算高度 ===
    total = 120  # 标题+行情
    total += 50 + len(data.get("funds",[])) * 30 + 20  # 主力
    total += 50 + 60  # 暗盘
    total += 50 + 120  # 财务
    news = data.get("news", [])
    if news: total += 50 + len(news) * 32 + 20
    total += 50 + len(data.get("targets",[])) * 30 + 20  # 目标
    total += 50 + len(data.get("strategy",[])) * 30 + 20  # 策略
    total += 50 + len(data.get("factors",[])) * 28 + 20  # 因素
    # 主力行为分析
    behav = data.get("behavior", {})
    if behav.get("retail"): total += 140
    if behav.get("signals"): total += 50 + len(behav["signals"]) * 28 + 20
    total += 80
    total += 40
    
    img = Image.new("RGBA", (W, total + 60), BG + (255,))
    draw = ImageDraw.Draw(img)
    y = P
    
    # ═══ 标题 ═══
    f34 = _f(34); f22 = _f(22); f16 = _f(16); f14 = _f(14)
    f48 = _f(48); f30 = _f(30)
    
    draw.text((P, y), f"{arrow} {name}", fill=(255,255,255), font=f34)
    tw = f30.getbbox(name)[2]
    draw.text((P+tw+20, y+7), f"{ticker}.SZ", fill=T2, font=f22)
    
    draw.text((P, y+40), f"{data.get('price', 0) if isinstance(data.get('price'), (int,float)) else 0:.2f}", fill=clr, font=f48)
    draw.text((P+200, y+58), f"{data['change']:+.2f}%", fill=clr, font=f30)
    y += 108
    
    # ═══ 行情 ═══
    ch = 60
    _card(draw, y, ch)
    info = f"今开 {data['opr']:.2f}  │  最高 {data['high']:.2f}  │  最低 {data['low']:.2f}  │  成交 {data['amount']/1e8:.1f}亿  │  换手 {data.get('turnover',0):.1f}%"
    draw.text((P+20, y+18), info, fill=T2, font=f22)
    y += ch + GAP
    
    # ═══ 主力 ═══
    y, _ = _section(draw, y, "💸 主力资金")
    funds = data.get("funds", [])
    fh = len(funds) * 30 + 20
    _card(draw, y, fh)
    yc = y + 12
    for date, close, net, note in funds:
        nc = RED if net > 0 else GREEN
        ns = "+" if net > 0 else ""
        draw.text((P+18, yc), date, fill=T2, font=f16)
        draw.text((P+90, yc), f"¥{close:.2f}", fill=TEXT, font=f22)
        draw.text((P+220, yc), f"{ns}{net:.2f}亿", fill=nc, font=f22)
        draw.text((P+380, yc), note, fill=T2, font=f16)
        yc += 30
    y += fh + GAP
    
    # ═══ 暗盘 ═══
    y, _ = _section(draw, y, "🔍 暗盘监控")
    dp = data.get("dark_pool", {})
    dh = 60
    _card(draw, y, dh)
    items = [
        (f"融资余额 {dp.get('financing','--')}", BLUE),
        (f"融券余额 {dp.get('short','--')}", YELLOW),
        (f"质押比例 {dp.get('pledge','--')}", RED),
        (f"大宗交易 {dp.get('big_trade','--')}", T2),
    ]
    for i, (txt, cl) in enumerate(items):
        x = P + 14 + (i % 2) * 460
        yy = y + 10 + (i // 2) * 28
        draw.text((x, yy), txt, fill=cl, font=f22)
    y += dh + GAP
    
    # ═══ 财务 ═══
    y, _ = _section(draw, y, "💰 核心财务")
    ff = data.get("finance", {})
    fh = 120
    _card(draw, y, fh)
    draw.text((P+14, y+12), f"2026Q1  营收 {ff.get('q1_rev','')}亿  净利 {ff.get('q1_net','')}亿  毛利率 {ff.get('q1_gm','')}%", fill=TEXT, font=f22)
    draw.text((P+14, y+42), f"2025FY  营收 {ff.get('fy_rev','')}亿  净利 {ff.get('fy_net','')}亿  ROE {ff.get('fy_roe','')}%", fill=TEXT, font=f22)
    draw.text((P+14, y+74), ff.get('good',''), fill=RED, font=_f(19))
    draw.text((P+14, y+100), ff.get('risk',''), fill=GREEN, font=_f(19))
    y += fh + GAP
    
    # ═══ 最新动态 ═══
    if news:
        y, _ = _section(draw, y, "📰 最新动态")
        nh = len(news) * 32 + 20
        _card(draw, y, nh)
        yc = y + 12
        for date, text in news:
            draw.text((P+18, yc), date, fill=T2, font=f16)
            draw.text((P+86, yc), text, fill=TEXT, font=f22)
            yc += 32
        y += nh + GAP
    
    # ═══ 目标价 ═══
    y, _ = _section(draw, y, "🎯 目标价分析")
    targets = data.get("targets", [])
    th = len(targets) * 30 + 20
    _card(draw, y, th)
    yc = y + 12
    for level, price_str, logic in targets:
        lclr = RED if "阻力" in level else GREEN if "支撑" in level else BLUE
        tag = "🔴" if "阻力" in level else "🟢" if "支撑" in level else "🔵"
        draw.text((P+18, yc), f"{tag}  {level}", fill=lclr, font=f22)
        draw.text((P+220, yc), f"¥{price_str}", fill=lclr, font=_f(24))
        draw.text((P+400, yc), logic, fill=T2, font=f16)
        yc += 30
    y += th + GAP
    
    # ═══ 操作策略 ═══
    y, _ = _section(draw, y, "📋 精准操作策略")
    strategy = data.get("strategy", [])
    sh = len(strategy) * 30 + 20
    _card(draw, y, sh)
    yc = y + 12
    for scenario, condition, action in strategy:
        emoji = {"弱势":"📉","震荡":"📊","反弹":"📈","转强":"🚀","突破":"🚀"}.get(scenario,"•")
        draw.text((P+18, yc), f"{emoji} {scenario}", fill=TEXT, font=f22)
        draw.text((P+140, yc), condition, fill=T2, font=_f(19))
        draw.text((P+520, yc), f"→ {action}", fill=YELLOW, font=f22)
        yc += 30
    y += sh + GAP
    
    # ═══ 影响因素 ═══
    y, _ = _section(draw, y, "📊 关键影响因素")
    factors = data.get("factors", [])
    fh2 = len(factors) * 28 + 20
    _card(draw, y, fh2)
    yc = y + 12
    for factor, impact, detail in factors:
        iclr = RED if "利好" in impact else GREEN if "利空" in impact else YELLOW
        draw.text((P+18, yc), f"• {factor}", fill=TEXT, font=f22)
        draw.text((P+300, yc), f"[{impact}]", fill=iclr, font=f22)
        draw.text((P+420, yc), detail, fill=T2, font=f16)
        yc += 28
    y += fh2 + GAP
    
    # ═══ 主力行为分析 ═══
    y, _ = _section(draw, y, "🔬 主力行为分析")
    behav = data.get("behavior", {})
    bh = 0
    
    # 散户 vs 主力对比
    retail = behav.get("retail", {})
    if retail:
        bh += 100
        _card(draw, y, bh)
        yc = y + 12
        draw.text((P+18, yc), "主力 vs 散户 资金流向对比", fill=TEXT, font=f22)
        yc += 28
        for label, val, clr in retail:
            draw.text((P+18, yc), f"• {label}", fill=T2, font=f16)
            draw.text((P+220, yc), val, fill=clr, font=f22)
            yc += 26
        y += bh + GAP
    
    # 建仓/洗盘/试盘/震仓 四维分析
    signals = behav.get("signals", [])
    if signals:
        sh2 = len(signals) * 28 + 20
        _card(draw, y, sh2)
        yc = y + 12
        draw.text((P+18, yc), "建仓·洗盘·试盘·震仓 四维信号", fill=TEXT, font=f22)
        yc += 30
        for phase, signal, detail in signals:
            clrs = {"建仓":GREEN,"洗盘":RED,"试盘":YELLOW,"震仓":RED}
            cls = clrs.get(phase, BLUE)
            draw.text((P+18, yc), f"• [{phase}]", fill=cls, font=f22)
            draw.text((P+140, yc), signal, fill=TEXT, font=_f(20))
            draw.text((P+380, yc), detail, fill=T2, font=f16)
            yc += 28
        y += sh2 + GAP
    
    # ═══ 综合研判 ═══
    conclusion = data.get("conclusion", "")
    if conclusion:
        y += 4
        # 自动换行
        f_cl = _f(18)
        max_w = W - P*2 - 30
        # 简单按宽度拆行
        words = conclusion
        lines = []
        while words:
            # 二分找合适的截断点
            lo, hi = 1, len(words)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                w = f_cl.getbbox(words[:mid])[2]
                if w <= max_w: lo = mid
                else: hi = mid - 1
            lines.append(words[:lo])
            words = words[lo:]
        
        ch2 = len(lines) * 26 + 20
        _card(draw, y, ch2)
        draw.rectangle([P+2, y, P+8, y+ch2], fill=BLUE)
        for i, line in enumerate(lines):
            draw.text((P+20, y+10 + i*26), line, fill=BLUE, font=f_cl)
        y += ch2 + GAP
    
    # 底部
    y += 12
    draw.line([P, y, W-P, y], fill=BORDER, width=1)
    y += 14
    footer = "DAO量化助手  |  纯Python渲染  |  数据:东方财富妙想  |  ⚠️不构成投资建议"
    ftw = _f(14).getbbox(footer)[2]
    draw.text((W//2 - ftw//2, y), footer, fill=T2, font=_f(20))
    
    # 精确裁剪（加安全边际）
    # 精确裁剪：从底部向上找最后内容
    pixels = img.load()
    last = 0
    for yy in range(img.height - 1, 0, -1):
        for xx in range(0, img.width, 5):
            if pixels[xx, yy][3] > 0:
                last = yy
                break
        if last > 0:
            break
    img = img.crop((0, 0, W, last + 0))
    return img

# ═══ 测试 ═══
if __name__ == "__main__":
    data = {
        "price": 23.38, "change": 1.65, "opr": 23.09, "high": 23.86, "low": 22.40,
        "volume": 1924701, "amount": 44.7e8, "turnover": 11.86,
        "funds": [
            ("05-29", 23.38, -0.12, "涨1.7% 主力微出"),
            ("05-28", 23.00, +1.54, "涨6.0% 主力大买 🔥"),
            ("05-27", 21.70, +0.14, "涨0.8% 温和流入"),
            ("05-26", 21.53, -1.11, "跌3.8% 主力砸盘"),
            ("05-25", 22.39, -0.75, "涨3.9% 借涨出货 ⚠️"),
        ],
        "dark_pool": {"financing": "11.93亿(净买7,438万)", "short": "907万(39.4万股)",
                       "pledge": "50.52%(4,200万股)", "big_trade": "机构卖467.6万"},
        "finance": {"q1_rev": "23.06", "q1_net": "2.88", "q1_gm": "30.6",
                    "fy_rev": "103.3", "fy_net": "4.04", "fy_roe": "3.4",
                    "good": "✅ 扣非+31%  毛利率连升(27.7→30.6%)  虚拟电厂江苏33%  5机构买入评级",
                    "risk": "⚠️ Q1营收-21%  负债64.2%  控股股东质押过半  算力收入占比极低"},
        "news": [
            ("05-29", "融资净买入7,438万；机构大宗卖出467.6万"),
            ("05-27", "\"电力+算力\"协同：为中国电信提供算力租赁"),
            ("05-26", "控股股东质押4,200万股，累计质押50.52%"),
            ("05-15", "发布鑫零碳生态方案+能碳管理平台"),
        ],
        "targets": [
            ("强阻力", "26.0", "前期密集成交区上沿，放量突破确认"),
            ("第一阻力", "24.0", "整数关口+近期高点，短线压力位"),
            ("多空中枢", "22.5", "近5日均价，方向分水岭"),
            ("第一支撑", "21.5", "5/26-27双底，短线强支撑"),
            ("强支撑", "20.4", "5/8业绩会价位，中线价值区"),
        ],
        "strategy": [
            ("弱势", "跌破21.5且量>3亿", "止损观望，等20.4以下再考虑"),
            ("震荡", "21.5~24.0区间", "不操作，等待方向确认"),
            ("反弹", "放量突破24.0", "轻仓跟进，目标26.0"),
            ("转强", "放量突破26.0站稳", "中线看多，空间看30+"),
        ],
        "factors": [
            ("电力+算力战略", "利好", "绿电直供+虚拟电厂，中长期看点"),
            ("毛利率连升", "利好", "27.7→28.4→30.6%，盈利结构优化"),
            ("营收下滑21%", "利空", "转型阵痛，传统能源业务收缩"),
            ("负债64%+质押过半", "利空", "财务杠杆偏高，流动性风险"),
            ("放量双连阳", "利好", "近2日换手11%+，短线活跃"),
            ("电力板块偏强", "利好", "今日板块整体上涨，有板块效应"),
        ],
        "conclusion": "📌 放量双连阳+主力大买→短线偏强。转型期盈利结构改善，但负债+质押压制中期空间。关键看22.5中枢争夺，跌破21.5止损，突破24.0加仓。",
    }
    
    img = make_report("协鑫能科", "002015", data)
    out = Path.home() / ".openclaw-autoclaw/workspace/reports/xnk_v5.png"
    img.save(str(out))
    print(f"✅ {out} ({img.width}x{img.height})")
