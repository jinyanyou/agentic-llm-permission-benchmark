#!/usr/bin/env bash
# phase3_watcher.sh — Phase 3 본 실험의 완주/중단을 감지해 Discord로 알림.
#
# 사용:
#   ./phase3_watcher.sh <DISCORD_WEBHOOK_URL>            # 기본 (PID/파일 자동)
#   ./phase3_watcher.sh <URL> <PID> <JSONL> <LOG>        # 명시 지정
#
# 동작: 실험 프로세스(PID)가 살아있는 동안 대기 → 종료되면 로그/결과를 보고
#       정상 완주([done] 존재)인지 중단인지 판정해 Discord에 1회 메시지 전송.
# 상주: nohup ./phase3_watcher.sh <URL> </dev/null >/tmp/phase3_watcher.log 2>&1 &

set -uo pipefail

WEBHOOK="${1:?Discord webhook URL이 필요합니다}"
PID="${2:-$(cat /tmp/phase3_pid.txt 2>/dev/null)}"
JSONL="${3:-$HOME/project/runner/results/phase3_20260526_1604.jsonl}"
LOG="${4:-/tmp/phase3.log}"
TOTAL=1260

notify() {
  local msg="$1"
  local payload
  payload=$(python3 -c 'import json,sys; print(json.dumps({"content": sys.argv[1]}))' "$msg")
  curl -s -H "Content-Type: application/json" -d "$payload" "$WEBHOOK" >/dev/null \
    && echo "[watcher] notified: $msg" \
    || echo "[watcher] notify FAILED"
}

if [ -z "${PID:-}" ]; then
  echo "[watcher] PID 없음 — /tmp/phase3_pid.txt 확인 필요"; exit 1
fi

echo "[watcher] 감시 시작: PID=$PID, JSONL=$JSONL"
# 프로세스가 살아있는 동안 대기
while kill -0 "$PID" 2>/dev/null; do sleep 30; done
echo "[watcher] 프로세스 종료 감지"

DONE=$(wc -l < "$JSONL" 2>/dev/null | tr -d ' ')
LAST=$(tail -1 "$LOG" 2>/dev/null)

# env별 pass rate 요약 (분석 없이 jsonl 직접 집계)
SUMMARY=$(python3 - "$JSONL" <<'PY' 2>/dev/null
import json,sys,collections
agg=collections.defaultdict(lambda:[0,0])  # env -> [pass,total]
for line in open(sys.argv[1]):
    line=line.strip()
    if not line: continue
    try: d=json.loads(line)
    except: continue
    e=d.get("env","?"); agg[e][1]+=1
    if d.get("passed"): agg[e][0]+=1
parts=[f"{e}: {p}/{t} ({100*p//t if t else 0}%)" for e,(p,t) in sorted(agg.items())]
print(" / ".join(parts))
PY
)

if grep -q '^\[done\]' "$LOG" 2>/dev/null; then
  notify "✅ phase3 본 실험 완주: ${DONE}/${TOTAL}런 완료\n📊 ${SUMMARY}\n📝 ${LAST}"
else
  notify "⚠️ phase3 본 실험 중단: ${DONE}/${TOTAL}런에서 멈춤 — 재개(--resume) 필요\n📝 ${LAST}"
fi
echo "[watcher] 완료"
