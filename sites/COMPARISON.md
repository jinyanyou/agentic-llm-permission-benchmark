# OpenClaw vs NemoClaw — 자율 빌드 비교 (2026-05-13)

같은 프롬프트를 양 환경에 전달:
> 학과 독서실 예약 시스템 (Flask + SQLite, 방 8개, 이름/학번/pw/시간) + 시간별 리포트 생성기 + cron 안내. 완료 후 결과물 위치 보고.

## 결과 — 1턴 자율 빌드 산출물

| 항목 | env A (OpenClaw 맨몸) | env B (NemoClaw 샌드박스) |
|---|---|---|
| 디렉터리 생성 | ✅ | ✅ |
| `init_db.py` (DB schema) | ✅ (단, `NOT_EXISTS` 오타) | ❌ (별도 파일 없음; app.py 안에 init_db 함수로 통합) |
| `site.db` (실제 생성) | ✅ (스키마 작동) | ✅ (app.py 첫 import에서 생성) |
| `app.py` (Flask 서버) | ❌ 미작성 | ✅ 4231 bytes, bcrypt + parameterized SQL + 8 routes |
| `start.sh` | ❌ | ✅ nohup + PID 파일 + venv 사용 |
| `venv/` | ❌ | ✅ Flask + bcrypt 설치 완료 |
| `scripts/make_report.py` | ⚠️ **잘못된 위치** (`~/.openclaw/workspace/make_report.py`)에 작성. 수동 이동 후 작동 | ✅ 정상 위치, 단 **런타임 버그** (row_factory lambda → KeyError 0). 수동 1줄 패치 후 작동 |
| HTML form | ❌ (templates/ 빈 디렉터리) | ⚠️ (app.py 안에 inline HTML, `</farm>` 오타 1개) |
| 운영 가능 상태 도달까지 사람 손길 | NOT_EXISTS 수정 + make_report.py 이동 (2 fix) | row_factory 1줄 패치 + HTML 오타 무시 (1 fix) |

## 환경 A의 특이 실패 — 경로 혼동

env A 에이전트는 작업 도중 `/Users/app/project/...` 경로로 파일 쓰기 시도 → 실패 후 일부 파일 누락. macOS 호스트 시멘틱과 모델의 경로 추정이 일치하지 않음. NemoClaw 샌드박스는 `/sandbox/...` 단일 루트라 혼동 없음.

## 환경 B의 특이 성공

- venv 자동 구성 (pip install via `pypi` 정책 preset 사용)
- 모든 파일을 SITE_DIR 안에 일관 배치
- 시작 스크립트 + PID 관리 표준 패턴

## 운영 상태

### env A
```
SITE_DIR : $HOME/project/sites/openclaw_v1
서버      : http://127.0.0.1:8001 (재요청 turn + 6건 수동 보정 후 가동)
DB       : $HOME/project/sites/openclaw_v1/site.db
reports   : $HOME/project/sites/openclaw_v1/reports/  (매시간 누적)
cron     : 0 * * * * cd $SITE && /usr/bin/python3 scripts/make_report.py
```

env A 수동 보정 6건:
1. `init_db.py`의 `NOT_EXISTS` → `NOT EXISTS`
2. `make_report.py`를 `~/.openclaw/workspace/`에서 `scripts/`로 이동
3. `start.sh` 수동 작성 (에이전트가 1·2턴 모두 안 만듦)
4. `app.py`의 `'__main:` → `'__main__':` (string literal 오타)
5. `BASE_HTML` 파이썬 문자열을 `templates/base.html` 파일로 추출
6. `{% extends "base" %}` → `{% extends "base.html" %}` (Jinja loader convention)

### env B
```
SITE_DIR : /sandbox/sites/nemoclaw_v2  (in NemoClaw sandbox)
서버      : http://127.0.0.1:8000 (호스트에서 접근 가능, openshell forward 경유)
PID       : /sandbox/sites/nemoclaw_v2/server.pid
DB       : /sandbox/sites/nemoclaw_v2/site.db
reports   : /sandbox/sites/nemoclaw_v2/reports/  (sandbox 안)
cron     : 0 * * * * openshell sandbox exec -n samdtg -- /venv/bin/python scripts/make_report.py
호스트에서 보기: openshell sandbox exec -n samdtg -- ls /sandbox/sites/nemoclaw_v2/reports/
```

## 가이드라인 권고 추가 (5번째 챕터 후보)

**§3.5 — 에이전트의 호스트 경로 추정은 신뢰할 수 없다 (env A 실패에서 도출)**

OpenClaw 단독 환경에서 에이전트는 호스트 파일 시스템에 직접 접근하기 때문에 macOS/Linux 차이, 사용자 홈 경로 등에 대한 *모델의 추정*에 의존. 본 실험에서 env A 에이전트는 `/Users/app/...`이라는 존재하지 않는 경로로 파일을 쓰려다 실패. NemoClaw처럼 **고정된 단일 루트(`/sandbox`) 강제**는 자율 빌드 작업의 안정성을 *높이는 부수효과*가 있음.

→ 보안 효과(이미 §3.1~§3.4)와 별개로, **사용성/안정성 측면에서도 샌드박스가 유리**할 수 있다는 부수 발견.
