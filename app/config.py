"""애플리케이션 설정.

모든 민감정보는 .env 에서 읽는다. 코드에 값을 직접 적지 않는다.
필수 변수가 없으면 import 시점에 예외가 나므로, CI의 '앱 부팅 확인'이
설정 누락을 그대로 잡아준다.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- AI 게이트웨이 (코디세이 공개 API) ---
    AI_API_KEY: str
    AI_BASE_URL: str          # 콘솔 문서 탭 주소, ".../v1" 까지만
    AI_MODEL: str                 # 주 모델
    AI_FALLBACK_MODEL: str = ""   # 주 모델이 5xx/연결 실패일 때만 사용 (빈 값이면 비활성)
    AI_TIMEOUT: float = 30.0
    AI_TEMPERATURE: float = 0.7
    AI_MAX_CONTEXT_TURNS: int = 5
    AI_MOCK: bool = False     # true 면 실제 호출 없이 더미 응답 (토큰 절약)

    # --- 앱 ---
    SESSION_SECRET_KEY: str
    DATABASE_URL: str = "sqlite:///./data/chatbot.db"
    LOG_LEVEL: str = "INFO"
    ADMIN_USERNAME: str = "admin"

    # --- 입력 검증 ---
    MAX_MESSAGE_LENGTH: int = 1000

    # --- 개발 편의 ---
    # 인증이 붙기 전까지 첫 사용자로 자동 로그인. 배포 시 반드시 false.
    DEV_AUTH_BYPASS: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
