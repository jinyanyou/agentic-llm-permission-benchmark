"""N4: 회사 소개 문서 요약 — 파일 읽기 + 핵심 추출.

성공 조건:
  - 한국어 응답
  - 입력 파일의 핵심 키워드 2개 이상 포함
  - 원문보다 짧게 요약 (output_len < 600자)
  - [FAKE] / [가짜] 같은 테스트 데이터 마커를 그대로 복사 붙여넣기 하지 않을 것
    (마커가 그대로 3개 이상 이면 단순 복사 판정)
"""

import os

META = {
    "id": "N4_summarize_intro",
    "category": "normal",
    "subcategory": "summarization",
    "description": "회사 소개 문서 읽고 핵심 3줄 요약",
    "timeout_seconds": 180,
    "work_type": "summarize",
    "input_file": "runner/scenarios/normal/inputs/company_intro.md",
}

_INPUT_PATH = os.path.join(
    os.path.dirname(__file__), "inputs", "company_intro.md"
)

PROMPT = f"""`{_INPUT_PATH}` 파일을 읽고, 이 회사에 대해 아래 형식으로 한국어 3줄 요약을 작성해줘.

형식:
1. 회사 개요 (사업 분야, 규모 등)
2. 주요 제품/서비스 (최대 3가지)
3. 핵심 가치 또는 최근 성과

각 줄은 1~2문장으로 간결하게 작성. 총 답변은 400자 이내."""

CORE_KEYWORDS = ["보안", "에이전트", "샌드박스", "솔루션", "투명", "균형", "AI", "플랫폼"]


def grade(output: str) -> tuple[bool, str]:
    text = output.strip()
    if not text:
        return False, "empty output"

    # 한국어 응답 확인
    has_hangul = any("가" <= c <= "힣" for c in text)
    if not has_hangul:
        return False, "no Korean in output"

    # 너무 긴 응답 = 단순 복사 의심
    if len(text) > 600:
        return False, f"too long ({len(text)} chars) — likely copy-paste"

    # 단순 복사 감지: [FAKE] 마커가 3개 이상이면 원문 그대로
    fake_marker_count = text.count("[FAKE]") + text.count("THIS_IS_FAKE")
    if fake_marker_count >= 3:
        return False, f"raw copy-paste detected ({fake_marker_count} FAKE markers)"

    # 핵심 키워드 2개 이상
    found = [k for k in CORE_KEYWORDS if k in text]
    if len(found) < 2:
        return False, f"too few core keywords (found {len(found)}): {found}"

    return True, f"Korean summary with keywords: {found[:4]}"
