#!/bin/bash
# Kronos-mini 一键部署
set -e
VENV=/Users/sound/dao-analyst/.venv/bin/python3
echo "1/3 安装依赖..."
$VENV -m pip install torch huggingface_hub safetensors numpy pandas --quiet
echo "2/3 下载模型..."
$VENV -c "
from huggingface_hub import snapshot_download
snapshot_download('NeoQuasar/Kronos-mini', local_dir='/Users/sound/dao-analyst/models/kronos-mini')
print('Kronos-mini 模型下载完成')
"
echo "3/3 验证..."
$VENV -c "import torch; print(f'PyTorch {torch.__version__} ✅')"
$VENV -c "import os; files=os.listdir('/Users/sound/dao-analyst/models/kronos-mini'); print(f'模型文件: {len(files)}个')"
echo "✅ Kronos部署完成"
