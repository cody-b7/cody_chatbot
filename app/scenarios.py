"""롤플레이 상황 정의.

한 곳에서만 정의한다. 예전에는 목록이 schemas.py 에, 역할 설명이
context.py 에 따로 있어서, 한쪽에만 추가하면 조용히 어긋났다.
(검증은 통과하는데 AI 는 엉뚱한 역할을 연기하는 식)

role·goal 은 AI 에게 주는 영어 지시이고,
label·partner·hint·opener 는 화면에 보여주는 값이다.
"""

from typing import NamedTuple


class Scenario(NamedTuple):
    key: str
    label: str  # 화면에 보여줄 상황 이름
    role: str  # AI 가 연기할 배역 (프롬프트용)
    goal: str  # 학습자가 해낼 일 (프롬프트용)
    partner: str  # 말풍선에 붙는 상대 배역 이름
    hint: str  # 빈 화면에 보여줄 할 일 안내
    opener: str  # 첫 마디 예시


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        key="cafe",
        label="카페",
        role="You are a friendly barista at a busy coffee shop.",
        goal="order a drink and answer questions about size and options",
        partner="바리스타",
        hint="음료를 주문하고, 사이즈나 옵션을 묻는 질문에 답해 보세요.",
        opener="Hi, could I get an iced latte?",
    ),
    Scenario(
        key="restaurant",
        label="식당",
        role="You are a waiter at a casual restaurant.",
        goal="order food, ask about the menu, and request the bill",
        partner="종업원",
        hint="메뉴를 묻고 주문한 다음, 계산까지 마쳐 보세요.",
        opener="Hi, could we see the menu, please?",
    ),
    Scenario(
        key="airport",
        label="공항",
        role="You are an airline check-in agent at an international airport.",
        goal="check in, deal with baggage, and ask about the gate",
        partner="체크인 직원",
        hint="체크인하고 짐을 부친 뒤, 탑승구를 물어보세요.",
        opener="Hi, I'd like to check in for my flight to Seoul.",
    ),
    Scenario(
        key="hotel",
        label="호텔",
        role="You are a receptionist at a mid-range hotel.",
        goal="check in, ask about facilities, and solve a small room problem",
        partner="프런트 직원",
        hint="체크인하고 시설을 물어본 다음, 객실 문제를 해결해 보세요.",
        opener="Hi, I have a reservation under the name Kim.",
    ),
    Scenario(
        key="shopping",
        label="쇼핑",
        role="You are a shop assistant in a clothing store.",
        goal="find the right size, ask the price, and decide whether to buy",
        partner="점원",
        hint="맞는 사이즈를 찾고 가격을 물어본 뒤, 살지 정해 보세요.",
        opener="Excuse me, do you have this in a medium?",
    ),
    Scenario(
        key="taxi",
        label="택시",
        role="You are a taxi driver in an English-speaking city.",
        goal="give the destination, discuss the route, and pay",
        partner="택시 기사",
        hint="목적지를 말하고 길을 이야기한 뒤, 요금을 내 보세요.",
        opener="Hi, could you take me to the train station?",
    ),
    Scenario(
        key="phone",
        label="전화 예약",
        role="You are a receptionist taking a phone booking. You cannot see the caller.",
        goal="book a time on the phone and confirm the details by voice only",
        partner="예약 담당자",
        hint="전화로 예약 시간을 잡고, 내용을 말로만 확인해 보세요.",
        opener="Hi, I'd like to book an appointment for Friday.",
    ),
    Scenario(
        key="interview",
        label="영어 면접",
        role="You are a friendly hiring manager doing a short job interview.",
        goal="introduce yourself and answer follow-up questions about experience",
        partner="면접관",
        hint="자기소개를 하고, 경력을 묻는 질문에 답해 보세요.",
        opener="Nice to meet you. Thank you for having me today.",
    ),
    Scenario(
        key="smalltalk",
        label="가벼운 대화",
        role="You are a friendly coworker making small talk in an office kitchen.",
        goal="keep a casual conversation going for a few turns",
        partner="동료",
        hint="회사 탕비실에서 동료와 가볍게 몇 마디 이어가 보세요.",
        opener="Hey, how was your weekend?",
    ),
)

BY_KEY: dict[str, Scenario] = {s.key: s for s in SCENARIOS}
KEYS: tuple[str, ...] = tuple(s.key for s in SCENARIOS)
DEFAULT = BY_KEY["smalltalk"]


def get(key: str) -> Scenario:
    """모르는 키가 와도 대화가 끊기지 않도록 기본 상황으로 떨어진다."""
    return BY_KEY.get(key, DEFAULT)
