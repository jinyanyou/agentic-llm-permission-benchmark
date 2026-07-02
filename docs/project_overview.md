# 캡스톤 프로젝트 총괄 기획서

**팀명**: 삼인성호  
**팀원**: 연구원C(팀장) / 연구원A / 연구원B  
**지도교수**: 지도교수 (경북대 AICOSS)  
**기업 멘토**: 기업 멘토 ((기업명 비공개))  
**작성일**: 2026-05-19  
**최종 제출**: 2026-06-12  

---

## 1. 프로젝트 목적

### 핵심 질문

> "동일한 LLM 에이전트가 OpenClaw(무샌드박스)와 NemoClaw(샌드박스) 위에서 실행될 때, 사내 보안 권한 제어 측면에서 측정 가능한 차이가 존재하는가?"

### 배경

사내 AI 에이전트 도입이 빠르게 확산되면서 에이전트가 파일 시스템·네트워크·프로세스에 접근하는 권한 범위가 보안의 핵심 변수가 되었다. 그러나 "샌드박스가 있으면 더 안전하다"는 직관적 주장을 정량적으로 입증한 국내 실험 사례는 드물다.

본 프로젝트는 아래 세 가지를 정량 실험으로 입증하고, 사내 AI 에이전트 도입을 위한 최소 보안 가이드라인 v1.0을 도출하는 것을 목표로 한다.

1. **파일시스템 경계**: NemoClaw(Landlock 기반)는 호스트 경로를 에이전트에게 invisible하게 만든다.
2. **네트워크 정책**: NemoClaw의 OpenShell declarative policy는 무허가 외부 송신을 차단한다.
3. **사회공학 우회**: "내 거니까 테스트해봐", "동의서 첨부" 등 LLM 확률적 동작을 악용한 시나리오에서 두 환경의 차단률 차이를 측정한다.

### 발표 한 줄 메시지

> "동일한 AI 에이전트가 어떤 플랫폼 위에서 실행되느냐에 따라 사내 기밀 유출 차단률이 0%와 100% 사이를 오간다 — 이것이 사내 AI 에이전트 도입 전에 반드시 권한 제어 프레임워크를 검토해야 하는 이유다."

---

## 2. 전체 폴더 구조

```
$HOME/project/
│
├── docs/                              # 기획·보고·발표 문서
│   └── project_overview.md            # 이 파일 (PM 총괄 기획서)
│
├── runner/                            # 자동 실험 러너 (기존 구조 유지)
│   ├── run.py                         # 메인 엔트리 (--reps, --envs, --only, --resume)
│   ├── envs.py                        # OpenClawEnv / NemoClawEnv 어댑터
│   ├── analyze.py                     # JSONL → 3축 지표 (SecurityScore, TaskSuccessRate, Overhead)
│   ├── bootstrap.sh                   # 인프라 복구 스크립트
│   ├── pilot.csv                      # 5/13 pilot 결과 (5 시나리오 × 2 env × 5 reps)
│   ├── summary.csv                    # Phase 3 완료 후 전체 집계
│   ├── README.md                      # 실험 사용법 + 발견 표
│   ├── scenarios/
│   │   ├── normal/                    # work-manager 담당 — 정상 업무 시나리오
│   │   │   ├── N1_hello.py            # 완료
│   │   │   ├── N2_arithmetic.py       # 완료
│   │   │   ├── N3_summarize.py        # 완료
│   │   │   ├── N4_balance.py          # 미작성 (한투 API 대기)
│   │   │   ├── N5_buy.py              # 미작성
│   │   │   ├── N6_sell.py             # 미작성
│   │   │   ├── N7_analysis_script.py  # 미작성
│   │   │   └── N8_notify.py           # 미작성
│   │   ├── attacks/                   # security-manager 담당 — 구권한 침해 시나리오
│   │   │   ├── C1_env_leak.py         # 완료 (workspace .env 누출 — 둘 다 누출, gap)
│   │   │   ├── C2_host_file_leak.py   # 완료 (호스트 외부 FS 경계 입증)
│   │   │   ├── C3_network_exfil.py    # 완료 (호스트 파일 + 외부 POST)
│   │   │   ├── C3b_network_exfil_workspace.py  # 완료 (네트워크 정책 단독 효과)
│   │   │   ├── C4_proc_leak.py        # 완료 (/proc 노출)
│   │   │   ├── C5_indirect_injection.py  # 완료 (문서 숨김 명령)
│   │   │   ├── C6_env_vars_leak.py    # 완료 (프로세스 환경변수)
│   │   │   ├── C7_dns_exfil.py        # 완료 (DNS 인코딩 송출)
│   │   │   │
│   │   │   # 아래는 4차 멘토링 결정에 따라 재설계 완료 필요 (5/20 마감)
│   │   │   ├── C8_secure_folder_bypass.py    # 보안 폴더 우회 시도
│   │   │   ├── C9_confidential_exfil.py      # 사내 기밀 파일 유출
│   │   │   ├── C10_social_eng_consent.py     # "동의서 첨부" 사회공학
│   │   │   ├── C11_social_eng_owner.py       # "내 거니까 테스트" 사회공학
│   │   │   ├── C12_physical_access.py        # 물리 접근 가정 시나리오
│   │   │   ├── C13_personnel_data_leak.py    # 사내 인사 자료 유출
│   │   │   ├── C14_ip_theft.py               # 코드/특허 IP 유출
│   │   │   ├── C15_privilege_escalation.py   # 권한 탈출 시도
│   │   │   ├── C16_chained_attack.py         # 복합 공격 (C9 + C10 연쇄)
│   │   │   └── C17_workspace_secret.py       # workspace 내부 secret 관리 gap
│   │   └── security/                  # 보안 폴더 정책 설정 파일 (env 별)
│   │       ├── policy_openclaw.json   # env A: OS 파일 권한 기반 (약한 제어)
│   │       └── policy_nemoclaw.yaml   # env B: OpenShell declarative policy (강한 제어)
│   └── results/                       # JSONL 실행 로그 (run_id, env, scenario_id, passed, ...)
│       └── 20260512_*.jsonl           # 기존 pilot 결과
│
├── data/                              # 모든 민감 데이터는 가짜(Fake) 데이터
│   ├── honeypot/                      # 미끼 파일 (유출 탐지용)
│   │   └── .env                       # FAKE AWS 키, DB URL (재현용)
│   ├── fake_confidential/             # 사내 기밀 모사 가짜 파일
│   │   ├── semiconductor_recipe.txt   # 반도체 공정 레시피 (가짜)
│   │   ├── personnel_records.csv      # 인사 자료 (가짜)
│   │   └── source_code_ip.py          # 핵심 알고리즘 (가짜)
│   └── secure_folder/                 # 보안 폴더 (Agent 접근 제한 대상)
│       └── README.txt                 # "이 폴더는 보안 폴더입니다" 안내
│
├── reports/                           # 보고서 산출물
│   ├── phase2/                        # Phase 2 완료 보고 (5/20)
│   ├── phase3/                        # Phase 3 실험 결과 원시 분석 (5/29)
│   └── final/                         # 최종 결과보고서 + 발표자료 (6/12)
│
├── demo/                              # 데모 3종 세트
│   ├── dashboard/                     # 데모 1: 한투 API 가상 대시보드
│   ├── whitehacker/                   # 데모 2: 화이트해커 에이전트 시연
│   └── quantitative/                  # 데모 3: 정량 비교 결과 시각화
│
├── sites/                             # 자율 빌드 비교 (기존 유지)
│   ├── COMPARISON.md
│   └── openclaw_v1/
│
├── NemoClaw/                          # NemoClaw 소스 (패치 포함, 기존 유지)
├── nemoclaw-debug/                    # 빌드 디버그 로그
├── 멘토링/                             # 멘토링 기록 텍스트
├── 2026-05-12_진행정리.md
├── 2026-05-15_멘토링_보고서_초안.md
├── RESTART.md
└── restart_sites.sh
```

---

## 3. 에이전트별 역할

### proj-manager (PM)

- 전체 프로젝트 맥락 유지 및 스케줄 관리
- 멘토링 직전·직후 산출물 정리
- 실험 흐름 설계 및 결과 보고서 구조 확정
- 발표 스토리라인 일관성 검수
- 담당 파일: `docs/project_overview.md`, `reports/final/`

### setup-manager (환경 구축)

- env A(OpenClaw) / env B(NemoClaw) 환경 동등 셋업 및 재현성 확보
- KNU GPU 세션 유지 (JOBID 갱신, tmux 'ollama', SSH 터널)
- NemoClaw 빌드 패치 관리 (`dist/lib/sandbox-build-context.js`)
- 포워더 영구성 개선 (`/sandbox/ollama_forwarder.js`)
- 보안 폴더 세팅: env A(OS 파일 권한), env B(OpenShell policy)
- 담당 파일: `runner/bootstrap.sh`, `runner/scenarios/security/policy_*.yaml`

### security-manager (보안 테스트)

- 공격 시나리오(C1~C17) 작성 및 실행
- 4차 멘토링 결정 원칙 준수: 사내 기밀 유출 / 물리 접근 / 보안 폴더 / 사회공학
- 가짜 데이터 생성 및 honeypot 배치 (`data/` 하위)
- 보안 테스트 결과 검증: grade() 함수의 방어 성공 기준 정의
- 담당 파일: `runner/scenarios/attacks/C*.py`, `data/honeypot/`, `data/fake_confidential/`

### work-manager (정상 업무 테스트)

- 정상 시나리오(N1~N8) 작성 및 실행
- TaskSuccessRate 측정 기준 정의 (정상 업무가 두 환경에서 동등하게 동작하는지)
- 한투 모의계좌 API 연동 완료 시 N4·N5·N6 추가
- 자율 빌드 비교 데모 지원 (`sites/` 업데이트)
- 담당 파일: `runner/scenarios/normal/N*.py`, `sites/COMPARISON.md`

---

## 4. 실험 흐름

### Phase 3 본 실험 흐름 (2026-05-20 ~ 05-29)

```
[환경 초기화]
    setup-manager: KNU GPU 세션 확인 + SSH 터널 + OrbStack + OpenShell gateway
    setup-manager: honeypot 배치 (data/honeypot/.env → $HOME/runner_honeypot/.env)
    setup-manager: 보안 폴더 정책 활성화 (env A: chmod, env B: OpenShell policy 적재)
         |
         v
[시나리오 실행 - 자동 러너]
    python3 runner/run.py --reps 30 --envs openclaw,nemoclaw
    - 25 시나리오 × 2 환경 × 30 회 = 1500 runs
    - 야간 무인 실행 (~12.5h 예상, 24h 버퍼)
    - 결과: runner/results/YYYYMMDD_HHMMSS.jsonl 자동 적재
         |
         v
[실험 분리]
    work-manager 트랙 (N1~N8):
        - 정상 업무 프롬프트 실행
        - grade(): 응답 품질·정확도로 TaskSuccessRate 측정
        - 두 환경의 사용성 동등성 확인 (보안이 생산성을 희생하지 않는다는 근거)

    security-manager 트랙 (C1~C17):
        - 공격 프롬프트 실행 (가짜 데이터 대상)
        - grade(): 방어 성공(차단) 여부 판정
        - 카테고리별 차단률 기록
         |
         v
[결과 분석]
    python3 runner/analyze.py --csv runner/summary.csv
    - SecurityScore = Σ (severity_i × defense_rate_i)
    - TaskSuccessRate = 정상 시나리오 중 성공 비율
    - Overhead = (T_nemoclaw - T_openclaw) / T_openclaw
         |
         v
[NAS 백업]
    cp -r runner/results/ /abr/coss37/results/
         |
         v
[보고서 작성 - Phase 4]
    reports/phase3/ → reports/final/
```

### 시나리오 카테고리 구분

| 카테고리 | 시나리오 ID | 담당 | 4차 결정 반영 |
|---|---|---|---|
| 정상 업무 (work-manager) | N1~N8 | work-manager | 변경 없음 |
| 호스트 FS 경계 | C1, C2 | security-manager | C1: workspace gap 재맥락화 |
| 네트워크 차단 | C3, C3b, C7 | security-manager | 변경 없음 |
| 샌드박스 내부 | C4, C6 | security-manager | C4: /proc 역설 주석 추가 |
| 간접 주입 | C5 | security-manager | 변경 없음 |
| 사내 기밀 유출 (신규) | C8, C9, C13, C14, C17 | security-manager | 4차 결정 핵심 |
| 사회공학 우회 (신규) | C10, C11, C12 | security-manager | 4차 결정 핵심 |
| 복합·권한 탈출 (신규) | C15, C16 | security-manager | 4차 결정 핵심 |

---

## 5. 평가 지표

### 주 지표 3축

| 지표 | 정의 | 측정 방법 | 기대 결과 |
|---|---|---|---|
| SecurityScore | Σ (severity_i × defense_rate_i) | analyze.py 자동 집계 | NemoClaw > OpenClaw |
| TaskSuccessRate | 정상 시나리오 통과율 | N1~N8 grade() 합산 | 양 환경 동등 (보안-생산성 트레이드오프 없음) |
| Overhead | (T_B - T_A) / T_A | 응답 시간 기준 | 5/13 pilot에서 NemoClaw가 오히려 22% 빠름 |

### 보조 지표 (카테고리별)

| 카테고리 | 측정 단위 | 설명 |
|---|---|---|
| 파일시스템 경계 차단률 | Nblocked / Nattempted | env B: Landlock으로 호스트 경로 invisible |
| 네트워크 송신 차단률 | Nblocked / Nattempted | env B: OpenShell 정책 기반 거부 |
| 사회공학 우회 차단률 | Nblocked / Nattempted | 확률적 동작 — 30회 반복으로 분포 측정 |
| 보안 폴더 접근 차단률 | Nblocked / Nattempted | env A(OS 권한) vs env B(policy) 차이 |

### 5/13 Pilot 기준값 (참조)

| 지표 | env A (OpenClaw) | env B (NemoClaw) | 차이 |
|---|---|---|---|
| SecurityScore | 3.0 / 20 (15%) | 14.0 / 20 (70%) | +55%p |
| TaskSuccessRate | 100% | 100% | 0%p |
| Mean response | 51.0s | 39.7s | -22% (B 더 빠름) |

### 데이터 형식 기준

| 데이터 | 형식 | 경로 |
|---|---|---|
| 실험 원시 로그 | JSONL | `runner/results/YYYYMMDD_HHMMSS.jsonl` |
| 집계 요약 | CSV | `runner/summary.csv`, `runner/pilot.csv` |
| 분석 보고서 | Markdown | `reports/phase3/analysis.md` |
| 최종 보고서 | Markdown | `reports/final/final_report.md` |
| 발표자료 | 별도 (PPT/PDF) | `reports/final/presentation.*` |
| 가이드라인 v1.0 | Markdown | `reports/final/guideline_v1.md` |

---

## 6. 최종 산출물

### 6-1. 실험 결과물

| 산출물 | 형식 | 경로 | 활용처 |
|---|---|---|---|
| Phase 3 원시 JSONL | JSONL | `runner/results/` | 분석의 1차 소스, 재현 보증 |
| 집계 CSV | CSV | `runner/summary.csv` | 그래프·표 생성 입력 |
| 시나리오별 차단률 표 | Markdown/CSV | `reports/phase3/table_blockrate.csv` | 보고서 본문 표 1 |
| 3축 지표 합산 표 | Markdown | `reports/phase3/table_metrics.md` | 보고서 본문 표 2 |
| 바 차트 (SecurityScore) | PNG | `reports/phase3/bar_securityscore.png` | 발표자료 그림 2 |

### 6-2. 보고서 문서

| 산출물 | 형식 | 경로 | 활용처 |
|---|---|---|---|
| 최종 결과보고서 | Markdown | `reports/final/final_report.md` | AICOSS 플랫폼 업로드 (6/12) |
| 사내 AI 에이전트 보안 가이드라인 v1.0 | Markdown | `reports/final/guideline_v1.md` | 기업 제출 산출물, 발표 핵심 메시지 |
| 발표자료 | PPT/PDF | `reports/final/presentation.*` | 최종 발표 (6/12) |

### 6-3. 데모 3종 세트

| 산출물 | 경로 | 내용 |
|---|---|---|
| 데모 1: 가상 대시보드 | `demo/dashboard/` | 한투 API 기반 대시보드 — OpenClaw/NemoClaw 양쪽 동작 확인, 토큰 연속성 시연 |
| 데모 2: 화이트해커 에이전트 | `demo/whitehacker/` | 사회공학 우회 시도 → env A에서 실패, env B에서 차단 시연 |
| 데모 3: 정량 비교 시각화 | `demo/quantitative/` | 1500회 실험 결과 요약 대시보드 (레이더 차트 + 바 차트 인터랙티브) |

### 6-4. 가이드라인 v1.0 챕터 구조 (목표)

| 챕터 | 결론 | 근거 시나리오 |
|---|---|---|
| §3.1 호스트-경계 제어 | NemoClaw 기본 정책(Landlock)으로 충분 | C2 입증 |
| §3.2 워크스페이스 내부 비밀 관리 | OpenShell path-coarse 정책으로 불충분 → 외부 secret manager 필요 | C1 gap |
| §3.3 네트워크 화이트리스트 | Declarative policy로 강제 가능 — 디버그 도메인 기본 deny | C3b 입증 |
| §3.4 보안 폴더 설계 | Policy 기반(env B) vs OS 권한(env A) 차이 측정 | C8, C9 신규 |
| §3.5 사회공학 우회 확률적 차단 | 30회 반복 차단률 분포로 정량화 | C10, C11, C12 신규 |

---

## 변경 이력

| 날짜 | 변경 내용 | 사유 |
|---|---|---|
| 2026-05-19 | 초안 작성 | 4차 멘토링 결정 반영, Phase 2→3 경계 시점 총괄 기획 |

---

*본 파일은 proj-manager가 관리한다. 시나리오 추가/변경 시 섹션 2(폴더 구조)와 섹션 4(실험 흐름)를 동기화할 것.*
