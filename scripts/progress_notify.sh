#!/usr/bin/env bash
# progress_notify.sh — 병렬 실험(A+B) 진행률 10%마다 Discord 알림.
#
# 합산 줄 수가 10%(84런) 경계를 넘을 때마다 1회 알림. 두 프로세스가 모두
# 끝나면 종료(100% 완주 알림은 통합 완주감시가 따로 보냄).
# 상주: nohup ./progress_notify.sh </dev/null >/tmp/progress_notify.log 2>&1 &

set -uo pipefail
A=$HOME/project/runner/results/phase3_v2A_openclaw_20260528.jsonl
B=$HOME/project/runner/results/phase3_v2B_nemoclaw_20260528.jsonl
PA=$(cat /tmp/phase3_A_pid.txt 2>/dev/null)
PB=$(cat /tmp/phase3_B_pid.txt 2>/dev/null)
TOTAL=840
STEP=84   # 10%
NOTIFY=$HOME/project/scripts/notify_discord.sh

cur() {
  local a b
  a=$(wc -l < "$A" 2>/dev/null | tr -d ' '); a=${a:-0}
  b=$(wc -l < "$B" 2>/dev/null | tr -d ' '); b=${b:-0}
  echo $((a + b))
}

last=$(( $(cur) / STEP ))   # 시작 시점 버킷(이미 지난 %는 중복 알림 안 함)
echo "[progress] 시작: $(cur)/$TOTAL (버킷 $last), PA=$PA PB=$PB"

while kill -0 "$PA" 2>/dev/null || kill -0 "$PB" 2>/dev/null; do
  done=$(cur)
  b=$(( done / STEP ))
  if [ "$b" -gt "$last" ] && [ "$b" -ge 1 ] && [ "$b" -le 9 ]; then
    la=$(wc -l < "$A" 2>/dev/null | tr -d ' '); lb=$(wc -l < "$B" 2>/dev/null | tr -d ' ')
    pct=$(( b * 10 ))
    bash "$NOTIFY" "📊 phase3 v2 진행 ${pct}% (${done}/${TOTAL}) — openclaw ${la:-0}/420, nemoclaw ${lb:-0}/420" 2>/dev/null \
      && echo "[progress] ${pct}% 알림 전송" || echo "[progress] 알림 실패"
    last=$b
  fi
  sleep 30
done
echo "[progress] 두 프로세스 종료 — 진행 알림 종료(완주 알림은 완주감시가 담당)"
