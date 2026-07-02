#!/usr/bin/env bash
# notify_discord.sh — 캡스톤 프로젝트 공용 Discord 알림 헬퍼 (단방향 send).
#
# 사용:
#   ./notify_discord.sh "보낼 메시지"                     # 기본 webhook
#   ./notify_discord.sh -p security "메시지"               # 프로필별 webhook
#   ./notify_discord.sh --profile work "메시지"
#   echo "메시지" | ./notify_discord.sh [-p NAME]          # stdin도 허용
#
# webhook URL 우선순위:
#   1) 환경변수 DISCORD_WEBHOOK_URL (있으면 프로필 무시하고 이걸 사용)
#   2) 프로필 파일 ~/.config/phase3/discord_webhook.<PROFILE>   (-p 지정 시)
#   3) 기본 파일   ~/.config/phase3/discord_webhook            (프로필 없거나 프로필 파일 부재 시 폴백)
#
# 프로필 = 에이전트별 채널 분리용 (security / work / setup / proj 등).
# URL을 인자/에이전트 정의에 하드코딩하지 않기 위해 파일에서 읽는다 (chmod 600).

set -uo pipefail

CONF_DIR="${PHASE3_CONF_DIR:-$HOME/.config/phase3}"
PROFILE=""

# --profile / -p 파싱 (선두 인자에서만)
if [ "${1:-}" = "--profile" ] || [ "${1:-}" = "-p" ]; then
  PROFILE="${2:-}"
  shift 2 2>/dev/null || shift $#
fi

# webhook 결정
WEBHOOK="${DISCORD_WEBHOOK_URL:-}"
USED_FILE=""
if [ -z "$WEBHOOK" ]; then
  if [ -n "$PROFILE" ] && [ -f "$CONF_DIR/discord_webhook.$PROFILE" ]; then
    USED_FILE="$CONF_DIR/discord_webhook.$PROFILE"
  elif [ -f "$CONF_DIR/discord_webhook" ]; then
    USED_FILE="$CONF_DIR/discord_webhook"
    [ -n "$PROFILE" ] && echo "[notify] 프로필 '$PROFILE' 파일 없음 → 기본 webhook으로 폴백" >&2
  fi
  [ -n "$USED_FILE" ] && WEBHOOK="$(cat "$USED_FILE" 2>/dev/null)"
fi

if [ -z "$WEBHOOK" ]; then
  echo "[notify] webhook 미설정 (프로필='$PROFILE', conf=$CONF_DIR). DISCORD_WEBHOOK_URL 또는 webhook 파일 필요" >&2
  exit 1
fi

# 메시지: 인자 우선, 없으면 stdin
if [ "$#" -ge 1 ] && [ -n "${1:-}" ]; then
  MSG="$1"
else
  MSG="$(cat)"
fi
[ -z "$MSG" ] && { echo "[notify] 빈 메시지" >&2; exit 1; }

# Discord content 한도 2000자 — 넘으면 자름
payload=$(MSG="$MSG" python3 -c '
import json,os
m=os.environ["MSG"]
if len(m)>1900: m=m[:1900]+"…(생략)"
print(json.dumps({"content": m}))
')

code=$(curl -s -o /dev/null -w "%{http_code}" -H "Content-Type: application/json" -d "$payload" "$WEBHOOK")
if [ "$code" = "204" ]; then
  echo "[notify] sent (HTTP 204${PROFILE:+, profile=$PROFILE})"
else
  echo "[notify] FAILED (HTTP $code)" >&2
  exit 1
fi
