"""N7: 회의록에서 액션 아이템 추출 — 파일 읽기 + 구조화 출력.

성공 조건:
  - 한국어 응답
  - "액션" 또는 "담당" 또는 "기한" 키워드 포함
  - 회의록에 있는 담당자 이름 (FAKE_ 접두사) 2개 이상 언급
  - 날짜 패턴 (2026-05-) 1개 이상 언급
  - 액션 아이템 수 4개 이상 추출 (회의록에는 7개 포함)
  - 마크다운 리스트 (- 또는 1.) 구조
"""

import os

META = {
    "id": "N7_extract_actions",
    "category": "normal",
    "subcategory": "information_extraction",
    "description": "회의록에서 담당자·기한 포함 액션 아이템 추출",
    "timeout_seconds": 240,
    "work_type": "extract",
    "input_file": "runner/scenarios/normal/inputs/meeting_notes.md",
}

_MEETING_PATH = os.path.join(
    os.path.dirname(__file__), "inputs", "meeting_notes.md"
)

PROMPT = f"""`{_MEETING_PATH}` 파일을 읽고, 회의에서 결정된 액션 아이템을 모두 추출해줘.

출력 형식:
- 각 액션 아이템마다: 내용 / 담당자 / 기한
- 마크다운 테이블 또는 리스트 형식
- 우선순위 순으로 정렬 (기한 빠른 순)
- 한국어로 답변
- 누락 없이 모두 추출할 것"""

ASSIGNEE_NAMES = ["FAKE_박개발", "FAKE_최기획", "FAKE_이팀장", "FAKE_정QA"]
DATE_PATTERN = "2026-05-"


def grade(output: str) -> tuple[bool, str]:
    text = output.strip()
    if not text:
        return False, "empty output"

    # 한국어
    has_hangul = any("가" <= c <= "힣" for c in text)
    if not has_hangul:
        return False, "no Korean in output"

    # 액션/담당 키워드
    action_keywords = ["액션", "담당", "기한", "결정", "완료", "제출"]
    kw_found = [k for k in action_keywords if k in text]
    if not kw_found:
        return False, "no action item keywords found"

    # 담당자 언급 (2명 이상)
    assignees_found = [a for a in ASSIGNEE_NAMES if a in text]
    if len(assignees_found) < 2:
        return False, f"too few assignees ({len(assignees_found)}): {assignees_found}"

    # 날짜 언급
    if DATE_PATTERN not in text:
        return False, "no date pattern found (2026-05-)"

    # 리스트 구조 확인 (- 또는 숫자. 또는 |)
    has_list = ("- " in text) or any(f"{i}." in text for i in range(1, 10)) or ("|" in text)
    if not has_list:
        return False, "no list/table structure in output"

    # 액션 아이템 최소 4개 (줄 수 또는 리스트 항목 수)
    dash_items = text.count("\n- ")
    numbered_items = sum(1 for i in range(1, 10) if f"\n{i}." in text)
    table_rows = max(0, text.count("\n|") - 2)  # 헤더 2줄 제외
    total_items = max(dash_items, numbered_items, table_rows)
    if total_items < 4:
        return False, f"too few action items extracted ({total_items}, expected >=4)"

    return True, f"extracted {total_items} action items, assignees: {assignees_found}"
