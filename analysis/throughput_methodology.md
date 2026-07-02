# Throughput 측정 방법론 + 검증 보고서

**대상**: KNU A6000 + gemma4:26b Q4_K_M
**일시**: 2026-06-04
**원본 데이터**: `throughput_a6000.json` (v1, 5/3프롬프트), `throughput_a6000_v2.json` (v2, 검증)

## 1. 측정 방법

```python
# Ollama /api/generate 호출 후 응답에서:
tok_per_sec = eval_count / (eval_duration_ns / 1e9)
```

- `eval_count`: 모델이 생성한 토큰 수
- `eval_duration_ns`: **생성에 걸린 순수 시간 (nanoseconds)**, prompt eval·model load·network 시간 제외

Ollama 공식 표준 방식 (CLI `ollama run --verbose`도 같은 산식).

## 2. v1 측정 결과 (1차)

- 5회 × 3프롬프트 (짧은 QA·중간 요약·긴 코드) × num_predict=400 = 15회
- **mean = 101.02 tok/s, stdev = 0.84, min = 99.81, max = 103.17** (n=15)

## 3. v2 검증 — 4가지 의심 포인트 점검

### (A) Generation 길이별 — 짧은 응답이 더 빠른가?

| num_predict | mean tok/s | stdev |
|---|---|---|
| 50 | 103.68 | 2.67 |
| 100 | 102.90 | 0.89 |
| 200 | 101.72 | 0.94 |
| **400** | **101.37** | **0.25** |
| 800 | 99.73 | 0.17 |
| 1200 | 98.68 | 0.12 |

**해석**: 길이가 길수록 KV cache가 커져 memory bandwidth 압박 → 약 5% 감소. 일반적 패턴. **400토큰 기준 101 tok/s는 정확** (v1과 v2 일치).

### (B) 동시 요청 — 사내 다중 사용자 시 throughput?

각 측정 직전 warmup 1회 실시 (cold start 제거).

| n_concurrent | per-request tok/s | wall (s) | aggregate tok/s |
|---|---|---|---|
| 1 | 101.83 | 2.77 | 72.3 |
| 2 | 102.06 | 5.24 | 76.3 |
| 4 | 100.84 | 10.76 | 74.3 |

**중요 발견**: Ollama 단일 GPU는 동시 요청을 **직렬 처리**.
- per-request throughput은 N에 관계없이 동일 (~101 tok/s)
- wall time이 정확히 N배 증가 (2.77 × 4 ≈ 11.06)
- aggregate throughput은 단일 요청과 같음

**시사점 (발표 슬라이드 12 보강)**:
> "사내 직원 4명이 동시에 요청하면 4번째 직원은 ~10초 대기. 사내 LLM 도입 시 vLLM 같은 multi-slot batching 엔진 또는 추가 GPU 필요."

### (C) TTFT (Time To First Token)

| 측정 | TTFT (s) |
|---|---|
| Run 1 | 1.63 |
| Run 2 | 1.74 |
| Run 3 | 2.27 |
| **평균** | **1.88** |

**해석**: 사용자 체감 첫 응답 시간 = ~1.9초. 상용 ChatGPT(0.5~1s) 대비 살짝 느리지만 사용 가능 수준.

### (D) Prompt eval 노이즈 — 무시해도 되는가?

v1에서 prompt_tok_per_sec가 1327~10327로 들쭉날쭉했던 이유 = 짧은 prompt(43 tokens) + nanosecond 정밀도 한계.

v2 측정 (긴 prompt 5회):
- 값: 5580, 5912, 5918, 5922, 5928 tok/s
- ratio max/min = **1.06x** (안정)

**결론**: prompt eval = ~5900 tok/s (generation의 58배). 짧은 prompt 측정 시 무시. **generation throughput에는 영향 없음**.

## 4. 최종 답

**A6000 + gemma4:26b Q4_K_M throughput** (확정):

| 지표 | 값 | 조건 |
|---|---|---|
| **Generation throughput (단일 요청)** | **101 tok/s** | 400 토큰 기준, stdev <1% |
| 짧은 응답 (50~200 토큰) | 102~104 tok/s | — |
| 긴 응답 (800~1200 토큰) | 99~100 tok/s | KV cache 영향 |
| Prompt eval | ~5900 tok/s | 긴 prompt 기준 |
| TTFT | ~1.9s | — |
| **다중 사용자 (직렬 처리)** | per-user 101 tok/s, **대기 N배** | Ollama 단일 슬롯 한계 |

## 5. 발표 적용

**슬라이드 12 (부족함 ① throughput)** 추가 한 줄:
> "단일 사용자 101 tok/s. 그러나 Ollama는 동시 요청을 직렬 처리 — 사내 4명 동시 시 4번째는 10초 대기. **vLLM 같은 batching 엔진 또는 GPU 다중화가 다음 단계 과제**."

## 6. 한계 (정직하게)

- **모델 1종(gemma4:26b Q4_K_M)만 측정**: 다른 양자화(FP16, Q8_0)·다른 모델(llama3, qwen)은 측정 안 함
- **단일 GPU(A6000) 1대**: 멀티 GPU·텐서 병렬 안 봄
- **Ollama만 측정**: vLLM·TGI·SGLang 등 batching 엔진은 측정 안 함 (단 발표에서 명시)
- **컨텍스트 길이 고정**: 4K 정도. 32K·64K 긴 컨텍스트는 측정 안 함
