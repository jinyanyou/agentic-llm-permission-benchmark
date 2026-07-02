#!/usr/bin/env bash
# capture_hotel_screenshots.sh — Safari + screencapture로 호텔 페이지 PNG
# 멘토 #14 (회사 홈페이지 더미 데이터 스크린샷)
set -euo pipefail

OUTDIR=$HOME/project/reports/final/screenshots
mkdir -p "$OUTDIR"

# Safari 윈도우 bounds: {left, top, right, bottom}. 메뉴바 22px.
WIN_LEFT=0
WIN_TOP=22
WIN_W=1280
WIN_H=900
WIN_RIGHT=$((WIN_LEFT + WIN_W))
WIN_BOTTOM=$((WIN_TOP + WIN_H))

# 캡처 영역 (탭바+툴바 약 110px, 페이지 콘텐츠 ~720px)
CAP_X=$WIN_LEFT
CAP_Y=$((WIN_TOP + 110))
CAP_W=$WIN_W
CAP_H=720

capture_url() {
    local URL=$1
    local FILE=$2
    echo "[capture] $URL -> $FILE"

    # 1) 윈도우 deminiaturize + 크기 잡고 URL 로드
    osascript <<APPLESCRIPT
tell application "Safari"
    activate
    if (count of windows) = 0 then
        make new document
    end if
    set miniaturized of window 1 to false
    set visible of window 1 to true
    set bounds of window 1 to {$WIN_LEFT, $WIN_TOP, $WIN_RIGHT, $WIN_BOTTOM}
    set index of window 1 to 1
    set URL of current tab of window 1 to "$URL"
end tell
APPLESCRIPT

    # 로딩 대기
    sleep 6

    # 2) 캡처 직전에 Safari 강제 frontmost (System Events) — 터미널이 가리는 사고 방지
    osascript >/dev/null <<'AS'
tell application "Safari" to activate
delay 0.5
tell application "System Events"
    set frontmost of process "Safari" to true
end tell
AS
    sleep 2

    # 3) 영역 캡처
    screencapture -x -R ${CAP_X},${CAP_Y},${CAP_W},${CAP_H} "$OUTDIR/$FILE"
    echo "       saved $OUTDIR/$FILE ($(stat -f%z "$OUTDIR/$FILE") bytes)"
}

capture_url "http://127.0.0.1:8001/" "envA_hotel_8001.png"
capture_url "http://127.0.0.1:8000/" "envB_hotel_8000.png"
capture_url "http://127.0.0.1:8000/reservations" "envB_hotel_8000_reservations.png"

echo
echo "=== Done ==="
ls -la "$OUTDIR"/*.png
