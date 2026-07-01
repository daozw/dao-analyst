#!/usr/bin/env python3
"""DAO 每日巡检 V1.0 — 通用巡检（磁盘/进化/通道/网关）"""
import subprocess, sys, os, json, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
HOME = Path.home()
WORKSPACE = HOME / ".openclaw-autoclaw" / "agents" / "dao" / "workspace"
EVOLUTION = WORKSPACE / "EVOLUTION.md"
PATROL_LOG = HOME / "dao-analyst" / "logs" / "patrol_log.json"
CHANNEL_GUARD = HOME / "dao-analyst" / "pipeline" / "channel_guard.py"
VENV_PYTHON = HOME / "dao-analyst" / ".venv" / "bin" / "python3"

def ts():
    return datetime.now(TZ).isoformat(timespec="seconds")

def log_entry(results):
    entry = {"time": ts(), "type": "通用巡检", "results": results}
    PATROL_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        if PATROL_LOG.exists():
            with open(PATROL_LOG) as f:
                existing = json.load(f)
        else:
            existing = []
        if isinstance(existing, dict):
            existing = [existing]
        existing.append(entry)
        existing = existing[-50:]
        with open(PATROL_LOG, "w") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[{ts()}] ❌ 写入patrol_log失败: {e}")

def check_disk():
    try:
        usage = shutil.disk_usage(str(HOME))
        pct = usage.used / usage.total * 100
        gb_free = usage.free / (1024**3)
        if pct > 90:
            return ("❌", f"磁盘使用{pct:.0f}%, 仅{gb_free:.0f}Gi可用", True)
        elif pct > 80:
            return ("⚠️", f"磁盘使用{pct:.0f}%, {gb_free:.0f}Gi可用", False)
        else:
            return ("✅", f"磁盘使用{pct:.0f}%, {gb_free:.0f}Gi可用", False)
    except Exception as e:
        return ("❌", f"磁盘检查失败: {e}", True)

def check_evolution():
    if not EVOLUTION.exists():
        return ("❌", "EVOLUTION.md不存在", True)
    mtime = datetime.fromtimestamp(EVOLUTION.stat().st_mtime, tz=TZ)
    days = (datetime.now(TZ) - mtime).days
    if days > 7:
        return ("⚠️", f"EVOLUTION.md {days}天未更新", True)
    else:
        return ("✅", f"EVOLUTION.md {days}天前更新", False)

def check_channel():
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), str(CHANNEL_GUARD)],
            capture_output=True, text=True, timeout=30,
            cwd=str(HOME / "dao-analyst")
        )
        out = result.stdout.strip()
        if "通道正常" in out:
            return ("✅", "微信通道正常", False)
        elif "✅" in out:
            last_line = out.split("\n")[-1] if out else ""
            return ("✅", last_line[:100], False)
        else:
            return ("⚠️", out[:200] or result.stderr.strip()[:200], True)
    except subprocess.TimeoutExpired:
        return ("❌", "channel_guard超时", True)
    except Exception as e:
        return ("❌", f"channel_guard异常: {e}", True)


def check_log_rotation():
    """Check and rotate oversized log files"""
    max_size = 1 * 1024 * 1024  # 1MB
    rotated = []
    for log_name in ['notify_relay.log', 'relay_cron.log']:
        log_path = HOME / 'dao-analyst' / 'logs' / log_name
        if log_path.exists() and log_path.stat().st_size > max_size:
            bak = log_path.with_suffix('.log.old')
            log_path.rename(bak)
            log_path.write_text(f'# Log rotated at {ts()}' + chr(10))
            rotated.append(log_name)
    if rotated:
        return ("⚠️", f"日志轮转: {', '.join(rotated)}", False)
    else:
        return ("✅", "日志大小正常", False)

def check_gateway():
    try:
        # macOS pgrep 15char limit, use ps like channel_guard does
        result = subprocess.run(
            ["ps", "-eo", "pid,comm"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if "openclaw-gateway" in line:
                pid = line.strip().split()[0]
                return ("✅", f"网关运行中 PID={pid}", False)
        return ("❌", "网关进程未找到", True)
    except Exception as e:
        return ("❌", f"网关检查失败: {e}", True)

def run():
    print(f"[{ts()}] 🔍 DAO每日巡检开始")

    results = {}
    alerts = []

    status, detail, alert = check_gateway()
    results["网关"] = {"status": status, "detail": detail}
    if alert: alerts.append(f"网关: {detail}")

    status, detail, alert = check_disk()
    results["磁盘"] = {"status": status, "detail": detail}
    if alert: alerts.append(f"磁盘: {detail}")

    status, detail, alert = check_evolution()
    results["EVOLUTION"] = {"status": status, "detail": detail}
    if alert: alerts.append(f"EVOLUTION: {detail}")

    status, detail, alert = check_channel()
    results["微信通道"] = {"status": status, "detail": detail}
    if alert: alerts.append(f"微信: {detail}")

    status, detail, alert = check_log_rotation()
    results["日志轮转"] = {"status": status, "detail": detail}
    if alert: alerts.append(f"日志: {detail}")

    log_entry(results)

    all_ok = all(v["status"] == "✅" for v in results.values())
    if all_ok:
        print(f"[{ts()}] ✅ 巡检完成: 全部正常")
    else:
        print(f"[{ts()}] ⚠️ 巡检完成: {len(alerts)}项异常")
        for a in alerts:
            print(f"  - {a}")

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(run())
