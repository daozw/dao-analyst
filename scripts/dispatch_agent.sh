#!/bin/bash
# 分身调度: crontab写任务 → agent执行
AGENT="$1"
TASK="$2"
FILE="/tmp/dao_dispatch/${AGENT}_$(date +%H%M%S).json"

python3 -c "
import json
json.dump({'agent':'$AGENT','task':'$TASK','time':__import__('datetime').datetime.now().isoformat()},open('$FILE','w'))
" 2>/dev/null
echo "[$(date '+%H:%M:%S')] $AGENT ← $TASK" >> /tmp/dao_dispatch/dispatch.log
