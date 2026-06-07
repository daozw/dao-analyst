#!/bin/bash
# DAO V3.3 系统状态面板
cd /Users/sound/dao-analyst

echo "🦅 DAO V3.3 | $(date '+%Y-%m-%d %H:%M')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Gateway
GW=$(ps aux | grep -c '[o]penclaw-gateway')
echo "Gateway: $([ $GW -gt 0 ] && echo '✅' || echo '❌')"

# APIs
.venv/bin/python3 -c "
import urllib.request,ssl,json
ssl._create_default_https_context=ssl._create_unverified_context
for n,u,h in [('腾讯','https://qt.gtimg.cn/q=sh600900',{}),('MX','https://mkapi2.dfcfs.com/finskillshub/api/claw/mockTrading/positions',{'apikey':'mkt_ih0rB17IBWiKJxSEe4qe1YPfwtueGmlhASMF38NMRI8','Content-Type':'application/json'})]:
    try:
        d=json.dumps({}).encode() if 'mkapi' in u else None
        m='POST' if 'mkapi' in u else 'GET'
        urllib.request.urlopen(urllib.request.Request(u,data=d,headers=h,method=m),timeout=5)
        print(f'{n}: ✅')
    except: print(f'{n}: ❌')
" 2>/dev/null

# Cron
CRON=$(crontab -l 2>/dev/null | grep -vc '^#')
echo "Cron: ${CRON:-0}条"

# MX
.venv/bin/python3 -c "
from pipeline.autotrade import get_mx_positions
pos,tv,tp=get_mx_positions()
print(f'MX: {len(pos)}只 ¥{tv:,.0f} 盈亏¥{tp:+,.0f}')
" 2>/dev/null

# Disk
DISK=$(df -h / | tail -1 | awk '{print $4}')
echo "磁盘: $DISK"

# Git
cd /Users/sound/dao-analyst && echo "Git: $(git log --oneline -1 2>/dev/null | cut -c1-7)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
