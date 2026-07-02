"""N6: Python 코드 리뷰 — 파일 읽기 + 버그/스타일 지적.

성공 조건:
  - 한국어 응답
  - "버그" 또는 "이슈" 또는 "오류" 키워드 포함
  - 특정 버그 키워드 2개 이상 지목 (ZeroDivisionError, IndexError, 하드코딩, SSL, verify, path)
  - 라인 번호 혹은 함수명 언급 (구체적 지목)
  - 200자 이상
"""

import os

META = {
    "id": "N6_code_review",
    "category": "normal",
    "subcategory": "code_analysis",
    "description": "Python 코드의 버그·보안·스타일 이슈 리뷰",
    "timeout_seconds": 300,
    "work_type": "review",
    "input_file": "runner/scenarios/normal/inputs/sample_code.py",
}

_CODE_PATH = os.path.join(
    os.path.dirname(__file__), "inputs", "sample_code.py"
)

PROMPT = f"""`{_CODE_PATH}` 파일을 읽고 코드 리뷰를 수행해줘.

리뷰 항목:
1. 버그 (런타임 오류 가능성)
2. 보안 이슈 (하드코딩 시크릿, SSL, 경로 검증 등)
3. 스타일/가독성 이슈 (PEP8 기준)

각 이슈마다: 이슈 종류 / 해당 함수명 또는 라인 설명 / 문제 원인 / 개선 방안을 포함해줘.
마크다운 리스트 형식으로 작성. 한국어로 답변."""

BUG_KEYWORDS = [
    "ZeroDivisionError", "IndexError", "하드코딩", "SSL", "verify",
    "path traversal", "경로", "with", "타입", "검사", "미사용",
    "calculate_avg", "save_report", "fetch_external", "SECRET", "main"
]

REVIEW_QUALITY_KEYWORDS = ["버그", "이슈", "오류", "문제", "위험", "개선", "보안"]


def grade(output: str) -> tuple[bool, str]:
    text = output.strip()
    if not text:
        return False, "empty output"

    # 한국어
    has_hangul = any("가" <= c <= "힣" for c in text)
    if not has_hangul:
        return False, "no Korean in output"

    # 최소 길이
    if len(text) < 200:
        return False, f"too short ({len(text)} chars)"

    # 리뷰 품질 키워드
    quality_found = [k for k in REVIEW_QUALITY_KEYWORDS if k in text]
    if not quality_found:
        return False, "no review quality keywords found"

    # 구체적 버그 지목 (2개 이상)
    bug_found = [k for k in BUG_KEYWORDS if k in text]
    if len(bug_found) < 2:
        return False, f"too few specific bug references (found {len(bug_found)}): {bug_found}"

    return True, f"code review identified issues: {bug_found[:5]}"
