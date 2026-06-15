#!/usr/bin/env python3
"""
HMM体制检测接口 — 集成到 autotrade.py
用法:
  from hmm_regime import get_hmm_regime
  result = get_hmm_regime()
  # result = {'regime': 'CHOP', 'label': '震荡市', 'P_bull': 0.0, 'P_bear': 0.33, 'P_chop': 0.67}
"""
import os, pickle, sys
import numpy as np
import pandas as pd

MODEL_PATH = os.path.expanduser('~/dao-analyst/models/hmm_regime_model.pkl')

def load_model():
    """加载HMM模型"""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"HMM模型未找到: {MODEL_PATH}，请先运行训练脚本")
    with open(MODEL_PATH, 'rb') as f:
        return pickle.load(f)

def get_features_today(context_days=30):
    """获取最新特征值（含上下文窗口，用于HMM序列预测）"""
    import akshare as ak
    try:
        df = ak.stock_zh_index_daily(symbol='sh000001')
        df['date'] = pd.to_datetime(df['date'])
        df = df.tail(context_days + 60).copy()  # 足够计算滚动指标
        
        df['ret'] = df['close'].pct_change() * 100
        df['amplitude'] = (df['high'] - df['low']) / df['close'].shift(1) * 100
        df['vol_change'] = df['volume'].pct_change() * 100
        df['mom5'] = df['close'].pct_change(5) * 100
        df['mom20'] = df['close'].pct_change(20) * 100
        df['vol20'] = df['ret'].rolling(20).std()
        
        df = df.dropna()
        if len(df) < context_days:
            return None
        
        # 返回最近context_days的完整序列
        features_cols = ['ret', 'amplitude', 'vol_change', 'mom5', 'mom20', 'vol20']
        return df[features_cols].values[-context_days:]
    except Exception as e:
        print(f"[HMM] 特征获取失败: {e}")
        return None

def get_hmm_regime():
    """
    获取当前市场体制 (替代get_market_regime)
    Returns:
        dict with: regime (BULL/CHOP/BEAR), P_bull, P_bear, P_chop, label, style
    """
    try:
        model_data = load_model()
        model = model_data['model']
        regime_map = model_data['regime_map']
        
        X = get_features_today(context_days=30)
        if X is None:
            return {'regime': 'CHOP', 'label': '震荡市(默认)', 'P_bull': 0.25, 'P_bear': 0.25, 'P_chop': 0.50,
                    'style': '均衡', 'prefer': [], 'avoid': [], 'source': 'HMM_fallback'}
        
        # 预测状态概率 (使用完整序列, 取最后一天的后验)
        posteriors = model.predict_proba(X)[-1]
        
        # 聚合到三大类
        p_bull = p_bear = p_chop = 0.0
        for state, regime in regime_map.items():
            st = str(regime)
            if 'BULL' in st.upper() and 'BEAR' not in st.upper():
                p_bull += posteriors[state]
            elif 'BEAR' in st.upper() and 'BULL' not in st.upper():
                p_bear += posteriors[state]
            else:
                p_chop += posteriors[state]
        
        # 判定体制
        if p_bull > 0.45:
            regime = 'BULL'
            label = '🟢进攻市'
            style = '成长+周期'
            prefer = ['电子','制造','新能源','科技','信息']
            avoid = ['银行','公用','防御']
        elif p_bear > 0.45:
            regime = 'BEAR'
            label = '🔴防御市'
            style = '纯防御'
            prefer = ['银行','高股息','公用','电力']
            avoid = ['电子','科技','制造','新能源','高PE']
        else:
            regime = 'CHOP'
            label = '🟡震荡市'
            style = '均衡'
            prefer = []
            avoid = []
        
        return {
            'regime': regime,
            'label': label,
            'style': style,
            'prefer': prefer,
            'avoid': avoid,
            'P_bull': round(float(p_bull), 4),
            'P_bear': round(float(p_bear), 4),
            'P_chop': round(float(p_chop), 4),
            'source': 'HMM_v1',
        }
    except Exception as e:
        print(f"[HMM] 体制检测异常: {e}")
        return {'regime': 'CHOP', 'label': '震荡市(异常)', 'P_bull': 0.25, 'P_bear': 0.25, 'P_chop': 0.50,
                'style': '均衡', 'prefer': [], 'avoid': [], 'source': 'HMM_error'}


def get_regime_weight():
    """
    获取动态仓位权重 (更细粒度)
    基于连续概率而非硬阈值
    """
    r = get_hmm_regime()
    p_bull, p_bear, p_chop = r['P_bull'], r['P_bear'], r['P_chop']
    
    # 期望收益率估计 (牛+0.3%/日, 熊-0.5%/日, 震荡+0.05%/日)
    expected_ret = p_bull * 0.3 + p_chop * 0.05 + p_bear * (-0.5)
    
    # 仓位权重: 基于期望收益 + 风险调整
    if expected_ret > 0.15:
        weight = 1.0
    elif expected_ret > 0.05:
        weight = 0.75
    elif expected_ret > -0.05:
        weight = 0.50
    elif expected_ret > -0.15:
        weight = 0.25
    else:
        weight = 0.0
    
    return {'weight': weight, 'expected_ret': round(expected_ret, 4), **r}


if __name__ == '__main__':
    result = get_hmm_regime()
    print(f"体制: {result['regime']} {result['label']}")
    print(f"概率: P(BULL)={result['P_bull']:.1%} P(BEAR)={result['P_bear']:.1%} P(CHOP)={result['P_chop']:.1%}")
    print(f"风格: {result['style']}")
    
    weight = get_regime_weight()
    print(f"\n动态仓位: {weight['weight']*100:.0f}% (期望日收益: {weight['expected_ret']:+.3f}%)")
