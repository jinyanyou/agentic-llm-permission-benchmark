#!/usr/bin/env bash
# bootstrap.sh — 콜드 스타트부터 실험 가능 상태까지 한 줄로.
#
# 사용: ./bootstrap.sh [--smoke]
#   --smoke   기본 환경 점검 후 1회 스모크 테스트까지 실행 (~2분)
#
# Idempotent: 이미 떠있는 컴포넌트는 건너뜀.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# GPU/SSH 접속 정보는 코드에 박지 않고 .env 에서 주입한다 (.env.example 참고).
[ -f "$ROOT/.env" ] && set -a && . "$ROOT/.env" && set +a
: "${GPU_HOST:?GPU_HOST 미설정 — .env 를 .env.example 기준으로 작성하세요}"
: "${GPU_USER:?GPU_USER 미설정}"
: "${GPU_PORT:?GPU_PORT 미설정}"
: "${GPU_PASS:?GPU_PASS 미설정}"
: "${OLLAMA_REMOTE_HOST:?OLLAMA_REMOTE_HOST 미설정 (예: GPU 노드명)}"
export GPU_HOST GPU_USER GPU_PORT GPU_PASS OLLAMA_REMOTE_HOST

log() { echo -e "\033[36m[bootstrap]\033[0m $*"; }
warn() { echo -e "\033[33m[bootstrap WARN]\033[0m $*"; }
err() { echo -e "\033[31m[bootstrap ERR]\033[0m $*" >&2; }

# 1. SSH tunnel (host 11434)
log "1/5  SSH tunnel"
if curl -s --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    log "     tunnel already up"
else
    if [ ! -x /tmp/knu_tunnel.exp ]; then
        warn "     /tmp/knu_tunnel.exp 없음 — 재생성"
        cat > /tmp/knu_tunnel.exp <<'EOF'
#!/usr/bin/expect -f
set timeout 30
log_user 1
spawn ssh -f -N -4 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -o TCPKeepAlive=yes -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new -L 127.0.0.1:11434:$env(OLLAMA_REMOTE_HOST):11434 -p $env(GPU_PORT) $env(GPU_USER)@$env(GPU_HOST)
expect {
    -re "(?i)password:" { send "$env(GPU_PASS)\r" }
    timeout { puts "\nTIMEOUT"; exit 2 }
}
expect eof
catch wait result
exit [lindex $result 3]
EOF
        chmod +x /tmp/knu_tunnel.exp
    fi
    /tmp/knu_tunnel.exp >/dev/null 2>&1 || true
    sleep 2
    if curl -s --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null; then
        log "     tunnel created"
    else
        err "     tunnel failed — KNU/ollama 직접 확인 필요"
        exit 1
    fi
fi

# 2. OrbStack
log "2/5  OrbStack"
if [ "$(orbctl status 2>&1 | head -1)" = "Running" ]; then
    log "     already running"
else
    orbctl start
    sleep 6
fi
export DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock

# 3. OpenShell gateway
log "3/5  OpenShell gateway 'nemoclaw'"
openshell gateway start --name nemoclaw 2>&1 | grep -E "running|started" || true
for i in 1 2 3 4 5; do
    if openshell status 2>&1 | grep -q "Connected"; then
        log "     gateway Connected"
        break
    fi
    sleep 3
done

# 4. Sandbox forwarder
log "4/5  Sandbox forwarder (localhost:11434 → host)"
FWD_RUNNING=$(openshell sandbox exec -n samdtg --no-tty -- pgrep -c -f ollama_forwarder 2>&1 | tail -1 | tr -dc '0-9')
if [ "${FWD_RUNNING:-0}" -gt 0 ]; then
    log "     forwarder already running"
else
    # Ensure script exists in sandbox
    if ! openshell sandbox exec -n samdtg --no-tty -- test -f /sandbox/ollama_forwarder.js 2>/dev/null; then
        FWD_SRC="$SCRIPT_DIR/ollama_forwarder.js"
        if [ -f "$FWD_SRC" ]; then
            log "     uploading forwarder script from $FWD_SRC"
            cat "$FWD_SRC" | openshell sandbox exec -n samdtg --no-tty -- bash -c 'cat > /sandbox/ollama_forwarder.js'
        else
            err "     $FWD_SRC 없음"
            exit 1
        fi
    fi
    # Launch as true daemon inside sandbox — nohup + stdin/stdout redirect ensures
    # openshell sandbox exec returns immediately (no blocking I/O).
    # Bug fix 2026-05-19: previous (openshell ... &) pattern caused exec to block
    # inside the forwarder loop even with &, because openshell holds a session fd.
    openshell sandbox exec -n samdtg --no-tty -- \
        bash -c 'nohup node /sandbox/ollama_forwarder.js </dev/null >/tmp/fwd.log 2>&1 &'
    sleep 4
    # Verify via HTTP instead of log grep — more reliable across log path differences
    if openshell sandbox exec -n samdtg --no-tty -- \
            curl -s --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        log "     forwarder started (HTTP verified)"
        # Mirror log to host for diagnostics
        openshell sandbox exec -n samdtg --no-tty -- \
            cat /tmp/fwd.log 2>/dev/null > /tmp/sb_forwarder.log || true
    else
        err "     forwarder did not start. sandbox log:"
        openshell sandbox exec -n samdtg --no-tty -- \
            cat /tmp/fwd.log 2>/dev/null >&2 || true
        exit 1
    fi
fi

# 5. Smoke verify both envs
if [ "${1:-}" = "--smoke" ]; then
    log "5/5  Smoke run (N1_hello × 1 rep, both envs)"
    cd "$SCRIPT_DIR"
    python3 run.py --only N1_hello --reps 1 --no-preflight 2>&1 | tail -8
else
    log "5/5  skipping smoke (run with --smoke to verify)"
fi

log "DONE. Ready to run experiments."
log ""
log "  cd $SCRIPT_DIR && python3 run.py --reps 30 &"
log ""
