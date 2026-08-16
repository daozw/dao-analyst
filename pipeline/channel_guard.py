#!/usr/bin/env python3
"""
手机通道守护 v3 — 微信+飞书通道健康检测 + 自动修复
检测网关进程 → 检查通道日志 → 发现断联自动重启
微信: 断联可重启网关修复 | 飞书: UAT失效需人工授权(仅告警)
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
FEISHU_REALERT_HOURS = 6   # 飞书UAT告警去重: 6小时内不重复告警
NO_LOG_ACTIVITY_MIN = 10   # 10分钟网关日志无任何新内容 → 可能挂了
MAX_RESTARTS_PER_HOUR = 2  # 1小时内最多重启2次
GATEWAY_START_WAIT = 15    # 重启后等15秒检查
GATEWAY_MIN_AGE_MIN = 15   # 网关进程最低年龄(分钟): 排除崩溃循环/瞬时exec进程的PID误报

def ts():
    return datetime.now(TZ).isoformat(timespec="seconds")

def log(msg):
    print(f"[{ts()}] {msg}")

def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:

            pass  # skip non-ISO lines
            pass
    return {"restarts": [], "last_ok": None, "consecutive_failures": 0}

def save_state(s):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, indent=2, ensure_ascii=False))

def pid_age_minutes(pid):
    """\u8fdb\u7a0b\u5b58\u6d3b\u5206\u949f\u6570; \u8fdb\u7a0b\u4e0d\u5b58\u5728\u6216\u89e3\u6790\u5931\u8d25\u8fd4\u56deNone"""
    try:
        r = subprocess.run(
            ["sh", "-c", f"ps -o etime= -p {int(pid)} | tr -d ' '"],
            capture_output=True, text=True, timeout=5
        )
        e = r.stdout.strip()
        if not e:
            return None
        days, rest = (e.split('-', 1) + [None])[:2] if '-' in e else (0, e)
        if rest is None:
            return None
        days = int(days) if str(days).isdigit() else 0
        parts = rest.split(':')
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            h, m, s = 0, int(parts[0]), int(parts[1])
        else:
            return None
        return days * 1440 + h * 60 + m
    except Exception:
        return None

def gateway_pid():
    """Detect gateway via ps - args-only match avoids false matches on our own detection commands"""
    try:
        r = subprocess.run(
            ["pgrep", "-f", "embedded-gateway-runtime.*dist/index.js gateway"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0 and r.stdout.strip():
            # 2026-08-16: embedded运行时(0aa756dc)自08-11起崩溃循环, 瞬时进程周期性命中此模式,
            # 导致每轮PID漂移(误报先例: 15705/3437/74877/84734/94337)。加年龄门槛:
            # <15min视为瞬时进程不采信, 回退最长存活检测。
            for cand in r.stdout.strip().split("\n"):
                age = pid_age_minutes(cand)
                if age is not None and age >= GATEWAY_MIN_AGE_MIN:
                    return cand
            # 全部候选过年轻(崩溃循环/瞬时exec) → 继续下一fallback
    except Exception:
        pass
    # Fallback: ps + precise grep
    try:
        r = subprocess.run(
            ["sh", "-c", "ps -eo pid,args | grep -v grep | grep 'embedded-gateway-runtime.*index.js gateway' | awk '{print $1}' | head -1"],
            capture_output=True, text=True, timeout=5
        )
        if r.stdout.strip().isdigit():
            cand = r.stdout.strip()
            if (pid_age_minutes(cand) or 0) >= GATEWAY_MIN_AGE_MIN:
                return cand
            # 过年轻 → 崩溃循环/瞬时进程, 继续下一fallback
    except Exception:
        pass
    # Fallback 2: native openclaw gateway = the LONGEST-LIVED openclaw process.
    # Transient openclaw CLI processes spawned by cron sessions live only minutes and
    # would otherwise mask a dead gateway and suppress auto-restart; the real gateway
    # is the supervisor-spawned persistent process (hours/days uptime)
    try:
        r = subprocess.run(
            ["sh", "-c",
             "ps -eo pid,etime,comm | awk '$3==\"openclaw\" {"
             "e=$2; n=split(e,a,\"-\"); if(n==2){d=a[1]; t=a[2]} else {d=0; t=e}"
             "m=split(t,c,\":\"); if(m==3) s=c[1]*3600+c[2]*60+c[3]; else if(m==2) s=c[1]*60+c[2]; else s=c[1]"
             "s+=d*86400; if(s>mx){mx=s; best=$1}} END {print best}'"],
            capture_output=True, text=True, timeout=5
        )
        if r.stdout.strip().isdigit():
            return r.stdout.strip()
    except Exception:
        pass
    # Fallback 3: detect via 'openclaw' binary (native package / PATH)
    try:
        r = subprocess.run(
            ["pgrep", "-x", "openclaw"],
            capture_output=True, text=True, timeout=5
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split("\n")[0]
    except Exception:
        pass
    # Fallback 4: detect via ps comm=openclaw (catches native openclaw process)
    try:
        r = subprocess.run(
            ["sh", "-c", "ps -eo pid,comm | grep -v grep | grep 'openclaw' | awk '{print $1}' | head -1"],
            capture_output=True, text=True, timeout=5
        )
        if r.stdout.strip().isdigit():
            return r.stdout.strip()
    except Exception:
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
                except Exception as e:

                    pass  # skip non-ISO lines
                    pass
        return age_s, recent_lines
    except Exception as e:

        pass  # skip non-ISO lines
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
                except Exception as e:

                    pass  # skip non-ISO lines
                    continue
                if "openclaw-weixin" not in line:
                    continue
                # errcode -14 会话过期/暂停bot: 不是活跃, 是故障
                if "session expired" in line or "pausing bot" in line or "errcode -14" in line:
                    errors += 1
                    continue
                activity += 1
                if "error" in line.lower() or "fail" in line.lower():
                    errors += 1
                if "delivery-recovery" in line and "Retry failed" in line:
                    delivery_fails += 1
    except Exception as e:

        pass  # skip non-ISO lines
        pass
    return {"active": activity > 0, "errors": errors, "activity": activity, "delivery_fails": delivery_fails}

def feishu_status(minutes=60):
    """Check feishu connector health: user-token errors in gateway log"""
    if not GATEWAY_LOG.exists():
        return {"token_error": False, "count": 0, "last": None}
    cutoff = datetime.now(TZ) - timedelta(minutes=minutes)
    count = 0
    last = None
    try:
        with open(GATEWAY_LOG) as f:
            for line in f:
                try:
                    line_ts = datetime.fromisoformat(line[:19]).replace(tzinfo=TZ)
                    if line_ts < cutoff:
                        continue
                except Exception as e:
                    continue
                if "feishu_token_unavailable" in line:
                    count += 1
                    last = line_ts
    except Exception as e:
        pass
    return {"token_error": count > 0, "count": count, "last": last}

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
    except Exception as e:

        pass  # skip non-ISO lines
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

    # 3.5 飞书通道检测 (UAT失效无法自动修复 → 告警提示)
    fs = feishu_status(minutes=60)
    if fs["token_error"]:
        last_alert = state.get("feishu_last_alert")
        recently = False
        if last_alert:
            try:
                t = datetime.fromisoformat(last_alert).replace(tzinfo=TZ)
                recently = (datetime.now(TZ) - t) < timedelta(hours=FEISHU_REALERT_HOURS)
            except Exception as e:
                pass
        if recently:
            warnings.append(f"⚠️ 飞书UAT失效持续中(6h内已告警 x{fs['count']}/60min)")
        else:
            issues.append(f"❌ 飞书UAT失效(feishu_token_unavailable x{fs['count']}/60min)，需人工重新授权")
            state["feishu_last_alert"] = ts()
    else:
        state["feishu_last_alert"] = None

    # 4. 决策: 是否需要修复 (仅网关挂掉才自动重启)
    need_repair = (not gw_ok) or (log_age is not None and log_age > NO_LOG_ACTIVITY_MIN * 60)
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
