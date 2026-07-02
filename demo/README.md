# 데모 3종 세트

발표(2026-06-12) 시연용. 각 데모는 단독 실행 가능하며, `runner/results/*.jsonl` 데이터를 입력으로 사용한다.

| 데모 | 목적 | 메시지 |
|---|---|---|
| `dashboard/` | SecurityScore·TaskSuccessRate 실시간 표시 | 정량 결과를 한 화면에 |
| `whitehacker/` | 동일 보안 요청 → env A 누출 / env B 차단 라이브 비교 | 권한 제어의 효과를 눈으로 |
| `quantitative/` | reps=30 분포 정적 시각화 | 통계 신뢰 구간 + 시나리오별 차이 |

## 실행 순서 (발표 당일 권장)

1. **dashboard** — 발표 시작 시 띄워두고 결과 숫자를 띄움
2. **whitehacker** — 슬라이드 9 (C_mixed 클라이맥스) 직전 라이브 시연
3. **quantitative** — 슬라이드 13 (정량 그래프 자리) 대체로 표시

## 데이터 의존
- 미니 결과: `runner/results/mini_reps3_20260519.jsonl`
- 본 실험: `runner/results/phase3_*.jsonl` (reps=30 완료 후)

발표 24h 전 마지막 갱신 권장.
