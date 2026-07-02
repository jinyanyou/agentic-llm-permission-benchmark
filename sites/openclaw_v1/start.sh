#!/bin/bash
# env A start script — manually written (agent twice failed to produce this)
SITE_DIR="$HOME/project/sites/openclaw_v1"
cd "$SITE_DIR"
nohup /usr/bin/python3 "$SITE_DIR/app.py" > "$SITE_DIR/server.log" 2>&1 &
echo $! > "$SITE_DIR/server.pid"
echo "Server started, PID: $(cat $SITE_DIR/server.pid), port 8001"
