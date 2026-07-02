#!/bin/bash
# 실행 경로로 이동
cd $HOME/project/runner/scenarios/normal/inputs/hotel_site

# 백그라운드 실행 (포트 8001)
nohup python3 app.py > server.log 2>&1 &

# PID 저장
echo $! > server.pid

echo "--------------------------------------------------"
echo "🏨 사내 호텔 예약 시스템이 시작되었습니다!"
echo "🔗 접속 URL: http://localhost:8001"
echo "📄 로그 파일: $(pwd)/server.log"
echo "🆔 PID: $(cat server.pid)"
echo "------------------------------------------------------------------"
