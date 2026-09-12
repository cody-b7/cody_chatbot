"""컨텍스트 구성 전략.

  시스템 프롬프트(시나리오 + 출력 규칙)
  + 같은 세션의 최근 N턴 (AI_MAX_CONTEXT_TURNS)
  + 이번 발화

세션 단위로 끊는 이유는 롤플레이 상황이 바뀌면 앞 대화가 방해가 되기 때문이다.
전체 히스토리를 넣지 않는 이유는 토큰 한도(월 차감) 때문이다.
"""

from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.models import ChatLog, RoleplaySession

SCENARIO_ROLES: dict[str, str] = {
    "cafe": "You are a friendly barista at a busy coffee shop.",
    "restaurant": "You are a waiter at a casual restaurant.",
    "airport": "You are an airline check-in agent at an international airport.",
    "shopping": "You are a shop assistant in a clothing store.",
    "smalltalk": "You are a friendly coworker making small talk in an office kitchen.",
}

SYSTEM_TEMPLATE = """{role}

You are helping a Korean learner practice spoken English.

Rules:
- Stay in character. Keep your reply to 1-2 short, natural sentences.
- Ask a follow-up question so the conversation keeps going.
- If the learner's last message has an unnatural or incorrect expression,
  explain it briefly IN KOREAN and give a better version.
- If their English is already natural, set "correction" to null.

Respond with JSON only, no markdown fence:
{{"reply": "<your in-character line>", "correction": "<한국어 교정 or null>"}}"""


def build_messages(
    db: DbSession,
    session: RoleplaySession,
    message: str,
) -> list[dict[str, str]]:
    """게이트웨이에 보낼 messages 배열을 만든다."""
    role = SCENARIO_ROLES.get(session.scenario, SCENARIO_ROLES["smalltalk"])
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_TEMPLATE.format(role=role)}
    ]

    recent = (
        db.query(ChatLog)
        .filter(ChatLog.session_id == session.id, ChatLog.error_code.is_(None))
        .order_by(ChatLog.id.desc())
        .limit(settings.AI_MAX_CONTEXT_TURNS)
        .all()
    )
    for log in reversed(recent):  # 오래된 것부터
        messages.append({"role": "user", "content": log.question})
        messages.append({"role": "assistant", "content": log.answer})

    messages.append({"role": "user", "content": message})
    return messages
