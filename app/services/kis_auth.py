# app/services/kis_auth.py
import requests
import time
from datetime import datetime, timedelta
import pytz
from app.core.config import settings
from app.db.kis_db import supabase
from threading import Lock
from enum import Enum

class AuthType(Enum):
    ACCESS_TOKEN = "access_token"
    APPROVAL_KEY = "approval_key"


class KISAuthService:
    """한국투자증권 API 인증 서비스 통합 클래스"""

    def __init__(self):
        # 각 인증 타입별 캐시와 락 분리
        self._caches = {
            AuthType.ACCESS_TOKEN: {
                "key": None,
                "expires_at": None,
                "last_refresh_time": 0,
                "lock": Lock()
            },
            AuthType.APPROVAL_KEY: {
                "key": None,
                "expires_at": None,
                "last_refresh_time": 0,
                "lock": Lock()
            }
        }

        # 각 인증 타입별 설정
        self._config = {
            AuthType.ACCESS_TOKEN: {
                "table_name": "access_tokens",
                "request_data": {
                    "grant_type": "client_credentials",
                    "appkey": settings.KIS_APPKEY,
                    "appsecret": settings.KIS_APPSECRET
                },
                "response_key": "access_token",
                "use_headers": False,
                "cache_message": "메모리에 캐시된 토큰 사용",
                "log_prefix": "토큰"
            },
            AuthType.APPROVAL_KEY: {
                "table_name": "approval_key",
                "request_data": {
                    "grant_type": "client_credentials",
                    "appkey": settings.KIS_APPKEY,
                    "appsecret": settings.KIS_APPSECRET
                },
                "response_key": "approval_key",
                "use_headers": True,  # approval_key는 headers에도 데이터 전달 필요
                "cache_message": "메모리에 캐시된 접속키 사용",
                "log_prefix": "접속키"
            }
        }

    def get_access_token(self):
        """Access Token 발급 또는 캐시된 토큰 반환"""
        return self._get_auth_key(AuthType.ACCESS_TOKEN)

    def get_approval_key(self):
        """Approval Key 발급 또는 캐시된 키 반환"""
        return self._get_auth_key(AuthType.APPROVAL_KEY)

    def _get_auth_key(self, auth_type: AuthType):
        """인증 키 발급 또는 캐시된 키 반환 (내부 메서드)"""
        config = self._config[auth_type]
        cache = self._caches[auth_type]

        now = datetime.now(pytz.UTC)

        # 메모리에 캐시된 키가 있고 유효하면 그것을 사용
        if cache["key"] and cache["expires_at"] and now < cache["expires_at"]:
            print(config["cache_message"])
            return cache["key"]

        # 1분 제한 체크
        current_time = time.time()
        if current_time - cache["last_refresh_time"] < 60:
            time_to_wait = 60 - (current_time - cache["last_refresh_time"])
            print(f"1분 제한으로 {time_to_wait:.1f}초 대기")
            time.sleep(time_to_wait)

        with cache["lock"]:  # 동시성 방지
            # 락 획득 후 다시 캐시 확인
            if cache["key"] and cache["expires_at"] and now < cache["expires_at"]:
                print(f"락 내에서 캐시된 {config['log_prefix']} 사용")
                return cache["key"]

            try:
                # 테이블에서 키 레코드 조회
                response = supabase.table(config["table_name"]).select("*").order("created_at", desc=True).limit(
                    1).execute()

                if response.data:
                    key_data = response.data[0]
                    expiration_time = parse_expiration_date(key_data["expiration_time"])

                    if now < expiration_time:  # 키가 아직 유효한 경우
                        print(f"기존 {config['log_prefix']} 사용 - 만료까지 남은 시간: {(expiration_time - now)}")
                        cache["key"] = key_data[config["response_key"]]
                        cache["expires_at"] = expiration_time
                        cache["last_refresh_time"] = current_time
                        return key_data[config["response_key"]]

                    print(f"{config['log_prefix']} 만료됨, 갱신 필요")
                    # 키가 만료된 경우 갱신
                    key = self._refresh_key_with_retry(auth_type, key_data["id"])
                    cache["key"] = key
                    cache["expires_at"] = now + timedelta(days=1)
                    cache["last_refresh_time"] = current_time
                    return key
                else:
                    print(f"{config['log_prefix']} 레코드 없음, 새로 생성")
                    key = self._refresh_key_with_retry(auth_type)
                    cache["key"] = key
                    cache["expires_at"] = now + timedelta(days=1)
                    cache["last_refresh_time"] = current_time
                    return key

            except Exception as e:
                print(f"{config['log_prefix']} 조회 오류: {str(e)}")
                if cache["key"]:
                    print(f"DB 조회 오류 - 메모리에 캐시된 {config['log_prefix']} 사용")
                    return cache["key"]
                raise Exception(f"{config['log_prefix']} 발급 실패: {str(e)}")

    def _refresh_key_with_retry(self, auth_type: AuthType, record_id=None, max_retries=3):
        """키 갱신을 재시도하며 처리"""
        config = self._config[auth_type]

        print(f'{config["log_prefix"]} 신규발급')

        for attempt in range(max_retries):
            try:
                # base_url 설정
                if settings.KIS_USE_MOCK == True:
                    base_url = "https://openapivts.koreainvestment.com:29443"
                elif settings.KIS_USE_MOCK == False:
                    base_url = "https://apivts.koreainvestment.com:9443"

                # auth_type에 따라 엔드포인트 분기
                if auth_type == AuthType.ACCESS_TOKEN:
                    url = f"{base_url}/oauth2/tokenP"

                else:
                    url = f"{base_url}/oauth2/Approval"


                data = config["request_data"]

                # approval_key는 headers에도 데이터를 전달해야 함
                if config["use_headers"]:
                    response = requests.post(url, json=data, headers=data)
                else:
                    response = requests.post(url, json=data)

                response_data = response.json()

                if config["response_key"] not in response_data:
                    raise Exception(f"{config['log_prefix']} 발급 실패: {response_data}")

                auth_key = response_data[config["response_key"]]
                expires_in = response_data.get("expires_in", 86400)  # 기본값 24시간(초)
                now = datetime.now(pytz.UTC)
                expiration_time = now + timedelta(seconds=expires_in)

                key_data = {
                    config["response_key"]: auth_key,
                    "expiration_time": expiration_time.isoformat(),
                    "is_active": True
                }

                # 레코드 ID가 있으면 업데이트, 없으면 새로 생성
                if record_id:
                    supabase.table(config["table_name"]).update(key_data).eq("id", record_id).execute()
                    print(f"{config['log_prefix']} 업데이트 완료")
                else:
                    supabase.table(config["table_name"]).insert(key_data).execute()
                    print(f"새 {config['log_prefix']} 레코드 생성 완료")

                return auth_key

            except Exception as e:
                print(f"{config['log_prefix']} 갱신 오류 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                if "EGW00133" in str(e) and attempt < max_retries - 1:
                    print("1분 제한 에러 발생, 61초 대기 후 재시도")
                    time.sleep(61)
                else:
                    raise

    def clear_cache(self, auth_type: AuthType = None):
        """캐시 초기화 (디버깅용)"""
        if auth_type:
            self._caches[auth_type]["key"] = None
            self._caches[auth_type]["expires_at"] = None
            print(f"{self._config[auth_type]['log_prefix']} 캐시 초기화 완료")
        else:
            for cache in self._caches.values():
                cache["key"] = None
                cache["expires_at"] = None
            print("모든 인증 캐시 초기화 완료")


# 전역 인스턴스 생성
_kis_auth_service = KISAuthService()


# 기존 함수들과 호환성을 위한 래퍼 함수들
def get_access_token():
    """한국투자증권 API 접근 토큰 발급 또는 캐시된 토큰 반환"""
    return _kis_auth_service.get_access_token()


def get_approval_key():
    """한국투자증권 API 웹소켓 접속키 발급 또는 캐시된 키 반환"""
    return _kis_auth_service.get_approval_key()


# 추가 유틸리티 함수
def clear_auth_cache(auth_type: str = None):
    """인증 캐시 초기화"""
    if auth_type == "access_token":
        _kis_auth_service.clear_cache(AuthType.ACCESS_TOKEN)
    elif auth_type == "approval_key":
        _kis_auth_service.clear_cache(AuthType.APPROVAL_KEY)
    else:
        _kis_auth_service.clear_cache()

def parse_expiration_date(date_str):
    try:
        # 정규 표현식으로 마이크로초 부분 처리
        import re
        if isinstance(date_str, str) and re.search(r'\.\d{5}\+', date_str):  # 5자리 소수점 확인
            # 마이크로초 부분을 6자리로 맞추기 - 수정된 부분
            date_str = re.sub(r'\.(\d{5})\+', r'.\g<1>0+', date_str)

        # datetime 직접 사용
        from datetime import datetime
        import pytz

        if isinstance(date_str, str):
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z")
                return dt
            except ValueError:
                # 다른 형식도 시도
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                    # 시간대 정보 추가
                    return dt.replace(tzinfo=pytz.UTC)
                except:
                    pass
        # 이미 datetime 객체인 경우
        return date_str
    except Exception as e:
        print(f"날짜 파싱 오류: {e}")
        # 현재 시간 + 1일을 기본값으로 반환 - 시간대 정보 추가
        from datetime import datetime, timedelta
        import pytz
        return datetime.now(pytz.UTC) + timedelta(days=1)