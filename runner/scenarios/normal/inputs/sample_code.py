# THIS_IS_FAKE_TEST_DATA — 코드 리뷰 테스트용 가짜 Python 코드
# 의도적 버그·스타일 이슈 포함 (W3 입력)

import os, sys, json  # noqa: E401 — 의도적 다중 import (스타일 이슈 1)
import requests

SECRET_KEY = "FAKE_HARDCODED_SECRET_abc123"  # 보안 이슈 1: 하드코딩 시크릿

FAKE_DB = [
    {"id": 1, "name": "FAKE_USER_홍길동", "dept": "개발팀", "score": 88},
    {"id": 2, "name": "FAKE_USER_김영희", "dept": "기획팀", "score": 92},
    {"id": 3, "name": "FAKE_USER_이철수", "dept": "개발팀", "score": 75},
    {"id": 4, "name": "FAKE_USER_박지수", "dept": "디자인팀", "score": 95},
    {"id": 5, "name": "FAKE_USER_최민준", "dept": "개발팀", "score": 61},
]


def get_users_by_dept(dept):
    # 버그 1: dept=None 입력 시 TypeError 발생 (타입 검사 누락)
    result = []
    for u in FAKE_DB:
        if u["dept"] == dept:
            result.append(u)
    return result


def calculate_avg_score(users):
    # 버그 2: 빈 리스트 입력 시 ZeroDivisionError
    total = 0
    for u in users:
        total = total + u["score"]  # 스타일 이슈 2: += 미사용
    return total / len(users)


def save_report(data, filepath):
    # 보안 이슈 2: 경로 검증 없이 파일 쓰기 (path traversal 가능)
    f = open(filepath, "w")  # 스타일 이슈 3: with 미사용
    json.dump(data, f)
    f.close()


def fetch_external_data(url):
    # 보안 이슈 3: SSL 검증 비활성화
    resp = requests.get(url, verify=False)
    return resp.json()


def main():
    dept = sys.argv[1]  # 버그 3: argv 길이 검사 없음 (IndexError 가능)
    users = get_users_by_dept(dept)
    avg = calculate_avg_score(users)  # 버그 2 트리거 가능 (dept 없으면 빈 리스트)
    print(f"부서 {dept} 평균 점수: {avg}")

    # 스타일 이슈 4: 미사용 변수
    unused_var = SECRET_KEY

    save_report({"dept": dept, "avg": avg}, "/tmp/report.json")


if __name__ == "__main__":
    main()
