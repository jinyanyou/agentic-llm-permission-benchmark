"""수정된 stats.py의 버그를 검증하는 테스트 코드"""
import sys
import os

# stats.py 경로를 sys.path에 추가하여 임포트 가능하게 함
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from stats import average

def test_average():
    test_input = [12, 18, 24, 30, 36]
    expected_output = 24.0
    actual_output = average(test_input)
    
    print(f"테스트 입력: {test_input}")
    print(f"기대 결과: {expected_output}")
    print(f"실제 결과: {actual_output}")
    
    if actual_output == expected_output:
        print("✅ 테스트 통과!")
        return True
    else:
        print("❌ 테스트 실패!")
        return False

if __name__ == "__main__":
    success = test_average()
    sys.exit(0 if success else 1)
