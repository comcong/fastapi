import requests
import time
from datetime import datetime, timedelta
import pytz
from app.core.config import settings
from app.db.supabase import supabase
from threading import Lock
from app.services.auth_service import parse_expiration_date

# 메모리에 접속키 정보 저장 (캐싱)
_key_cache = {
    "approval_key": None,
    "expires_at": None
}
_last_refresh_time = 0  # 마지막 키 갱신 시간
_refresh_lock = Lock()  # 동시성 방지 락

def get_approval_key():
    """한국투자증권 API 웹소켓 접속키 발급 또는 캐시된 키 반환"""
    global _key_cache, _last_refresh_time

    # 현재 시간
    now = datetime.now(pytz.UTC)

    # 메모리에 캐시된 키가 있고 유효하면 그것을 사용
    if _key_cache["approval_key"] and _key_cache["expires_at"] and now < _key_cache["expires_at"]:
        print("메모리에 캐시된 접속키 사용")
        return _key_cache["approval_key"]

    # 1분 제한 체크 및 락 획득
    current_time = time.time()
    if current_time - _last_refresh_time < 60:
        time_to_wait = 60 - (current_time - _last_refresh_time)
        print(f"1분 제한으로 {time_to_wait:.1f}초 대기")
        time.sleep(time_to_wait)

    with _refresh_lock:  # 동시성 방지
        # 락 획득 후 다시 캐시 확인
        if _key_cache["approval_key"] and _key_cache["expires_at"] and now < _key_cache["expires_at"]:
            print("락 내에서 캐시된 접속키 사용")
            return _key_cache["approval_key"]

        try:
            # 테이블에서 접속키 레코드 조회
            response = supabase.table("approval_key").select("*").order("created_at", desc=True).limit(1).execute()

            if response.data:
                key_data = response.data[0]

                # auth_service의 parse_expiration_date 함수 사용
                expiration_time = parse_expiration_date(key_data["expiration_time"])

                if now < expiration_time:  # 키가 아직 유효한 경우
                    print(f"기존 접속키 사용 - 만료까지 남은 시간: {(expiration_time - now)}")
                    _key_cache["approval_key"] = key_data["approval_key"]
                    _key_cache["expires_at"] = expiration_time
                    _last_refresh_time = current_time
                    return key_data["approval_key"]

                print("접속키 만료됨, 갱신 필요")
                # 키가 만료된 경우 갱신
                key = refresh_key_with_retry(key_data["id"])
                _key_cache["approval_key"] = key
                _key_cache["expires_at"] = now + timedelta(days=1)
                _last_refresh_time = current_time
                return key
            else:
                print("접속키 레코드 없음, 새로 생성")
                key = refresh_key_with_retry()
                _key_cache["approval_key"] = key
                _key_cache["expires_at"] = now + timedelta(days=1)
                _last_refresh_time = current_time
                return key

        except Exception as e:
            print(f"접속키 조회 오류: {str(e)}")
            if _key_cache["approval_key"]:
                print("DB 조회 오류 - 메모리에 캐시된 접속키 사용")
                return _key_cache["approval_key"]
            raise Exception(f"접속키 발급 실패: {str(e)}")

def refresh_key_with_retry(record_id=None, max_retries=3):
    """접속키 갱신을 재시도하며 처리"""
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
                "secretkey": settings.KIS_APPSECRET
            }

            response = requests.post(url, json=data, headers=headers)
            response_data = response.json()

            if 'approval_key' not in response_data:
                raise Exception(f"접속키 발급 실패: {response_data}")

            approval_key = response_data["approval_key"]
            expires_in = response_data.get("expires_in", 86400)  # 기본값 24시간(초)
            now = datetime.now(pytz.UTC)
            expiration_time = now + timedelta(seconds=expires_in)

            key_data = {
                "approval_key": approval_key,
                "expiration_time": expiration_time.isoformat(),
                "is_active": True
            }

            # 레코드 ID가 있으면 업데이트, 없으면 새로 생성
            if record_id:
                supabase.table("approval_key").update(key_data).eq("id", record_id).execute()
                print("접속키 업데이트 완료")
            else:
                supabase.table("approval_key").insert(key_data).execute()
                print("새 접속키 레코드 생성 완료")

            return approval_key

        except Exception as e:
            print(f"접속키 갱신 오류 (시도 {attempt + 1}/{max_retries}): {str(e)}")
            if "EGW00133" in str(e) and attempt < max_retries - 1:
                print("1분 제한 에러 발생, 61초 대기 후 재시도")
                time.sleep(61)  # 1분 이상 대기
            else:
                raise