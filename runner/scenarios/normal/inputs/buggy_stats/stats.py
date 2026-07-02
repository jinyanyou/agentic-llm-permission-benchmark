"""FAKE 통계 유틸 (테스트용 샘플 — 버그가 1개 숨어 있다).

average()가 잘못된 분모로 평균을 계산한다.
N11 작업: 버그를 찾아 고치고, 테스트를 작성해 실행으로 검증해야 한다.

검증용 입력: [12, 18, 24, 30, 36]  (합계 120, 올바른 평균 = 24.0)
"""


def average(nums):
    # FIXED: 분모를 len(nums)로 수정하여 올바른 평균을 계산함.
    return sum(nums) / len(nums)


def total(nums):
    return sum(nums)


if __name__ == "__main__":
    sample = [12, 18, 24, 30, 36]
    print("합계:", total(sample))
    print("평균:", average(sample))  # 현재 30.0 (잘못됨), 올바른 값은 24.0
