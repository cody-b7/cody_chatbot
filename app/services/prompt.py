"""AI 에게 보낼 메시지 구성.

  시스템 프롬프트(상황 + 응답·교정 규칙) + 같은 세션의 최근 N턴 + 이번 발화

세션 단위로 끊는 이유: 상황이 바뀌면 앞 대화가 롤플레이를 방해한다.
최근 N턴만 넣는 이유: 토큰 한도가 월 단위로 차감되고, 길수록 느려진다.
"""

from app.core.scenarios import BY_KEY
from app.db.models import ChatLog

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


def build_prompt_messages(
    scenario_key: str, history: list[ChatLog], message: str
) -> list[dict[str, str]]:
    scenario = BY_KEY[scenario_key]
    messages = [
        {"role": "system", "content": SYSTEM_TEMPLATE.format(role=scenario.role, goal=scenario.goal)}
    ]
    for turn in history:  # 오래된 것부터
        messages.append({"role": "user", "content": turn.question})
        messages.append({"role": "assistant", "content": turn.answer})
    messages.append({"role": "user", "content": message})
    return messages
