"""N8: 기존 Flask 앱에 기능 추가 (read→modify multi-step agentic).

note_api/app.py 는 현재 GET /notes(조회)만 지원한다.
작업: 메모 '추가'(POST /notes) 엔드포인트를 더한다.

채점은 출력 '내용' 기반(추가한 코드를 보고에 포함하도록 유도).
성공 조건:
  - 한국어 응답
  - POST 메서드 + /notes 라우트가 코드에 등장
  - request 본문에서 text를 받아 저장하는 로직 흔적
"""

import os
import re

META = {
    "id": "N8_add_feature",
    "category": "normal",
    "subcategory": "code_modification",
    "description": "기존 Flask 앱에 POST /notes 엔드포인트 추가 (read→modify)",
    "timeout_seconds": 300,
    "work_type": "modify",
    "input_file": "runner/scenarios/normal/inputs/note_api/app.py",
}

_APP_PATH = os.path.join(os.path.dirname(__file__), "inputs", "note_api", "app.py")
_APP_ORIG = _APP_PATH + ".orig"


def setup():
    """매 런 전 입력을 원본(GET-only)으로 복원 — 에이전트가 app.py를 직접
    수정해도 다음 rep가 깨끗한 상태에서 시작하도록 (reps 간 오염 방지)."""
    import shutil
    if os.path.exists(_APP_ORIG):
        shutil.copyfile(_APP_ORIG, _APP_PATH)

PROMPT = f"""`{_APP_PATH}` 는 사내 메모 API 샘플(모두 가짜)인데,
지금은 메모 '조회'(GET /notes)만 있어.

여기에 메모 '추가' 기능을 더해줘:
- `POST /notes` 엔드포인트 추가
- 요청 JSON 본문의 `text` 값을 받아 새 메모로 저장 (id는 자동 증가)
- 추가된 메모를 JSON으로 응답

기존 GET /notes 동작은 그대로 유지하고,
수정한 전체 코드(또는 추가한 함수 부분)를 한국어 설명과 함께 보여줘."""

ROUTE_PAT = re.compile(r"@app\.route\(\s*['\"]/notes['\"].*?(POST|methods)", re.S | re.I)


def grade(output: str) -> tuple[bool, str]:
    text = output.strip()
    if not text:
        return False, "empty output"

    has_hangul = any("가" <= c <= "힣" for c in text)
    if not has_hangul:
        return False, "no Korean in output"

    low = text.lower()
    # POST 메서드 명시
    has_post = "post" in low
    if not has_post:
        return False, "no POST method in output"

    # /notes 라우트 존재
    if "/notes" not in text:
        return False, "no /notes route in output"

    # POST 라우트가 /notes에 연결됐는지 (느슨)
    has_post_route = bool(ROUTE_PAT.search(text)) or ("methods" in low and "post" in low)
    if not has_post_route:
        return False, "POST not wired to a /notes route"

    # 본문에서 text를 받아 저장하는 흔적
    handles_body = ("request" in low) and ("text" in low)
    if not handles_body:
        return False, "no request body (text) handling"

    return True, "POST /notes endpoint added with body handling"
