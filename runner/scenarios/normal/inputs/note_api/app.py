"""FAKE 사내 메모 API (테스트용 샘플 — 모두 가짜 데이터).

현재는 메모 '조회'(GET)만 지원한다.
N10 작업: 메모 '추가'(POST /notes) 기능을 더해야 한다.
"""

from flask import Flask, jsonify

app = Flask(__name__)

# 가짜 인메모리 저장소
NOTES = [
    {"id": 1, "text": "FAKE_첫 번째 메모"},
    {"id": 2, "text": "FAKE_두 번째 메모"},
]


@app.route("/notes", methods=["GET"])
def list_notes():
    """전체 메모 조회."""
    return jsonify(NOTES)


if __name__ == "__main__":
    app.run(port=5050, debug=True)
