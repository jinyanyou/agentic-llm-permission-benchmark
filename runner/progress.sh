#!/bin/bash
# 본 실험(phase3) 라이브 진행 대시보드 — 읽기 전용, 실험에 간섭 안 함
# 사용: bash $HOME/project/runner/progress.sh
#   종료: Ctrl-C

OUT="$HOME/project/runner/results/phase3_20260526_1604.jsonl"
LOG="/tmp/phase3.log"
PIDF="/tmp/phase3_pid.txt"
TOTAL=1260
INTERVAL=2.5   # 갱신 주기(초)

while true; do
  N=$(wc -l < "$OUT" 2>/dev/null | tr -d ' '); N=${N:-0}
  PID=$(cat "$PIDF" 2>/dev/null)
  ALIVE="DEAD ❌"; ELAPSED="-"
  if [ -n "$PID" ] && ps -p "$PID" >/dev/null 2>&1; then
    ALIVE="가동중 🟢"
    ELAPSED=$(ps -o etime= -p "$PID" 2>/dev/null | tr -d ' ')
  fi
  LAST=$(tail -1 "$LOG" 2>/dev/null | cut -c1-72)

  STATS=$(python3 - "$OUT" "$N" "$TOTAL" "$ELAPSED" <<'PY'
import sys, json
from collections import defaultdict
out, n, total, elapsed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
pct = 100*n/total if total else 0
# 진행 막대
barlen=40; filled=int(barlen*n/total)
bar='█'*filled + '░'*(barlen-filled)
# ETA
def sec(e):
    try:
        d=0; e=e.split('-')
        if len(e)==2: d=int(e[0]); e=e[1]
        else: e=e[0]
        p=[int(x) for x in e.split(':')]
        s=p[-1]+(p[-2]*60 if len(p)>=2 else 0)+(p[-3]*3600 if len(p)>=3 else 0)
        return d*86400+s
    except: return 0
eta='-'
el=sec(elapsed)
if el and n:
    rate=el/n; rem=(total-n)*rate
    h=int(rem//3600); m=int((rem%3600)//60)
    eta=f'{h}h {m}m  (평균 {rate:.0f}s/런)'
# env×track 집계
agg=defaultdict(lambda:[0,0])
try:
    with open(out) as f:
        for line in f:
            line=line.strip()
            if not line: continue
            r=json.loads(line)
            env=r.get('env','?'); sid=r.get('scenario_id','')
            tr='정상' if sid.startswith('N') else '공격'
            agg[(env,tr)][1]+=1
            if r.get('passed'): agg[(env,tr)][0]+=1
except: pass
print(f'  [{bar}] {pct:.1f}%')
print(f'  {n} / {total} 런   |  잔여 ETA: {eta}')
print()
for (env,tr) in sorted(agg):
    p,t=agg[(env,tr)]
    lab='차단' if tr=='공격' else '성공'
    print(f'    {env:9} {tr}: {p}/{t} {lab} ({100*p//t if t else 0}%)')
PY
)

  clear
  echo "=========================================="
  echo " Phase 3 본 실험 진행  $(date '+%H:%M:%S')"
  echo "=========================================="
  echo "  프로세스: $ALIVE   경과: ${ELAPSED:-?}"
  echo "$STATS"
  echo ""
  echo "  최근: $LAST"
  echo "------------------------------------------"
  echo "  (Ctrl-C 종료 · ${INTERVAL}초마다 갱신)"
  sleep "$INTERVAL"
done
