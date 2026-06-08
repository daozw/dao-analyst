#!/usr/bin/env python3
"""
手机通道守护 v2 — 微信通道健康检测 + 自动修复
检测网关进程 → 检查通道日志 → 发现断联自动重启
修复方式: 通过 pkill 杀网关进程让 AutoClaw 自动重启
"""

import subprocess, sys, json, os, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

TZ = timezone(timedelta(hours=8))
GATEWAY_LOG = Path.home() / ".openclaw-autoclaw" / "logs" / "gateway.log"
STATE_FILE = Path.home() / ".openclaw-autoclaw" / "logs" / "channel-guard-state.json"

# 阈值
NO_ACTIVITY_MIN = 15       # 15分钟无微信活动 → 可疑
NO_LOG_ACTIVITY_MIN = 10   # 10分钟网关日志无任何新内容 → 可能挂了
MAX_RESTARTS_PER_HOUR = 2  # 1小时内最多重启2次
GATEWAY_START_WAIT = 15    # 重启后等15秒检查

def ts():
    return datetime.now(TZ).isoformat(timespec="seconds")

def log(msg):
    print(f"[{ts()}] {msg}")

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {"restarts": [], "last_ok": None, "consecutive_failures": 0}

def save_state(s):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, indent=2, ensure_ascii=False))

def gateway_pid():
    """macOS pgrep has a 15-char limit; use ps instead"""
    try:
        r = subprocess.run(["ps", "-eo", "pid,comm"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if "openclaw-gateway" in line:
                parts = line.strip().split()
                if parts and parts[0].isdigit():
                    return parts[0]
    except:
        pass
    return None

def log_activity(minutes=15):
    """Check if the gateway log has been updated recently"""
    if not GATEWAY_LOG.exists():
        return None, 0
    try:
        mtime = GATEWAY_LOG.stat().st_mtime
        age_s = time.time() - mtime
        cutoff = datetime.now(TZ) - timedelta(minutes=minutes)
        recent_lines = 0
        with open(GATEWAY_LOG) as f:
            for line in f:
                try:
                    line_ts = datetime.fromisoformat(line[:19]).replace(tzinfo=TZ)
                    if line_ts >= cutoff:
                        recent_lines += 1
                except:
                    pass
        return age_s, recent_lines
    except:
        return None, 0

def weixin_status(minutes=15):
    """Check weixin-specific activity and errors"""
    if not GATEWAY_LOG.exists():
        return {"active": False, "errors": 0, "activity": 0}
    cutoff = datetime.now(TZ) - timedelta(minutes=minutes)
    activity = 0
    errors = 0
    delivery_fails = 0
    try:
        with open(GATEWAY_LOG) as f:
            for line in f:
                try:
                    line_ts = datetime.fromisoformat(line[:19]).replace(tzinfo=TZ)
                    if line_ts < cutoff:
                        continue
                except:
                    continue
                if "openclaw-weixin" not in line:
                    continue
                activity += 1
                if "error" in line.lower() or "fail" in line.lower():
                    errors += 1
                if "delivery-recovery" in line and "Retry failed" in line:
                    delivery_fails += 1
    except:
        pass
    return {"active": activity > 0, "errors": errors, "activity": activity, "delivery_fails": delivery_fails}

def check_weixin_config():
    """Check if weixin account config exists and looks valid"""
    config = Path.home() / ".openclaw-autoclaw" / "openclaw-weixin" / "accounts.json"
    if not config.exists():
        return False, "accounts.json 不存在"
    try:
        data = json.loads(config.read_text())
        if not isinstance(data, list) or len(data) == 0:
            return False, "accounts.json 为空"
        return True, f"{len(data)}个账号已配置"
    except:
        return False, "accounts.json 解析失败"

def restart_gateway():
    """重启网关: kill进程 → 等待AutoClaw自动拉起"""
    log("🔄 执行网关重启...")
    pid = gateway_pid()
    if not pid:
        log("⚠️ 网关未运行，尝试通过 killall 触发重启")
    pid = gateway_pid()
    try:
        # Kill gateway gracefully by PID
        if pid:
            subprocess.run(["kill", "-TERM", pid], timeout=10)
            time.sleep(3)
            # Force kill if still alive
            if gateway_pid():
                subprocess.run(["kill", "-KILL", pid], timeout=5)
                time.sleep(2)
        # Wait for AutoClaw to restart it
        log(f"等待 AutoClaw 自动拉起 (最多{GATEWAY_START_WAIT}s)...")
        for i in range(GATEWAY_START_WAIT):
            time.sleep(1)
            if gateway_pid():
                # Give it a moment to initialize
                time.sleep(3)
                log("✅ 网关已自动重启")
                return True
        log("❌ 网关未被自动拉起")
        return False
    except Exception as e:
        log(f"❌ 重启异常: {e}")
        return False

def main():
    state = load_state()
    issues = []
    warnings = []

    # 1. 网关进程检测
    pid = gateway_pid()
    gw_ok = pid is not None
    if not gw_ok:
        issues.append("❌ 网关进程不存在")
    else:
        log(f"✅ 网关运行中 PID={pid}")

    # 2. 日志活跃度检测
    log_age, log_lines = log_activity(minutes=NO_LOG_ACTIVITY_MIN)
    if log_age is not None:
        if log_age > NO_LOG_ACTIVITY_MIN * 60:
            issues.append(f"❌ 网关日志{log_age/60:.0f}分钟无更新(> {NO_LOG_ACTIVITY_MIN}min)")
        elif log_lines == 0:
            warnings.append(f"⚠️ 近{NO_LOG_ACTIVITY_MIN}分钟日志量为0")

    # 3. 微信通道检测
    wx = weixin_status(minutes=NO_ACTIVITY_MIN)
    sys_cfg_ok, sys_cfg_msg = check_weixin_config()

    if sys_cfg_ok:
        log(f"✅ 微信配置: {sys_cfg_msg}")
    else:
        issues.append(f"❌ 微信配置异常: {sys_cfg_msg}")

    if wx["active"]:
        log(f"✅ 微信通道活跃 (近{NO_ACTIVITY_MIN}min: {wx['activity']}条日志)")
    elif gw_ok:
        warnings.append(f"⚠️ 微信通道近{NO_ACTIVITY_MIN}分钟无活动")

    if wx["errors"] > 0:
        log(f"⚠️ 微信错误/失败 {wx['errors']}条 (含delivery-retry {wx['delivery_fails']}条)")

    # 4. 决策: 是否需要修复 (仅网关挂掉才自动重启)
    need_repair = not gw_ok
    repaired = False

    if need_repair:
        # Rate limit
        state["restarts"] = [
            t for t in state.get("restarts", [])
            if datetime.fromisoformat(t).replace(tzinfo=TZ) > datetime.now(TZ) - timedelta(hours=1)
        ]
        recent = len(state["restarts"])

        if recent < MAX_RESTARTS_PER_HOUR:
            log(f"🔧 检测到{len(issues)}个严重问题，触发修复 (1h内第{recent+1}次)")
            state["restarts"].append(datetime.now(TZ).isoformat())
            repaired = restart_gateway()
            if repaired:
                state["last_ok"] = ts()
                state["consecutive_failures"] = 0
            else:
                state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
        else:
            log(f"⛔ 1h内已重启{recent}次，跳过自动修复")
            warnings.append(f"⛔ 重启频率过高({recent}次/h)，需人工检查")
    else:
        state["last_ok"] = ts()
        state["consecutive_failures"] = 0

    save_state(state)

    # 输出摘要
    all_msgs = issues + warnings
    if repaired:
        all_msgs.append("🔧 已自动修复 (网关重启)")
    if not all_msgs:
        log("✅ 通道正常")

    for m in all_msgs:
        log(f"  {m}")

    status = "ok"
    if issues and not repaired:
        status = "degraded"
    elif repaired:
        status = "repaired"

    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "repaired": repaired,
        "time": ts(),
        "gateway_pid": pid,
        "weixin": wx,
    }

if __name__ == "__main__":
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    result = main()
    if verbose:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    sys.exit(0 if result["status"] in ("ok", "repaired") else 1)
