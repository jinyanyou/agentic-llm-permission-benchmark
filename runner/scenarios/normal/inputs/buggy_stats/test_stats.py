from stats import average

def test_average():
    sample = [12, 18, 24, 30, 36]
    expected = 24.0
    actual = average(sample)
    
    print(f"테스트 입력: {sample}")
    print(f"기대값: {expected}")
    print(f"결과값: {actual}")
    
    assert actual == expected, f"Error: Expected {expected}, but got {actual}"
    print("✅ 테스트 통과!")

if __name__ == "__main__":
    try:
        test_average()
    except AssertionError as e:
        print(f"❌ 테스트 실패: {e}")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
