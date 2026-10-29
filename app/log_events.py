"""로그 이벤트 이름.

이벤트 이름을 코드 곳곳에 문자열로 흩어 두면 오타가 나도 알 수 없고,
"어떤 이벤트가 있나"를 한눈에 볼 수 없다. 여기 한 곳에서 관리한다.

로그 레벨 기준
  INFO     정상 흐름 (요청, AI 성공, 저장 성공, 로그인 성공·실패)
  WARNING  회복 가능한 실패 (AI 실패·폴백, 응답 형식 위반)
  ERROR    예상 밖 오류, DB 저장 실패 (스택트레이스 포함)
"""

from enum import StrEnum


class Event(StrEnum):
    # cody.app — 앱 시작·종료 (DB 체크포인트 포함)
    APP_STARTED = "app_started"
    APP_STOPPED = "app_stopped"

    # cody.request — 요청 단위
    REQUEST_RECEIVED = "request_received"
    REQUEST_DONE = "request_done"
    UNHANDLED_ERROR = "unhandled_error"

    # cody.auth — 인증
    SIGNUP_SUCCESS = "signup_success"
    SIGNUP_FAILED = "signup_failed"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    STALE_SESSION = "stale_session_cleared"

    # cody.ai — AI 게이트웨이 호출
    AI_CALL_START = "ai_call_start"
    AI_CALL_SUCCESS = "ai_call_success"
    AI_CALL_FAILED = "ai_call_failed"
    AI_FALLBACK_START = "ai_fallback_start"
    AI_RESPONSE_MALFORMED = "ai_response_malformed"

    # cody.db — 대화 기록 저장
    DB_SAVE_SUCCESS = "db_save_success"
    DB_SAVE_FAILED = "db_save_failed"
