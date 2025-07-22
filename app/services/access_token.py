import requests
import time
from datetime import datetime, timedelta
import pytz
from app.core.config import settings
from app.db.supabase import supabase
from threading import Lock
from app.services.auth_service import parse_expiration_date

# 메모리에 토큰 정보 저장 (캐싱)
_token_cache = {
    "access_token": None,
    "expires_at": None
}
_last_refresh_time = 0  # 마지막 토큰 갱신 시간
_refresh_lock = Lock()  # 동시성 방지 락

def get_access_token():
    """한국투자증권 API 접근 토큰 발급 또는 캐시된 토큰 반환"""
    global _token_cache, _last_refresh_time

    # 현재 시간
    now = datetime.now(pytz.UTC)

    # 메모리에 캐시된 토큰이 있고 유효하면 그것을 사용
    if _token_cache["access_token"] and _token_cache["expires_at"] and now < _token_cache["expires_at"]:
        print("메모리에 캐시된 토큰 사용")
        return _token_cache["access_token"]

    # 1분 제한 체크 및 락 획득
    current_time = time.time()
    if current_time - _last_refresh_time < 60:
        time_to_wait = 60 - (current_time - _last_refresh_time)
        print(f"1분 제한으로 {time_to_wait:.1f}초 대기")
        time.sleep(time_to_wait)

    with _refresh_lock:  # 동시성 방지
        # 락 획득 후 다시 캐시 확인
        if _token_cache["access_token"] and _token_cache["expires_at"] and now < _token_cache["expires_at"]:
            print("락 내에서 캐시된 토큰 사용")
            return _token_cache["access_token"]

        try:
            # 테이블에서 토큰 레코드 조회
            response = supabase.table("access_tokens").select("*").order("created_at", desc=True).limit(1).execute()

            if response.data:
                token_data = response.data[0]

                # auth_service의 parse_expiration_date 함수 사용
                expiration_time = parse_expiration_date(token_data["expiration_time"])

                if now < expiration_time:  # 토큰이 아직 유효한 경우
                    print(f"기존 토큰 사용 - 만료까지 남은 시간: {(expiration_time - now)}")
                    _token_cache["access_token"] = token_data["access_token"]
                    _token_cache["expires_at"] = expiration_time
                    _last_refresh_time = current_time
                    return token_data["access_token"]

                print("토큰 만료됨, 갱신 필요")
                # 토큰이 만료된 경우 갱신
                token = refresh_token_with_retry(token_data["id"])
                _token_cache["access_token"] = token
                _token_cache["expires_at"] = now + timedelta(days=1)
                _last_refresh_time = current_time
                return token
            else:
                print("토큰 레코드 없음, 새로 생성")
                token = refresh_token_with_retry()
                _token_cache["access_token"] = token
                _token_cache["expires_at"] = now + timedelta(days=1)
                _last_refresh_time = current_time
                return token

        except Exception as e:
            print(f"토큰 조회 오류: {str(e)}")
            if _token_cache["access_token"]:
                print("DB 조회 오류 - 메모리에 캐시된 토큰 사용")
                return _token_cache["access_token"]
            raise Exception(f"토큰 발급 실패: {str(e)}")

def refresh_token_with_retry(record_id=None, max_retries=3):
    """토큰 갱신을 재시도하며 처리"""
    for attempt in range(max_retries):
        try:
            # base_url 설정
            if settings.KIS_USE_MOCK == True:
                base_url = "https://openapivts.koreainvestment.com:29443"
            elif settings.KIS_USE_MOCK == False:
                base_url = "https://apivts.koreainvestment.com:9443"

            url = f"{base_url}/oauth2/Approval"

            data = {
                "grant_type": "client_credentials",
                "appkey": settings.KIS_APPKEY,
                "appsecret": settings.KIS_APPSECRET
            }

            response = requests.post(url, json=data)
            response_data = response.json()

            if 'access_token' not in response_data:
                raise Exception(f"토큰 발급 실패: {response_data}")

            access_token = response_data["access_token"]
            expires_in = response_data.get("expires_in", 86400)  # 기본값 24시간(초)
            now = datetime.now(pytz.UTC)
            expiration_time = now + timedelta(seconds=expires_in)

            token_data = {
                "access_token": access_token,
                "expiration_time": expiration_time.isoformat(),
                "is_active": True
            }

            # 레코드 ID가 있으면 업데이트, 없으면 새로 생성
            if record_id:
                supabase.table("access_tokens").update(token_data).eq("id", record_id).execute()
                print("토큰 업데이트 완료")
            else:
                supabase.table("access_tokens").insert(token_data).execute()
                print("새 토큰 레코드 생성 완료")

            return access_token

        except Exception as e:
            print(f"토큰 갱신 오류 (시도 {attempt + 1}/{max_retries}): {str(e)}")
            if "EGW00133" in str(e) and attempt < max_retries - 1:
                print("1분 제한 에러 발생, 61초 대기 후 재시도")
                time.sleep(61)  # 1분 이상 대기
            else:
                raise