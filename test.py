def func1():
    try:
        print("func1 시작")
        # 의도적으로 예외 발생
        raise ValueError("func1에서 강제 에러 발생")
        print("func1 끝")  # 이 줄은 실행되지 않음
    except Exception as e:
        print("func1 예외 처리:", e)

def func2():
    try:
        print("func2 시작")
        # 의도적으로 예외 발생
        raise RuntimeError("func2에서 강제 에러 발생")
        print("func2 끝")  # 이 줄은 실행되지 않음
    except Exception as e:
        print("func2 예외 처리:", e)

# 순서대로 실행
func1()
func2()
