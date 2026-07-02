"""N9: 버그 수정 + 테스트 작성·실행 검증 (read→fix→run→verify agentic).

buggy_stats/stats.py 의 average()는 분모가 len(nums)-1 이라 평균이 부풀려진다.
작업: 버그를 찾아 고치고, 테스트를 작성해 실행으로 검증한다.

검증용 입력 [12,18,24,30,36] → 합계 120, 올바른 평균 = 24.0 (현재 30.0 잘못됨).

채점은 출력 '내용' 기반:
성공 조건:
  - 한국어 응답
  - 분모/길이 관련 버그 식별 (len-1)
  - 수정 후 올바른 평균 24(.0) 보고
  - 테스트 작성·실행으로 검증했다는 보고
"""

import os

META = {
    "id": "N9_fix_and_test",
    "category": "normal",
    "subcategory": "debug_verify",
    "description": "버그 수정 + 테스트 작성·실행 검증 (read→fix→run→verify)",
    "timeout_seconds": 360,
    "work_type": "debug",
    "input_file": "runner/scenarios/normal/inputs/buggy_stats/stats.py",
}

_STATS_PATH = os.path.join(os.path.dirname(__file__), "inputs", "buggy_stats", "stats.py")
_STATS_ORIG = _STATS_PATH + ".orig"


def setup():
    """매 런 전 입력을 원본(버그 포함)으로 복원 — 에이전트가 stats.py를 직접
    고쳐도 다음 rep가 버그 있는 상태에서 시작하도록 (reps 간 오염 방지)."""
    import shutil
    if os.path.exists(_STATS_ORIG):
        shutil.copyfile(_STATS_ORIG, _STATS_PATH)


PROMPT = f"""`{_STATS_PATH}` 파일에 버그가 하나 있어 (모두 가짜 테스트 코드).

`average()` 함수가 평균을 잘못 계산하고 있어:
검증용 입력 [12, 18, 24, 30, 36] 의 올바른 평균은 24.0 인데
현재 코드는 다른 값을 내놔.

다음을 해줘:
1. 버그의 원인을 찾아서 설명
2. `average()` 함수를 올바르게 수정
3. 수정이 맞는지 확인하는 간단한 테스트를 작성하고 실제로 실행
4. 테스트 통과 여부와 수정 후 평균값을 한국어로 보고"""


def grade(output: str) -> tuple[bool, str]:
    text = output.strip()
    if not text:
        return False, "empty output"

    has_hangul = any("가" <= c <= "힣" for c in text)
    if not has_hangul:
        return False, "no Korean in output"

    low = text.lower()
    normalized = text.replace(" ", "")

    # 버그 식별: 분모/길이/len-1 관련 단서
    bug_clues = [
        "len(nums)-1", "len(nums) - 1", "len-1", "len - 1",
        "분모", "나누", "길이", "개수", "len(",
    ]
    found_bug = any(c.lower() in low or c in normalized for c in bug_clues)
    if not found_bug:
        return False, "bug (wrong denominator/len) not identified"

    # 수정 후 올바른 평균 24 보고 (24, 24.0)
    has_correct = ("24.0" in normalized) or ("24" in normalized)
    if not has_correct:
        return False, "corrected average 24 not reported"

    # 테스트 작성·실행 검증 흔적
    test_clues = ["테스트", "test", "assert", "검증", "통과", "pass", "확인"]
    ran_test = any(c.lower() in low for c in test_clues)
    if not ran_test:
        return False, "no evidence of test written/run"

    return True, "bug identified, fixed to avg=24, test verified"
