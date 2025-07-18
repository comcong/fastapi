import time
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, Optional, Union

import pytz
import requests
from postgrest import APIResponse

from app.core.config import settings
from app.db.supabase import supabase
from app.services.auth_service import parse_expiration_date

# 메모리에 웹소켓 접속키 정보 저장 (캐싱)
_websocket_key_cache: Dict[str, Optional[Union[str, datetime]]] = {
    "approval_key": None,
    "expires_at": None
}
_websocket_last_refresh_time: float = 0  # 마지막 접속키 갱신 시간
_websocket_refresh_lock = Lock()  # 동시성 방지 락


def get_approval_key() -> str:
    """한국투자증권 웹소켓 접속키 발급 또는 캐시된 접속키 반환"""
    global _websocket_key_cache, _websocket_last_refresh_time

    # 현재 시간
    now = datetime.now(pytz.UTC)

    # 메모리에 캐시된 접속키가 있고 유효하면 그것을 사용
    if (_websocket_key_cache["approval_key"] and
            isinstance(_websocket_key_cache["expires_at"], datetime) and
            now < _websocket_key_cache["expires_at"]):
        print("메모리에 캐시된 웹소켓 접속키 사용")
        return str(_websocket_key_cache["approval_key"])

    # 1분 제한 체크 및 락 획득
    current_time = time.time()
    if current_time - _websocket_last_refresh_time < 60:
        time_to_wait = 60 - (current_time - _websocket_last_refresh_time)
        print(f"1분 제한으로 {time_to_wait:.1f}초 대기")
        time.sleep(time_to_wait)

    with _websocket_refresh_lock:  # 동시성 방지
        # 락 획득 후 다시 캐시 확인
        if (_websocket_key_cache["approval_key"] and
                isinstance(_websocket_key_cache["expires_at"], datetime) and
                now < _websocket_key_cache["expires_at"]):
            print("락 내에서 캐시된 웹소켓 접속키 사용")
            return str(_websocket_key_cache["approval_key"])

        try:
            # 테이블에서 웹소켓 접속키 레코드 조회
            response: APIResponse = supabase.from_("approval_key").select("*").order("created_at", desc=True).limit(
                1).execute()

            # 응답 검증 - data 속성이 있고 비어있지 않은지 확인
            if hasattr(response, 'data') and response.data:
                key_data = response.data[0]

                # 필수 필드 존재 확인
                if not key_data.get("approval_key") or not key_data.get("expiration_time"):
                    print("응답 데이터에 필수 필드 누락, 새로 생성")
                    key = refresh_websocket_key_with_retry()
                    _websocket_key_cache["approval_key"] = key
                    _websocket_key_cache["expires_at"] = now + timedelta(hours=24)
                    _websocket_last_refresh_time = current_time
                    return key

                expiration_time = parse_expiration_date(key_data["expiration_time"])
                if isinstance(expiration_time, datetime) and now < expiration_time:
                    print(f"기존 웹소켓 접속키 사용 - 만료까지 남은 시간: {(expiration_time - now)}")
                    _websocket_key_cache["approval_key"] = key_data["approval_key"]
                    _websocket_key_cache["expires_at"] = expiration_time
                    _websocket_last_refresh_time = current_time
                    return key_data["approval_key"]

                print("웹소켓 접속키 만료됨, 갱신 필요")
                key = refresh_websocket_key_with_retry(key_data.get("id"))
                _websocket_key_cache["approval_key"] = key
                _websocket_key_cache["expires_at"] = now + timedelta(hours=24)
                _websocket_last_refresh_time = current_time
                return key
            else:
                print("웹소켓 접속키 레코드 없음, 새로 생성")
                key = refresh_websocket_key_with_retry()
                _websocket_key_cache["approval_key"] = key
                _websocket_key_cache["expires_at"] = now + timedelta(hours=24)
                _websocket_last_refresh_time = current_time
                return key

        except Exception as e:
            print(f"웹소켓 접속키 조회 오류: {str(e)}")
            if _websocket_key_cache["approval_key"]:
                print("DB 조회 오류 - 메모리에 캐시된 웹소켓 접속키 사용")
                return str(_websocket_key_cache["approval_key"])
            raise Exception(f"웹소켓 접속키 발급 실패: {str(e)}")


def refresh_websocket_key_with_retry(record_id: Optional[str] = None, max_retries: int = 3) -> str:
    """웹소켓 접속키 갱신을 재시도하며 처리"""
    for attempt in range(max_retries):
        try:
            url = f"{settings.kis_base_url}/oauth2/Approval"
            data = {
                "grant_type": "client_credentials",
                "appkey": settings.KIS_APPKEY,
                "secretkey": settings.KIS_APPSECRET
            }
            headers = {
                "content-type": "application/json; charset=utf-8"
            }

            response = requests.post(url, json=data, headers=headers)

            # HTTP 상태 코드 확인
            if response.status_code != 200:
                raise Exception(f"API 요청 실패: HTTP {response.status_code} - {response.text}")

            response_data = response.json()

            if 'approval_key' not in response_data:
                raise Exception(f"웹소켓 접속키 발급 실패: {response_data}")

            approval_key = response_data["approval_key"]
            now = datetime.now(pytz.UTC)
            expiration_time = now + timedelta(hours=24)  # 웹소켓 접속키는 24시간 유효

            key_data = {
                "approval_key": approval_key,
                "expiration_time": expiration_time.isoformat(),
                "is_active": True
            }

            try:
                if record_id:
                    db_response = supabase.from_("approval_key").update(key_data).eq("id", record_id).execute()
                    print("웹소켓 접속키 업데이트 완료")
                else:
                    db_response = supabase.from_("approval_key").insert(key_data).execute()
                    print("새 웹소켓 접속키 레코드 생성 완료")
            except Exception as db_error:
                print(f"DB 저장 오류: {str(db_error)}")
                # DB 저장 실패해도 API에서 받은 키는 반환 (임시 사용 가능)

            return approval_key

        except Exception as e:
            print(f"웹소켓 접속키 갱신 오류 (시도 {attempt + 1}/{max_retries}): {str(e)}")
            if "EGW00133" in str(e) and attempt < max_retries - 1:
                print("1분 제한 에러 발생, 61초 대기 후 재시도")
                time.sleep(61)  # 1분 이상 대기
            else:
                raise


if __name__ == "__main__":
    res = get_approval_key()
    print(res)