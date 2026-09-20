"""롤플레이 상황 정의.

한 곳에서만 정의한다. 예전에는 목록이 schemas.py 에, 역할 설명이
context.py 에 따로 있어서, 한쪽에만 추가하면 조용히 어긋났다.
(검증은 통과하는데 AI 는 엉뚱한 역할을 연기하는 식)
"""

from typing import NamedTuple


class Scenario(NamedTuple):
    key: str
    label: str  # 화면에 보여줄 한국어 이름
    role: str  # AI 가 연기할 배역
    goal: str  # 이 대화에서 학습자가 해내야 하는 일


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "cafe",
        "카페",
        "You are a friendly barista at a busy coffee shop.",
        "order a drink and answer questions about size and options",
    ),
    Scenario(
        "restaurant",
        "식당",
        "You are a waiter at a casual restaurant.",
        "order food, ask about the menu, and request the bill",
    ),
    Scenario(
        "airport",
        "공항",
        "You are an airline check-in agent at an international airport.",
        "check in, deal with baggage, and ask about the gate",
    ),
    Scenario(
        "hotel",
        "호텔",
        "You are a receptionist at a mid-range hotel.",
        "check in, ask about facilities, and solve a small room problem",
    ),
    Scenario(
        "shopping",
        "쇼핑",
        "You are a shop assistant in a clothing store.",
        "find the right size, ask the price, and decide whether to buy",
    ),
    Scenario(
        "taxi",
        "택시",
        "You are a taxi driver in an English-speaking city.",
        "give the destination, discuss the route, and pay",
    ),
    Scenario(
        "phone",
        "전화 예약",
        "You are a receptionist taking a phone booking. You cannot see the caller.",
        "book a time on the phone and confirm the details by voice only",
    ),
    Scenario(
        "interview",
        "영어 면접",
        "You are a friendly hiring manager doing a short job interview.",
        "introduce yourself and answer follow-up questions about experience",
    ),
    Scenario(
        "smalltalk",
        "가벼운 대화",
        "You are a friendly coworker making small talk in an office kitchen.",
        "keep a casual conversation going for a few turns",
    ),
)

BY_KEY: dict[str, Scenario] = {s.key: s for s in SCENARIOS}
KEYS: tuple[str, ...] = tuple(s.key for s in SCENARIOS)
DEFAULT = BY_KEY["smalltalk"]


def get(key: str) -> Scenario:
    """모르는 키가 와도 대화가 끊기지 않도록 기본 상황으로 떨어진다."""
    return BY_KEY.get(key, DEFAULT)
