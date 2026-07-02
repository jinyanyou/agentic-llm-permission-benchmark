#!/usr/bin/env bash
# tunnel_watchdog.sh — KNU SSH 터널(host 127.0.0.1:11434) 헬스 감시 + 자동 재연결.
#
# 배경: 2026-05-28 본 실험 도중 SSH 터널이 끊겨 nemoclaw 추론이 전부 empty FAIL.
#       openclaw는 무사했으나 env B가 전멸 위기 → 터널 죽음을 빨리 잡아 복구해야 한다.
#
# 동작: 30초마다 호스트 11434 /api/tags 확인 → 죽으면 /tmp/knu_tunnel.exp로 재생성.
#       복구/실패를 Discord(setup 채널)로 1회 알림(상태 변화 시에만, 도배 방지).
# 상주: nohup ./tunnel_watchdog.sh </dev/null >/tmp/tunnel_watchdog.log 2>&1 &

set -uo pipefail
NOTIFY=$HOME/project/scripts/notify_discord.sh
TAGS_URL=http://127.0.0.1:11434/api/tags
EXP=/tmp/knu_tunnel.exp
prev_state="up"   # up | down

check() { curl -s --max-time 6 -o /dev/null "$TAGS_URL" 2>/dev/null; }

echo "[$(date '+%F %T')] tunnel_watchdog 시작 (대상 $TAGS_URL)"
while true; do
  if check; then
    if [ "$prev_state" = "down" ]; then
      echo "[$(date '+%F %T')] 터널 복구 확인"
      bash "$NOTIFY" -p setup "⚙️ KNU 터널 자동 복구됨 (watchdog 재연결 성공)" 2>/dev/null || true
      prev_state="up"
    fi
  else
    echo "[$(date '+%F %T')] 터널 DOWN 감지 — 재연결 시도"
    if [ "$prev_state" = "up" ]; then
      bash "$NOTIFY" -p setup "🚨 KNU 터널 DOWN 감지 — 자동 재연결 시도 중 (nemoclaw 런 영향 가능)" 2>/dev/null || true
      prev_state="down"
    fi
    # 좀비 터널 정리 후 재생성
    pkill -f "11434:DIS" 2>/dev/null || true
    sleep 1
    if [ -x "$EXP" ]; then
      "$EXP" >/dev/null 2>&1 || true
    fi
    sleep 3
    if check; then
      echo "[$(date '+%F %T')] 재연결 성공"
      bash "$NOTIFY" -p setup "⚙️ KNU 터널 자동 복구됨 (watchdog 재연결 성공)" 2>/dev/null || true
      prev_state="up"
    else
      echo "[$(date '+%F %T')] 재연결 실패 — 다음 주기 재시도"
    fi
  fi
  sleep 30
done
