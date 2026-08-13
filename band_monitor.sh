#!/bin/bash
cd /Users/sound/dao-analyst

HOUR=$(date +%H)
MIN=$(date +%M)

# 市场温度（获取失败→不阻止交易,只打日志）
TEMP=$(.venv/bin/python3 -c "
from market_thermometer_v2 import get_thermometer
t=get_thermometer()
print(t.get('level',''))
" 2>/dev/null)

if [ -z "$TEMP" ]; then
    echo "[$HOUR:$MIN] ⚠️ 温度获取失败→默认执行autotrade"
elif echo "$TEMP" | grep -q "防御主导"; then
    echo "[$HOUR:$MIN] 🔴 防御主导→跳过autotrade"
    exit 0
elif echo "$TEMP" | grep -q "防御抬头"; then
    echo "[$HOUR:$MIN] 🟠 防御抬头→半仓模式"
fi

# 正常交易(180秒超时保护, 防止行情接口挂起)
.venv/bin/python3 -c "
import subprocess, sys
try:
    r = subprocess.run([sys.executable, 'pipeline/autotrade.py', '--plan', '--real'], capture_output=True, text=True, timeout=180)
    print(r.stdout[-2500:])
    if r.returncode != 0:
        print(r.stderr[-500:])
except subprocess.TimeoutExpired:
    print('⏰ autotrade --plan 超时(180s), 跳过本轮')
except Exception as e:
    print(f'⚠️ autotrade 异常: {e}')
"
echo "[$HOUR:$MIN] ⏳ 等待60秒通知窗口..."
sleep 60
.venv/bin/python3 pipeline/autotrade.py --execute 2>&1
