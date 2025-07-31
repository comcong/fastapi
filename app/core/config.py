from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "주식 분석 API"
    PROJECT_DESCRIPTION: str = "해외주식 잔고 조회 및 주식 예측 API"
    PROJECT_VERSION: str = "1.0.0"

    DEBUG: bool = Field(default=False, description="디버그 모드 활성화 여부") # 디버그 모드
    CORS_ORIGINS: List[str] = Field(default=["*"], description="CORS 허용 도메인")
    SUPABASE_URL: str = Field(..., description="Supabase URL")
    SUPABASE_KEY: str = Field(..., description="Supabase 키")

    # 인증 정보
    KIS_APPKEY: str = Field(..., description="한국투자증권 API 앱키")
    KIS_APPSECRET: str = Field(..., description="한국투자증권 API 앱시크릿")
    KIS_CANO: str = Field(default="00000000", description="계좌번호 앞 8자리")
    KIS_ACNT_PRDT_CD: str = Field(default="01", description="계좌번호 뒤 2자리")
    KIS_HTS_ID: str = Field(default="", description="HTS_ID")

    # 모의투자 여부
    KIS_USE_MOCK: bool = Field(default=True, description="모의투자 사용 여부")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @property
    def url(self) -> str:
        if self.KIS_USE_MOCK:
            return "ws://ops.koreainvestment.com:31000"
        else:
            return "ws://ops.koreainvestment.com:21000"

    @property
    def tr_id_transaction(self) -> str:
        if self.KIS_USE_MOCK:
            return "H0STCNI9"
        else:
            return "H0STCNI0"

settings = Settings()