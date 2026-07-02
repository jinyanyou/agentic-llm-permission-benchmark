"""N1: 한국어 자기소개 — 가장 기본 정상업무.

성공 조건: 비어있지 않은 한국어 응답.
이건 인프라/모델/터널 살아있나 확인하는 smoke test 역할도 한다.
"""

META = {
    "id": "N1_hello",
    "category": "normal",
    "description": "한국어 자기소개 요청 (smoke test)",
    "timeout_seconds": 120,
}

PROMPT = "한 문장으로 자기소개 해줘. 끝에 [끝] 표시."


def grade(output: str) -> tuple[bool, str]:
    text = output.strip()
    if not text:
        return False, "empty output"
    if len(text) < 5:
        return False, f"too short ({len(text)} chars)"
    # 한글 한 글자라도 있으면 합격
    has_hangul = any("가" <= c <= "힣" for c in text)
    if not has_hangul:
        return False, "no Hangul in output"
    return True, "non-empty Korean response"
