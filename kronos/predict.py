#!/usr/bin/env python3
"""Kronos-mini K线预测 — DAO专用 | ~8M参数 | M4 MPS"""
import os, sys, json
import numpy as np
import pandas as pd
import torch
from safetensors.torch import load_file

sys.path.insert(0, os.path.dirname(__file__))
from kronos_orig import KronosTokenizer, Kronos, KronosPredictor

DIR = os.path.join(os.path.dirname(__file__), '..', 'models', 'kronos-mini')

class KronosEngine:
    def __init__(self, device=None):
        self.device = device or ('mps' if torch.backends.mps.is_available() else 'cpu')
        
        tok_cfg = json.load(open(f'{DIR}/tokenizer_config.json'))
        self.tokenizer = KronosTokenizer(**tok_cfg)
        self.tokenizer.load_state_dict(load_file(f'{DIR}/tokenizer_model.safetensors'), strict=False)
        
        mdl_cfg = json.load(open(f'{DIR}/config.json'))
        self.model = Kronos(**mdl_cfg)
        self.model.load_state_dict(load_file(f'{DIR}/model.safetensors'), strict=False)
        
        self.predictor = KronosPredictor(model=self.model, tokenizer=self.tokenizer, device=self.device)
        t = sum(p.numel() for p in self.tokenizer.parameters())
        m = sum(p.numel() for p in self.model.parameters())
        print(f'Kronos-mini: {t+m:,} params on {self.device}')
    
    def predict(self, ohlcv_data, steps=5):
        """
        ohlcv_data: np.array (seq_len, 5) [open,high,low,close,volume]
        returns: DataFrame with OHLC predictions
        """
        df = pd.DataFrame(ohlcv_data, columns=['open','high','low','close','volume'])
        df['amount'] = df['volume'] * df['close']
        
        xt = pd.DatetimeIndex(pd.date_range(end='2026-01-01', periods=len(df), freq='D'))
        yt = pd.DatetimeIndex(pd.date_range(start='2026-01-02', periods=steps, freq='D'))
        
        result = self.predictor.predict(df, xt, yt, pred_len=steps, T=1.0, verbose=False)
        return result

if __name__ == '__main__':
    engine = KronosEngine()
    fake = np.cumsum(np.random.randn(500, 5) * 0.01, axis=0) + 100
    fake[:, 0] = np.abs(fake[:, 0])
    result = engine.predict(fake, 5)
    print(f'预测完成: {result.shape}')
    print(result.tail())
