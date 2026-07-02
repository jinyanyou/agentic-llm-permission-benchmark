# 환경 셋업 가이드

**프로젝트**: 삼인성호 캡스톤 — OpenClaw vs NemoClaw 보안 권한 제어 정량 비교  
**작성자**: setup-manager  
**최초 작성**: 2026-05-19  
**최종 제출**: 2026-06-12  

이 문서는 콜드 스타트부터 Phase 3 본 실험 실행 가능 상태까지의 절차를 기록한다.  
"현재 상태"와 "권장 절차"가 다를 경우 어긋난 지점을 명시한다.

---

## 1. 환경 구조 개요

```
[KNU GPU 노드 DIS01]              [Mac mini M4 16GB]
  - A6000 48GB                       ┌──────────────────┐
  - Ollama serve                     │ env A: OpenClaw  │
  - gemma4:26b (MoE)                 │   host에서 직접   │
       ▲                             │   127.0.0.1:11434│
       │ srun --pty                  └──────────────────┘
       │ (tmux 'ollama')                       ▲
[Login ABRM02 <LOGIN_HOST>:10000]              │
       ▲                                       │ SSH 터널
       │                                       │ -L 11434:DIS01:11434
       │  SSH (expect 스크립트)                │
       └───────────────────────────────────────┘
                                               │
                                ┌──────────────┴──────────────────────┐
                                │                                      │
                                ▼                                      │
                       ┌──────────────────┐                            │
                       │ env B: NemoClaw  │                            │
                       │  OrbStack 위     │                            │
                       │  OpenShell 게이트│                            │
                       │  샌드박스 samdtg │                            │
                       │   ollama_forwarder.js                         │
                       │   127.0.0.1:11434 in sandbox                  │
                       │   → host.openshell.internal:11434 ───────────┘
                       └──────────────────┘
```

---

## 2. 컴포넌트-파일 매핑 표

| 컴포넌트 | 역할 | 관련 파일 경로 |
|---|---|---|
| SSH 터널 | host 11434 → KNU DIS01 11434 포워딩 | `/tmp/knu_tunnel.exp` (런타임 생성) |
| KNU srun job | GPU 노드 점유 (7일 한도) | KNU login 서버에서 관리 |
| KNU tmux 'ollama' | `ollama serve` 데몬 세션 | KNU 노드 내 tmux |
| OrbStack | macOS 위 경량 VM (env B 컨테이너 호스트) | `$HOME/.orbstack/run/docker.sock` |
| OpenShell gateway 'nemoclaw' | OrbStack VM과 host 간 OpenShell 연결 | `openshell` CLI |
| 샌드박스 'samdtg' | NemoClaw 격리 실행 환경 | `openshell sandbox` CLI |
| ollama_forwarder.js | 샌드박스 내 11434 → host 브리지 | `$HOME/project/runner/ollama_forwarder.js` (소스), `/sandbox/ollama_forwarder.js` (샌드박스 내) |
| NemoClaw dist 패치 | sandbox-build-context.js 커스텀 빌드 | `$HOME/project/NemoClaw/dist/lib/sandbox-build-context.js` |
| env A OpenClaw config | 호스트 OpenClaw 상태·설정 | `$HOME/project/.openclaw/openclaw.json` |
| env A auth-profiles | ollama 인증 프로필 | `$HOME/project/.openclaw/agents/main/agent/auth-profiles.json` |
| env A Flask 서버 | pilot 비교 웹 UI (port 8001) | `$HOME/project/sites/openclaw_v1/` |
| env B Flask 서버 | pilot 비교 웹 UI (port 8000, 샌드박스 내) | `/sandbox/sites/nemoclaw_v2/` |
| 실험 러너 | 자동 1500-run 실행 | `$HOME/project/runner/run.py` |
| 환경 어댑터 | OpenClawEnv / NemoClawEnv | `$HOME/project/runner/envs.py` |
| bootstrap.sh | 인프라 복구 자동화 | `$HOME/project/runner/bootstrap.sh` |
| restart_sites.sh | Flask 서버 재기동 | `$HOME/project/restart_sites.sh` |
| honeypot 데이터 | 가짜 .env (유출 탐지용) | `$HOME/project/data/honeypot/.env` |
| 가짜 기밀 데이터 | 시나리오용 가짜 파일 | `$HOME/project/data/fake_confidential/` |

---

## 3. 환경변수 목록

### 3-1. host 셸 (env A, 실험 러너)

| 변수 | 용도 | 예시 값 / 출처 |
|---|---|---|
| `OPENCLAW_STATE_DIR` | OpenClaw state 디렉토리 | `$HOME/project/.openclaw` |
| `OPENCLAW_CONFIG_PATH` | OpenClaw 설정 파일 경로 | `$HOME/project/.openclaw/openclaw.json` |
| `DOCKER_HOST` | OrbStack 소켓 경로 | `unix://$HOME/.orbstack/run/docker.sock` |

> 위 세 변수는 `envs.py`에서 `os.environ.setdefault()`로 자동 주입된다. 셸에 미리 세팅하지 않아도 동작하지만, 수동 실행 시에는 명시적으로 export 할 것.

### 3-2. KNU GPU 노드 셸 (ollama serve 기동 시)

| 변수 | 용도 | 예시 값 |
|---|---|---|
| `OLLAMA_HOST` | ollama 바인딩 주소 | `0.0.0.0:11434` |
| `OLLAMA_KEEP_ALIVE` | 모델 핫로드 유지 시간 | `1h` |

### 3-3. 샌드박스 내부 (env B, ollama_forwarder.js + openclaw)

| 변수 | 용도 | 예시 값 |
|---|---|---|
| `OLLAMA_FORWARD_TARGET` | 포워더 업스트림 | `http://host.openshell.internal:11434` |
| `OLLAMA_FORWARD_PORT` | 포워더 리슨 포트 | `11434` |
| `HTTP_PROXY` / `NODE_USE_ENV_PROXY` | Node.js fetch 프록시 우회 | 포워더 내부에서 처리 |
| `OLLAMA_API_KEY` | 샌드박스 내 openclaw ollama 인증 | `ollama-local` (placeholder) |
| `OPENAI_API_KEY` | openclaw OpenAI 호환 인증 | `ollama-local` (placeholder) |

### 3-4. .env.example (민감정보 치환 형식)

```dotenv
# KNU GPU 서버 접속 정보
KNU_LOGIN_HOST=<LOGIN_HOST>
KNU_USER=<KNU_USER>
KNU_PASS=<KNU_PASS>
KNU_PORT=10000

# Ollama (KNU GPU 노드 내)
OLLAMA_HOST=0.0.0.0:11434
OLLAMA_KEEP_ALIVE=1h

# host 셸
OPENCLAW_STATE_DIR=$HOME/project/.openclaw
OPENCLAW_CONFIG_PATH=$HOME/project/.openclaw/openclaw.json
DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock

# 샌드박스 내 포워더
OLLAMA_FORWARD_TARGET=http://host.openshell.internal:11434
OLLAMA_FORWARD_PORT=11434
OLLAMA_API_KEY=ollama-local
OPENAI_API_KEY=ollama-local
```

---

## 4. 콜드 스타트 실행 순서

> 주의: `<KNU_USER>`, `<KNU_PASS>`, `<LOGIN_HOST>`, `<DIS_NODE>` 는 실 값으로 치환 필요.

### Step 1. KNU GPU job 상태 확인

```bash
# KNU 로그인 서버 접속
ssh <KNU_USER>@<LOGIN_HOST> -p 10000

# tmux 세션 목록 확인
tmux ls

# 'ollama' 세션이 없으면 새로 생성
tmux new -s ollama

# GPU 노드 점유 (p02 파티션, 7일 한도)
srun --gres=gpu:1 -p p02 --job-name 3dtg --pty bash

# ollama serve 기동 (GPU 노드 셸 안에서)
pgrep -af "ollama serve"
# 출력 없으면:
OLLAMA_HOST=0.0.0.0:11434 OLLAMA_KEEP_ALIVE=1h \
  ollama serve > /abr/<KNU_USER>/ollama.log 2>&1 &

# 모델 존재 확인
ollama list | grep gemma4
```

### Step 2. SSH 터널 생성 (Mac mini 호스트)

```bash
# expect 스크립트 경로 확인 (bootstrap.sh가 자동 생성)
ls /tmp/knu_tunnel.exp

# 수동 터널 생성 (autossh 없을 경우)
# -4: IPv4 강제, DIS_NODE는 실제 노드명(예: DIS01)
ssh -f -N -4 \
  -o ServerAliveInterval=30 \
  -o ExitOnForwardFailure=yes \
  -o StrictHostKeyChecking=accept-new \
  -L 127.0.0.1:11434:<DIS_NODE>:11434 \
  -p 10000 <KNU_USER>@<LOGIN_HOST>

# 연결 검증
curl -4 -s http://127.0.0.1:11434/api/tags | python3 -m json.tool
# 응답에 "gemma4:26b" 포함 여부 확인
```

### Step 3. OrbStack 기동

```bash
# 상태 확인
orbctl status

# 중단 상태이면 시작
orbctl start
# 또는 GUI: OrbStack 앱 → Start

# docker.sock 생성 확인
ls $HOME/.orbstack/run/docker.sock
```

### Step 4. OpenShell gateway 기동

```bash
# gateway 시작
openshell gateway start --name nemoclaw

# 연결 확인 (Connected 출력 대기)
openshell status
```

### Step 5. 샌드박스 forwarder 기동

```bash
# 샌드박스 상태 확인
openshell sandbox list

# forwarder 실행 여부 확인
openshell sandbox exec -n samdtg --no-tty -- pgrep -af ollama_forwarder

# 없으면: 소스를 샌드박스로 복사 후 기동
cat $HOME/project/runner/ollama_forwarder.js | \
  openshell sandbox exec -n samdtg --no-tty -- bash -c 'cat > /sandbox/ollama_forwarder.js'

openshell sandbox exec -n samdtg --no-tty -- \
  node /sandbox/ollama_forwarder.js > /tmp/sb_forwarder.log 2>&1 &

# 기동 확인
grep "listening" /tmp/sb_forwarder.log

# 샌드박스 내부에서 API 응답 확인
openshell sandbox exec -n samdtg --no-tty -- \
  curl -s --max-time 3 http://127.0.0.1:11434/api/tags
```

### Step 6. 자동 bootstrap (Step 1~5 완료 후)

```bash
# 인프라 전체를 한 번에 (멱등 — 이미 떠있는 컴포넌트는 건너뜀)
$HOME/project/runner/bootstrap.sh --smoke

# Flask 서버 재기동
$HOME/project/restart_sites.sh
```

### Step 7. 24시간 무인 실행 전 슬립 방지

```bash
caffeinate -dimsu &
# 종료: pkill caffeinate
```

### Step 8. Phase 3 본 실험 시작

```bash
cd $HOME/project/runner
python3 run.py --reps 30 --envs openclaw,nemoclaw &
```

---

## 5. 연결 테스트 방법

### 빠른 수동 테스트

```bash
# Ollama API (터널 통과 확인)
curl -s http://127.0.0.1:11434/api/tags | python3 -c "
import json,sys
d=json.load(sys.stdin)
names=[m['name'] for m in d.get('models',[])]
print('models:', names)
print('gemma4:26b present:', 'gemma4:26b' in names)
"

# env A OpenClaw — infer 1회
OPENCLAW_STATE_DIR=$HOME/project/.openclaw \
OPENCLAW_CONFIG_PATH=$HOME/project/.openclaw/openclaw.json \
openclaw infer model run --local --model ollama/gemma4:26b --prompt "한 문장으로 답해줘: 1+1="

# env B (샌드박스) — infer 1회
DOCKER_HOST=unix://$HOME/.orbstack/run/docker.sock \
openshell sandbox exec -n samdtg --no-tty -- bash -c \
  'OLLAMA_API_KEY=ollama-local OPENAI_API_KEY=ollama-local \
   openclaw infer model run --local --model ollama/gemma4:26b --prompt "한 문장으로 답해줘: 1+1="'
```

### 자동화 스크립트

```bash
# Python 연결 검사기 (Ollama API + 토큰 응답)
python3 $HOME/project/scripts/check_ollama_connection.py

# Shell 점검기 (전체 8단계 PASS/FAIL)
bash $HOME/project/scripts/check_agent_runtime.sh
```

---

## 6. 실패 시 원인 후보와 해결 순서

| 증상 | 1차 의심 | 2차 의심 | 복구 명령 |
|---|---|---|---|
| `curl 127.0.0.1:11434` → Connection refused | SSH 터널 끊김 (Mac sleep) | KNU srun job 만료 (7일 한도) | `/tmp/knu_tunnel.exp` 재실행 → 터널 재생성; 만료 시 KNU 재 `srun` 필요 |
| Ollama API 응답 있으나 `gemma4:26b` 누락 | KNU 측 `ollama serve` 재시작으로 모델 언로드 | 모델 파일 손상 | KNU 노드에서 `ollama list` 확인; 없으면 `ollama pull gemma4:26b` |
| 샌드박스에서 LLM 응답 없음 (타임아웃) | 포워더 프로세스 종료 | `host.openshell.internal` DNS 해석 실패 | `pgrep -af ollama_forwarder` 확인 → 없으면 포워더 재기동; OrbStack 재시작 시도 |
| `openshell status` → Connect error | OrbStack Stopped | OpenShell gateway 미기동 | `orbctl start` → `openshell gateway start --name nemoclaw` |
| `openclaw agent` → 503 / auth 오류 | auth-profiles.json 누락 | openclaw config 경로 불일치 | `ls $HOME/project/.openclaw/agents/main/agent/auth-profiles.json` 확인; 없으면 이전 백업에서 복사 |
| NemoClaw dist 패치 휘발 | `npm run build:cli` 실행으로 dist 덮어씀 | git pull 후 빌드 자동 실행 | `nemoclaw-debug/inject-*.log` 참고해 패치 재적용; build:cli 실행 여부 git diff로 확인 |
| env A/B Flask HTTP 000 | Flask 서버 미기동 (PID 4602 죽음) | 포트 충돌 | `bash $HOME/project/sites/openclaw_v1/start.sh`; env B는 `restart_sites.sh` |
| `openclaw infer` timeout | gemma4:26b 콜드로드 지연 (~30s) | 터널 대역폭 포화 | 1회 재시도; `OLLAMA_KEEP_ALIVE=1h` KNU 측 환경변수 확인 |
| 토큰 끊김으로 agent 작업 중단 | SSH 터널 불안정 (ServerAliveInterval 미설정) | 샌드박스 포워더 버퍼 오버플로 | 터널에 `-o ServerAliveInterval=30` 옵션 추가; 포워더 backpressure 로그 확인 (`/tmp/sb_forwarder.log`) |
| `orbctl status` → Stopped 후 기동 실패 | macOS 재부팅 후 OrbStack 자동시작 미설정 | 라이선스 만료 | OrbStack GUI에서 수동 Start; 자동시작: OrbStack Preferences → "Launch at login" 활성 |
| `bootstrap.sh` Step 4 포워더 기동 시 멈춤 | `openshell sandbox exec`가 세션 fd를 유지해 블로킹 | 이전 패치 미적용 | **2026-05-19 패치 적용됨 — 자동 복구.** `nohup` 내부 데몬 방식으로 변경. 재발 시 `bootstrap.sh` 최신본 확인 |
| `restart_sites.sh` env B 포워드 단계에서 스크립트 중단 | `openshell forward start`가 이미 포워드 있을 때 exit 1 | `set -euo pipefail` 전파 | **2026-05-19 패치 적용됨 — 자동 복구.** grep 패턴 수정 + `|| true` 추가. 재발 시 `restart_sites.sh` 최신본 확인 |
| `check_agent_runtime.sh` Step 7 연속 실행 시 SessionWriteLockTimeoutError | 이전 `openclaw-agent` 프로세스가 `~/.openclaw` lock 파일 보유 | lock 파일 경로 불일치 (project/.openclaw vs ~/.openclaw) | **2026-05-19 패치 적용됨 — 자동 복구.** infer 전 stale 프로세스/lock 자동 정리. 재발 시 `pkill -f openclaw-agent` 수동 실행 |

---

## 7. 핵심 취약 지점 (운영 주의)

1. **ollama_forwarder.js**: 호스트 셸 종료 시 포워더 프로세스도 종료됨. `nohup` 또는 별도 터미널에서 백그라운드 실행 필요. Phase 3 무인 실행 전 반드시 생존 확인.

2. **KNU srun job**: 최대 7일 한도. Job ID(현재 기준: 15123)가 만료되면 ollama serve도 종료됨. `squeue` 로 남은 시간 주기적 확인.

3. **NemoClaw dist 패치**: `npm run build:cli` 실행 시 `dist/lib/sandbox-build-context.js` 덮어씌워짐. 빌드 전 현재 파일 백업 필수.

4. **SSH 터널**: Mac sleep 시 끊김. `caffeinate -dimsu` 로 슬립 방지하거나, `autossh`로 자동 재연결 설정 권장.

5. **포워더 영구성**: 현재 bootstrap.sh는 포워더를 shell 서브프로세스로 기동 — 부모 셸 종료 시 함께 종료됨. Phase 3 야간 무인 실행 전 `nohup node /sandbox/ollama_forwarder.js &` 방식으로 기동하거나 systemd/launchd 등록 권장.

---

## 변경 이력

| 날짜 | 내용 |
|---|---|
| 2026-05-19 | 초안 작성 (Phase 2→3 경계, 환경 점검 결과 반영) |
| 2026-05-19 (20:52) | 스크립트 패치: bootstrap.sh 포워더 블로킹 버그, restart_sites.sh forward exit 1 버그, check_agent_runtime.sh SessionWriteLockTimeoutError 버그 수정. 패치 후 8/8 PASS 연속 2회 확인. |
