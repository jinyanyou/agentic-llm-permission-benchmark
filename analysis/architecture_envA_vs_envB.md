# env A vs env B 아키텍처 — 권한 구조 비교

**용도**: 발표 슬라이드 5 메인 시각 (멘토 #13 "데모<시각화") + 보고서·온라인 렌더링용

**PNG (발표용)**: `architecture_envA_vs_envB.png` (1.6:0.9, 1600×900px)

**근거 데이터**: Phase 3 v2, 840런 (21 시나리오 × 2 env × 20 reps), 2026-05-28

---

## 1. 핵심 한 줄

> "동일한 AI 에이전트(gemma4:26b)가 어떤 권한 구조 위에서 실행되느냐에 따라 사내 기밀 유출이 100%와 0% 사이를 오간다."

| | env A (OpenClaw) | env B (NemoClaw) | Δ |
|---|---|---|---|
| 권한 메커니즘 | OS chmod | OpenShell Policy (Landlock + Whitelist) | — |
| SecurityScore | 34.8% | **81.5%** | **+46.7%p** |
| 사회공학(C_role) 유출 | 100% | **0%** | -100%p |

---

## 2. Mermaid 다이어그램 (보고서·온라인용)

### 2.1 env A — OpenClaw 무샌드박스

```mermaid
flowchart TD
    User_A[사용자<br/>사내 직원]
    Agent_A[AI 에이전트<br/>gemma4:26b]
    Workspace_A[워크스페이스<br/>.openclaw/]
    Secure_A[사내 기밀 폴더<br/>인사·IP·재무]
    EnvFile_A[워크스페이스 .env<br/>API 키]
    HostFS_A[호스트 FS<br/>/etc, /Users/]
    Network_A[외부 네트워크<br/>임의 도메인]

    User_A -->|요청| Agent_A
    Agent_A -->|정상 ✓| Workspace_A
    Agent_A -->|100% 유출| Secure_A
    Agent_A -->|100% 유출| EnvFile_A
    Agent_A -->|100% 유출| HostFS_A
    Agent_A -->|90% 유출| Network_A

    classDef leak fill:#f3aaa6,stroke:#b22222,color:#222
    classDef ok fill:#a7d99a,stroke:#2a7a3a,color:#222
    classDef agent fill:#f9e3a4,stroke:#666,color:#222
    classDef user fill:#dbe9f4,stroke:#666,color:#222
    class User_A user
    class Agent_A agent
    class Workspace_A ok
    class Secure_A,EnvFile_A,HostFS_A,Network_A leak
```

### 2.2 env B — NemoClaw OpenShell Policy

```mermaid
flowchart TD
    User_B[사용자<br/>사내 직원]
    Agent_B[AI 에이전트<br/>gemma4:26b — 동일 모델]
    Policy[OpenShell Policy Layer<br/>Landlock + Declarative Whitelist]
    Workspace_B[워크스페이스<br/>/sandbox/]
    Secure_B[사내 기밀 폴더<br/>paths.deny]
    EnvFile_B[워크스페이스 .env<br/>gap — §3.2]
    HostFS_B[호스트 FS<br/>invisible]
    Network_B[외부 네트워크<br/>whitelist만]

    User_B -->|요청| Agent_B
    Agent_B -->|모든 접근 거침| Policy
    Policy -->|정상 ✓| Workspace_B
    Policy -.->|0% 유출 ✓ 차단| Secure_B
    Policy -->|gap §3.2| EnvFile_B
    Policy -.->|0% 유출 ✓ 차단| HostFS_B
    Policy -->|0% 유출 ✓ whitelist| Network_B

    classDef block fill:#f3aaa6,stroke:#b22222,color:#222
    classDef gap fill:#f5d061,stroke:#c89b1c,color:#222
    classDef ok fill:#a7d99a,stroke:#2a7a3a,color:#222
    classDef policy fill:#9ad4a3,stroke:#1e6f33,color:#222,stroke-width:3px
    classDef agent fill:#f9e3a4,stroke:#666,color:#222
    classDef user fill:#dbe9f4,stroke:#666,color:#222
    class User_B user
    class Agent_B agent
    class Policy policy
    class Workspace_B,Network_B ok
    class Secure_B,HostFS_B block
    class EnvFile_B gap
```

---

## 3. 읽는 법 (발표 멘트 가이드)

### env A 멘트 (45초)
"왼쪽이 env A, OpenClaw 무샌드박스 환경입니다. 사용자가 에이전트에 요청하면, 에이전트는 호스트 OS 권한만으로 모든 자원에 접근합니다. 워크스페이스, 사내 기밀 폴더, API 키 파일, 호스트 파일시스템, 외부 네트워크 — 전부 직접 접근 가능합니다. 실험 결과 기밀 폴더 유출 100%, 사회공학 우회 100%였습니다."

### env B 멘트 (45초)
"오른쪽이 env B, NemoClaw OpenShell 샌드박스입니다. 모델은 **완전히 동일**합니다 — 같은 gemma4:26b. 다른 것은 에이전트와 자원 사이에 **정책 레이어**가 끼어든다는 것입니다. 기밀 폴더와 호스트 파일시스템은 정책에 의해 **invisible** 처리됩니다. 에이전트가 인식조차 못 합니다. 외부 네트워크는 whitelist에 등재된 도메인만 통과. 결과 — SecurityScore 81.5%, 사회공학 차단 100%."

### 마무리 (15초)
"같은 모델, 같은 프롬프트, 다른 권한 구조. **Δ +46.7%p**가 단일 의사결정 — 어떤 플랫폼을 선택할 것인가 — 에서 나옵니다."

---

## 4. 알아둘 디테일 (Q&A 대응)

- **.env gap (노란색)**: 양 환경 모두 워크스페이스 내 `.env` 평문은 접근 가능. 경로 단위 정책은 파일 내 자격증명을 구분 못 함. → §3.2 권장: 외부 secret manager.
- **C4 (/proc) 표기 누락 이유**: env A는 macOS 호스트라 /proc 없음 → "차단" 측정이 OS 차이 아티팩트. 발표 핵심에서 의도적 제외 (§5.1에만 명시).
- **정책 레이어 = OpenShell**: NemoClaw 내장. 별도 패치 불필요. 가이드라인 §3.4 "디폴트 권장"으로 입증.

---

## 5. 파일

- 발표용 PNG: `reports/phase3/architecture_envA_vs_envB.png` (160 dpi, 1600×900)
- 생성 스크립트: `scripts/plot_architecture.py`
- 본 문서: `reports/phase3/architecture_envA_vs_envB.md`
