#!/usr/bin/env python3
"""智能模型路由 V2 — 基于实测基准"""

MODELS = {
    "qwen3": {
        "name": "qwen3:14b",
        "speed": "快(5-10s)",
        "quality": "中",
        "best_for": "日常报告/数据汇总/快速问答",
        "use_in": ["stock_report", "news_summary", "batch_check", "code_assist"]
    },
    "deepseek": {
        "name": "deepseek-r1:14b",
        "speed": "慢(60-120s)",
        "quality": "高",
        "best_for": "深度分析/估值建模/策略研判",
        "use_in": ["deep_analysis", "valuation", "risk_assessment", "behavior_analysis"]
    }
}

TASK_MAP = {
    "stock_report": "qwen3",
    "deep_analysis": "deepseek",
    "valuation": "deepseek",
    "behavior_analysis": "deepseek",
    "risk_assessment": "deepseek",
    "news_summary": "qwen3",
    "batch_check": "qwen3",
    "code_assist": "qwen3",
    "default": "qwen3"
}

def route(task: str = "default") -> dict:
    model_key = TASK_MAP.get(task, "qwen3")
    return MODELS[model_key]

def env_for(task: str = "default") -> dict:
    cfg = route(task)
    return {
        "TRADINGAGENTS_LLM_PROVIDER": "ollama",
        "TRADINGAGENTS_DEEP_THINK_LLM": MODELS["deepseek"]["name"],
        "TRADINGAGENTS_QUICK_THINK_LLM": cfg["name"],
        "TRADINGAGENTS_BACKEND_URL": "http://localhost:11434/v1",
        "TRADINGAGENTS_OUTPUT_LANGUAGE": "Chinese"
    }

if __name__ == "__main__":
    import sys
    task = sys.argv[1] if len(sys.argv) > 1 else "default"
    cfg = route(task)
    print(f"任务: {task} → {cfg['name']} ({cfg['speed']}, {cfg['quality']}质量)")
