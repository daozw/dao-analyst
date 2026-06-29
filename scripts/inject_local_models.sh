#!/bin/bash
# Gateway重启后自动注入Ollama本地模型配置
# 在crontab中加入: @reboot 或 openclaw启动后触发

RUNTIME="/Users/sound/.openclaw-autoclaw/openclaw.runtime.json"
PYTHON="/Users/sound/dao-analyst/.venv/bin/python3"

$PYTHON -c "
import json
cfg=json.load(open('$RUNTIME'))
# Add ollama if missing
if 'ollama' not in cfg['models']['providers']:
    cfg['models']['providers']['ollama']={
        'baseUrl':'http://127.0.0.1:11434/v1','apiKey':'ollama',
        'api':'openai-completions',
        'models':[
            {'id':'deepseek-r1:8b','name':'DeepSeek-R1-8B','contextWindow':131072,'maxTokens':32768,'input':['text']},
            {'id':'qwen3.6:27b','name':'Qwen3.6-27B','contextWindow':131072,'maxTokens':32768,'input':['text']}
        ]
    }
# Set local models + fallback
cfg['agents']['defaults']['model']={'primary':'ollama/deepseek-r1:8b','fallbacks':['zai/zai_auto']}
for a in cfg['agents']['list']:
    if a['id']=='dao': a['model']={'primary':'ollama/qwen3.6:27b','fallbacks':['zai/zai_auto']}
    elif a['id'] in ['dp','main']: a['model']={'primary':'ollama/deepseek-r1:8b','fallbacks':['zai/zai_auto']}
json.dump(cfg,open('$RUNTIME','w'),indent=2,ensure_ascii=False)
print('✅ local models injected')
"
