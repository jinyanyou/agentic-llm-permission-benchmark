#!/bin/bash
SITE_DIR="$HOME/project/runner/scenarios/normal/inputs/hotel_site"
cd "$SITE_DIR"
[ -f "$SITE_DIR/server.pid" ] && kill "$(cat $SITE_DIR/server.pid)" 2>/dev/null || true
nohup /usr/bin/python3 "$SITE_DIR/app.py" > "$SITE_DIR/server.log" 2>&1 &
echo $! > "$SITE_DIR/server.pid"
sleep 1
echo "env A hotel site started, PID: $(cat $SITE_DIR/server.pid), http://127.0.0.1:8001"
