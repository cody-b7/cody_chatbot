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
from app.scenarios import get as get_scenario

SYSTEM_TEMPLATE = """{role}

You are helping a Korean learner practice spoken English through roleplay.
In this scene the learner needs to: {goal}

How to reply:
- Stay in character. 1-2 short, natural sentences.
- Ask one follow-up question so the conversation keeps moving.
- Move the scene forward. Do not restart the situation.

How to correct:
- Point out AT MOST ONE thing per turn, the one that matters most.
  Listing every small slip discourages the learner and they stop talking.
- Ignore typos, punctuation and capitalisation. This is spoken practice.
- Write the correction IN KOREAN: what sounded off, then a natural version.
- If their English was already natural, set "correction" to null.
- If they wrote in Korean, stay in character in English and invite them to
  try it in English. Put the Korean hint in "correction".

Respond with JSON only, no markdown fence:
{{"reply": "<your in-character line>", "correction": "<한국어 교정 or null>"}}"""


def build_messages(
    db: DbSession,
    session: RoleplaySession,
    message: str,
) -> list[dict[str, str]]:
    """게이트웨이에 보낼 messages 배열을 만든다."""
    scenario = get_scenario(session.scenario)
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": SYSTEM_TEMPLATE.format(
                role=scenario.role, goal=scenario.goal
            ),
        }
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
