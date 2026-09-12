# Cody — 영어 회화 롤플레이 파트너

상황을 고르면 AI가 상대역을 연기하고, 어색한 표현이 나오면 한국어로 교정해 주는
웹 챗봇 서비스. 연습 기록은 사용자별로 쌓여 "내가 자주 틀리는 표현"으로 다시 볼 수 있다.

## 1. 프로젝트 개요

- **문제 정의** — 영어 회화는 상대가 있어야 늘지만, 사람을 붙잡고 반복 연습하기는 어렵다.
  혼자 하는 문법 학습은 실제 발화로 이어지지 않는다.
- **타겟 사용자** — 말하기 연습 상대가 필요한 한국어 화자 학습자
- **핵심 시나리오**
  1. 로그인 후 상황(카페·공항·쇼핑 등)을 고른다
  2. 영어로 말을 건다 → AI가 상대역으로 답하고 대화를 이어간다
  3. 어색한 표현은 한국어 교정이 함께 붙는다
  4. 지난 대화와 교정 이력을 다시 볼 수 있다

## 2. 시스템 구조

```
브라우저 ──▶ FastAPI ──▶ 코디세이 게이트웨이 ──▶ gemini-3-flash  (주)
              │          copa.codyssey.kr/v1  └▶ gpt-5-mini      (폴백)
              └──▶ SQLite (users / roleplay_sessions / chat_logs)
```

OpenAI 호환 엔드포인트(`/v1/chat/completions`)를 쓰므로 `openai` SDK에
`base_url` 만 바꿔 끼운다. 모델 ID로 Anthropic·Google 계열을 함께 부를 수 있다.

**모델 선택** — 게이트웨이를 실제로 호출해 확인한 제약이 두 가지 있다.

| 확인한 것 | 결과 |
|---|---|
| Anthropic 계열(`claude-*`) | OpenAI 호환 키로는 **호출되지 않는다** (HTTP 400). Anthropic 방식 키 + `/v1/messages` 가 따로 필요하다 |
| GPT-5 계열(`gpt-5*`) | 기본값 외의 `temperature` 를 거부한다 (게이트웨이가 502). 이 모델에는 파라미터를 빼고 보낸다 |

그래서 주 모델은 `gemini-3-flash`(차감 0.5), 폴백은 **공급사가 다른** `gpt-5-mini` 로 두었다.
한쪽 공급사에 장애가 나도 다른 쪽으로 넘어간다.

폴백은 주 모델이 **5xx·연결 실패**일 때만 동작한다.
**타임아웃에는 폴백하지 않는다** — 이미 기다린 사용자를 또 기다리게 하면 체감이 두 배로 나빠지므로,
즉시 `AI_TIMEOUT` 안내로 돌린다.

| 컴포넌트 | 역할 |
|---|---|
| `app/main.py` | 앱 생성, 미들웨어(세션·요청 로깅), 전역 예외 처리 |
| `app/routers/pages.py` | 화면 라우트 |
| `app/routers/auth.py` | 회원가입 / 로그인 / 로그아웃 |
| `app/routers/chat.py` | 챗 파이프라인 (수신 → 컨텍스트 → 호출 → 저장 → 응답) |
| `app/routers/logs.py` | 사용자 기준 대화 로그 조회 |
| `app/services/ai.py` | 게이트웨이 호출, 타임아웃·실패 정규화 |
| `app/services/context.py` | 문맥 구성 전략 |
| `app/deps.py` | 인증 의존성 (`get_current_user`) |

**API 키는 서버에만 존재한다.** 브라우저는 `/api/chat` 만 호출하고 결과만 받는다.

## 3. API 명세

### `POST /api/chat` — 대화 (로그인 필요)

```json
{ "message": "I want coffee", "scenario": "cafe", "session_id": null }
```

`session_id` 가 `null` 이면 새 세션을 연다. 응답의 `session_id` 를 다음 요청에 넣어야 문맥이 이어진다.

```json
{
  "session_id": 12,
  "chat_id": 87,
  "reply": "Sure! What size would you like?",
  "correction": "\"I want coffee\" 보다 \"Could I get a coffee?\" 가 자연스러워요."
}
```

실패 시 **HTTP 503**

```json
{ "error": "AI_TIMEOUT", "message": "현재 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요." }
```

| 에러 코드 | 상황 |
|---|---|
| `AI_TIMEOUT` | 게이트웨이 응답 지연 |
| `AI_ERROR` | 호출 실패 / 빈 응답 |
| `INTERNAL_ERROR` | 그 외 예외 |

입력 검증 실패는 **422** (빈 메시지, 길이 초과, 미지원 시나리오).

### `GET /api/me/chats` — 내 대화 로그 (로그인 필요)

`?limit=50&session_id=12` — 본인 로그만 반환한다.

### `GET /api/me/corrections` — 교정이 달린 턴만

### `GET /health` — 상태 확인

## 4. DB 구조

| 테이블 | 주요 필드 |
|---|---|
| `users` | `id`, `username`(unique), `password_hash`, `created_at` |
| `roleplay_sessions` | `id`, `user_id`, `scenario`, `created_at` |
| `chat_logs` | `id`, `user_id`, `session_id`, `question`, `answer`, `correction`, `model`, `latency_ms`, `error_code`, `created_at` |

세션을 따로 둔 이유는 **문맥을 롤플레이 단위로 끊기 위해서**다. 상황이 바뀌면 앞 대화는 문맥에서 빠진다.

<!-- TODO(A): ERD 이미지 추가 -->

## 5. DB 확인 가이드

```bash
sqlite3 data/chatbot.db < scripts/check_logs.sql
```

사용자 목록, 최근 대화 20건, 사용자별 누적 통계가 출력된다.
웹으로는 `GET /api/me/chats` 로 확인할 수 있다.

## 6. 실행 방법

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: ./.venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env             # 값 채우기
uvicorn app.main:app --reload
```

**Python 3.12 이상**이 필요하다.

`.env` 의 `AI_MOCK=true` 로 두면 API 키 없이 전체 흐름이 동작한다.

### 환경 변수

| 키 | 설명 |
|---|---|
| `AI_API_KEY` | 코디세이 콘솔에서 발급 (권한: 채팅) |
| `AI_BASE_URL` | `https://copa.codyssey.kr/v1` — **`/v1` 까지만** |
| `AI_MODEL` | 주 모델. 기본 `gemini-3-flash` |
| `AI_FALLBACK_MODEL` | 보조 모델. 기본 `gpt-5-mini`. 빈 값이면 폴백 안 함 |
| `AI_TEMPERATURE` | 기본 0.7. GPT-5 계열에는 전송하지 않는다 |
| `AI_TIMEOUT` | 호출 타임아웃(초), 기본 30 |
| `AI_MAX_CONTEXT_TURNS` | 문맥에 넣을 직전 턴 수, 기본 5 |
| `AI_MOCK` | `true` 면 실제 호출 없이 더미 응답 |
| `SESSION_SECRET_KEY` | 세션 쿠키 서명 키 |
| `DATABASE_URL` | 기본 `sqlite:///./data/chatbot.db` |
| `LOG_LEVEL` | 기본 `INFO` |
| `MAX_MESSAGE_LENGTH` | 입력 길이 제한, 기본 1000 |
| `DEV_AUTH_BYPASS` | 개발용 자동 로그인. **배포 시 false** |

실제 값은 `.env` 에만 두며 저장소에 올리지 않는다 (`.gitignore` 적용).

<!-- TODO(A): 배포 절차(systemd·nginx) 추가 -->

## 7. 팀 구성원 역할

| | 담당 | 범위 |
|---|---|---|
| A | 인프라 · DB · 배포 | VM, 고정 IP, nginx/systemd, 로그 파일, ERD, 배포 문서 |
| B | 인증 · 웹 UI | 회원가입/로그인, 접근 제어, 템플릿·정적 파일 |
| C | AI 파이프라인 · 운영 | 게이트웨이 연동, 문맥 전략, 로그 저장·조회, API 명세 |

개인별 작업 요약은 작업 완료 후 채운다. 트랙별 체크리스트는 [docs/HANDOFF.md](docs/HANDOFF.md) 참고.

## 8. 협업 규칙

- `main`(배포) / `develop`(통합) / `feat/*`(작업)
- 모든 머지는 PR + 팀원 1명 승인 + CI 통과
- squash 머지 금지 (개인 커밋 이력 보존)
