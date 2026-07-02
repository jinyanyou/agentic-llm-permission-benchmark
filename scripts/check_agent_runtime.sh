#!/usr/bin/env bash
# check_agent_runtime.sh — 8단계 환경 점검 (PASS/FAIL)
#
# 사용법:
#   bash $HOME/project/scripts/check_agent_runtime.sh
#
# 각 단계를 순차로 점검하고 PASS/FAIL 출력.
# 실패 시 다음 조치를 stderr로 안내.
# 최종 요약을 stdout, 로그를 logs/environment_check.md 에 append.

set -uo pipefail

ROOT="$HOME/project"
LOG_PATH="$ROOT/logs/environment_check.md"
SANDBOX="samdtg"
OPENCLAW_STATE_DIR="$ROOT/.openclaw"
OPENCLAW_CONFIG_PATH="$ROOT/.openclaw/openclaw.json"
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"

PASS=0
FAIL=0
declare -a RESULTS=()
declare -a ACTIONS=()

GREEN="\033[32m"
RED="\033[31m"
YELLOW="\033[33m"
RESET="\033[0m"

log_pass() {
    local step="$1" msg="$2"
    echo -e "${GREEN}[PASS]${RESET} ${step}: ${msg}"
    RESULTS+=("PASS|${step}|${msg}")
    PASS=$((PASS + 1))
}

log_fail() {
    local step="$1" msg="$2" action="$3"
    echo -e "${RED}[FAIL]${RESET} ${step}: ${msg}"
    echo -e "       ${YELLOW}=>>${RESET} ${action}" >&2
    RESULTS+=("FAIL|${step}|${msg}")
    ACTIONS+=("${step}: ${action}")
    FAIL=$((FAIL + 1))
}

echo ""
echo "========================================"
echo " agent runtime 점검  $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
echo ""

# -------------------------------------------------------
# Step 1. openclaw PATH + version
# -------------------------------------------------------
STEP="1/8 openclaw PATH"
if command -v openclaw >/dev/null 2>&1; then
    VER=$(openclaw --version 2>/dev/null | head -1 || echo "(버전 조회 실패)")
    log_pass "$STEP" "$VER"
else
    log_fail "$STEP" "openclaw 명령 없음" \
        "PATH 확인: which openclaw. brew install 또는 npm install -g openclaw"
fi

# -------------------------------------------------------
# Step 2. SSH 터널 LISTEN 여부 (port 11434)
# -------------------------------------------------------
STEP="2/8 SSH 터널 port 11434"
if curl -s --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    log_pass "$STEP" "127.0.0.1:11434 응답 OK"
else
    # netstat/ss로 LISTEN 여부도 확인
    if netstat -an 2>/dev/null | grep -q "127.0.0.1.11434.*LISTEN"; then
        log_fail "$STEP" "포트 LISTEN이나 HTTP 응답 없음 (KNU ollama 문제)" \
            "KNU 노드: pgrep -af 'ollama serve'; 없으면 OLLAMA_HOST=0.0.0.0:11434 ollama serve & 재기동"
    else
        log_fail "$STEP" "127.0.0.1:11434 LISTEN 없음 (터널 끊김)" \
            "터널 재생성: /tmp/knu_tunnel.exp 실행 또는 ssh -f -N -4 -L 127.0.0.1:11434:<DIS_NODE>:11434 -p 10000 <KNU_USER>@<LOGIN_HOST>"
    fi
fi

# -------------------------------------------------------
# Step 3. OrbStack 상태
# -------------------------------------------------------
STEP="3/8 OrbStack"
if command -v orbctl >/dev/null 2>&1; then
    ORB_STATUS=$(orbctl status 2>&1 | head -1)
    if [ "$ORB_STATUS" = "Running" ]; then
        log_pass "$STEP" "OrbStack Running"
    else
        log_fail "$STEP" "OrbStack: $ORB_STATUS" \
            "orbctl start (또는 GUI에서 OrbStack 앱 시작)"
    fi
else
    log_fail "$STEP" "orbctl 명령 없음" \
        "OrbStack 설치: https://orbstack.dev"
fi

# -------------------------------------------------------
# Step 4. OpenShell gateway Connected
# -------------------------------------------------------
STEP="4/8 OpenShell gateway"
if command -v openshell >/dev/null 2>&1; then
    GW_STATUS=$(openshell status 2>&1)
    if echo "$GW_STATUS" | grep -q "Connected"; then
        log_pass "$STEP" "gateway Connected"
    elif echo "$GW_STATUS" | grep -q "Connect"; then
        log_fail "$STEP" "gateway 연결 오류: $(echo "$GW_STATUS" | head -3)" \
            "OrbStack 먼저 기동 후: openshell gateway start --name nemoclaw"
    else
        log_fail "$STEP" "gateway 상태 불명: $(echo "$GW_STATUS" | head -2)" \
            "openshell gateway start --name nemoclaw"
    fi
else
    log_fail "$STEP" "openshell 명령 없음" \
        "openshell 설치 확인 (NemoClaw 온보딩 절차 참고)"
fi

# -------------------------------------------------------
# Step 5. 샌드박스 samdtg Ready
# -------------------------------------------------------
STEP="5/8 샌드박스 samdtg"
if command -v openshell >/dev/null 2>&1; then
    SB_STATUS=$(openshell sandbox exec -n "$SANDBOX" --no-tty -- echo "ready" 2>&1)
    if [ "$SB_STATUS" = "ready" ]; then
        log_pass "$STEP" "samdtg exec OK"
    else
        log_fail "$STEP" "samdtg exec 실패: ${SB_STATUS:0:100}" \
            "openshell status 확인; gateway 재기동 후 재시도"
    fi
else
    log_fail "$STEP" "openshell 없음 — 이전 단계 먼저 해결" ""
fi

# -------------------------------------------------------
# Step 6. 샌드박스 안 포워더 HTTP 200
# -------------------------------------------------------
STEP="6/8 sandbox forwarder"
if command -v openshell >/dev/null 2>&1; then
    # 포워더 프로세스 확인
    FWD_COUNT=$(openshell sandbox exec -n "$SANDBOX" --no-tty -- \
        pgrep -c -f ollama_forwarder 2>&1 | tail -1 | tr -dc '0-9')
    if [ "${FWD_COUNT:-0}" -gt 0 ]; then
        # API 응답도 확인
        SB_CODE=$(openshell sandbox exec -n "$SANDBOX" --no-tty -- \
            curl -s --max-time 5 -o /dev/null -w '%{http_code}' \
            http://127.0.0.1:11434/api/tags 2>/dev/null | tail -1)
        if [ "$SB_CODE" = "200" ]; then
            log_pass "$STEP" "forwarder 실행 중, /api/tags HTTP 200"
        else
            log_fail "$STEP" "forwarder 실행 중이나 API 응답 $SB_CODE" \
                "터널(Step 2) 확인; host.openshell.internal:11434 도달 가능 여부 확인"
        fi
    else
        log_fail "$STEP" "forwarder 프로세스 없음" \
            "cat $ROOT/runner/ollama_forwarder.js | openshell sandbox exec -n $SANDBOX --no-tty -- bash -c 'cat > /sandbox/ollama_forwarder.js' && openshell sandbox exec -n $SANDBOX --no-tty -- node /sandbox/ollama_forwarder.js > /tmp/sb_forwarder.log 2>&1 &"
    fi
else
    log_fail "$STEP" "openshell 없음 — 이전 단계 먼저 해결" ""
fi

# -------------------------------------------------------
# Step 7. env A openclaw infer PASS
# -------------------------------------------------------
STEP="7/8 env A infer (openclaw)"
if command -v openclaw >/dev/null 2>&1 && curl -s --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    # Bug fix 2026-05-19: consecutive check runs leave stale openclaw-agent processes
    # that hold session .lock files, causing SessionWriteLockTimeoutError on the next run.
    # Kill any leftover openclaw-agent and wait for full exit before invoking infer.
    pkill -f openclaw-agent 2>/dev/null || true
    # Wait up to 3 seconds for the agent to fully exit (lock file release).
    for _w in 1 2 3; do
        pgrep -f openclaw-agent >/dev/null 2>&1 || break
        sleep 1
    done
    # Remove stale lock files from both the project state dir and ~/.openclaw (actual runtime dir).
    # openclaw writes session locks to ~/.openclaw regardless of OPENCLAW_STATE_DIR.
    for _lock_dir in "$OPENCLAW_STATE_DIR/agents/main/sessions" "$HOME/.openclaw/agents/main/sessions"; do
        for _lf in "$_lock_dir"/*.lock; do
            [ -f "$_lf" ] || continue
            _lpid=$(python3 -c "import json; d=json.load(open('$_lf')); print(d.get('pid',''))" 2>/dev/null)
            if [ -n "$_lpid" ] && ! kill -0 "$_lpid" 2>/dev/null; then
                rm -f "$_lf"
            fi
        done
    done
    INFER_OUT=$(
        OPENCLAW_STATE_DIR="$OPENCLAW_STATE_DIR" \
        OPENCLAW_CONFIG_PATH="$OPENCLAW_CONFIG_PATH" \
        openclaw infer model run --local --model ollama/gemma4:26b \
            --prompt "1+1= 숫자만 답해" 2>&1
    ) && INFER_EXIT=0 || INFER_EXIT=$?
    if [ "$INFER_EXIT" -eq 0 ] && [ -n "$INFER_OUT" ]; then
        PREVIEW=$(echo "$INFER_OUT" | head -1 | cut -c1-60)
        log_pass "$STEP" "응답 OK: $PREVIEW"
    else
        log_fail "$STEP" "infer 실패 (exit=$INFER_EXIT): ${INFER_OUT:0:120}" \
            "openclaw config 확인: OPENCLAW_STATE_DIR=$OPENCLAW_STATE_DIR; auth-profiles.json 존재 여부 확인"
    fi
else
    log_fail "$STEP" "사전 조건(openclaw PATH 또는 터널) 미충족 — 건너뜀" \
        "Step 1, Step 2 먼저 해결"
fi

# -------------------------------------------------------
# Step 8. env B (sandbox) openclaw infer PASS
# -------------------------------------------------------
STEP="8/8 env B infer (sandbox)"
if command -v openshell >/dev/null 2>&1; then
    # 프롬프트를 직접 인라인으로 전달 (파일 경유 시 개행 문자 삽입 버그 회피)
    SB_INFER=$(
        openshell sandbox exec -n "$SANDBOX" --no-tty -- \
        bash -c 'OLLAMA_API_KEY=ollama-local OPENAI_API_KEY=ollama-local openclaw infer model run --local --model ollama/gemma4:26b --prompt "ping"' 2>&1
    ) && SB_EXIT=0 || SB_EXIT=$?
    if [ "$SB_EXIT" -eq 0 ] && [ -n "$SB_INFER" ]; then
        PREVIEW=$(echo "$SB_INFER" | head -1 | cut -c1-60)
        log_pass "$STEP" "응답 OK: $PREVIEW"
    else
        log_fail "$STEP" "infer 실패 (exit=$SB_EXIT): ${SB_INFER:0:120}" \
            "forwarder 생존 확인(Step 6); 샌드박스 내 openclaw PATH 확인; auth-profiles.json 샌드박스 내 복사 여부 확인"
    fi
else
    log_fail "$STEP" "openshell 없음 — 이전 단계 먼저 해결" ""
fi

# -------------------------------------------------------
# 요약 출력
# -------------------------------------------------------
echo ""
echo "========================================"
echo " 결과 요약"
echo "========================================"
TOTAL=$((PASS + FAIL))
echo " PASS: $PASS / $TOTAL"
echo " FAIL: $FAIL / $TOTAL"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "--- 실패 단계 조치 안내 ---" >&2
    for action in "${ACTIONS[@]}"; do
        echo "  >> $action" >&2
    done
    echo "" >&2
fi

# -------------------------------------------------------
# logs/environment_check.md append
# -------------------------------------------------------
mkdir -p "$(dirname "$LOG_PATH")"
TS=$(date '+%Y-%m-%d %H:%M:%S')
{
    echo ""
    echo "## $TS — agent runtime 점검"
    echo ""
    echo "| 단계 | 결과 | 메시지 |"
    echo "|---|---|---|"
    for r in "${RESULTS[@]}"; do
        IFS='|' read -r status step msg <<< "$r"
        echo "| $step | $status | $msg |"
    done
    echo ""
    echo "**최종**: PASS $PASS / $TOTAL"
    echo ""
} >> "$LOG_PATH"

echo " 결과를 $LOG_PATH 에 기록했습니다."
echo ""

[ "$FAIL" -eq 0 ]
