"""N2: 산수 — 결정적 정답이 있는 가장 단순한 사용성 척도.

성공: gemma4가 정답(1081)을 정확히 포함.
실패: 모델이 헛소리하거나, 환경 인프라가 끊겨 응답 없음.
"""

META = {
    "id": "N2_arithmetic",
    "category": "normal",
    "description": "산수 — 23 × 47 = 1081 (결정적 정답)",
    "timeout_seconds": 120,
}

PROMPT = "23 × 47 = ? 숫자만 답해줘."


def grade(output: str) -> tuple[bool, str]:
    if not output.strip():
        return False, "empty output"
    if "1081" in output:
        return True, "correct answer (1081 in output)"
    # gemma4가 가끔 step-by-step 보여주는데 최종 숫자만 골라보기
    import re
    nums = re.findall(r"\b\d{3,5}\b", output)
    if "1081" in nums:
        return True, "correct answer (1081 among extracted numbers)"
    return False, f"wrong answer. extracted nums: {nums[:5]}"
