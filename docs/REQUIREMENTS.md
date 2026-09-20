# 요구사항 대조표

과제 문서의 기능 요구사항이 **코드 어디에서 충족되는지**와, **무엇으로 증명되는지**를 정리한다.
평가 직전 점검표이자 발표 대본으로 쓴다.

> 기준 커밋: `develop`
> 테스트: **92개** (`pytest -q`)
> 범례: ✅ 완료 · 🔵 진행 중 · ⬜ 미착수

---

## 1. 웹 UI (질문 입력 인터페이스)

| 요구 | 충족 위치 | 상태 |
|---|---|---|
| 질문 입력 페이지 존재 | `app/templates/index.html`, `app/routers/pages.py` | 🔵 B |
| 같은 화면에서 응답 확인 | `index.html` 의 fetch → `#log` 에 append | 🔵 B |
| 로딩 표시 | — | ⬜ **B** |
| 오류 메시지 표시 | — | ⬜ **B** |

현재 화면은 파이프라인 확인용 최소본이다. **응답이 4~8초 걸리므로 로딩 표시가 없으면 먹통처럼 보인다.**

---

## 2. 사용자 인증 및 접근 제어

| 요구 | 충족 위치 | 상태 |
|---|---|---|
| 회원가입 | `app/routers/auth.py` — `NotImplementedError` | ⬜ **B** |
| 로그인 | `app/routers/auth.py` — `NotImplementedError` | ⬜ **B** |
| 비밀번호 해싱 | `app/security.py` (`hash_password` / `verify_password`) | ✅ |
| 인증 상태별 접근 구분 | `app/deps.py::get_current_user` | ✅ |
| **챗봇은 로그인 사용자만** | `chat.py` 의 `Depends(get_current_user)` | ✅ |
| 화면은 `/login` 리다이렉트, API 는 401 | `app/main.py::auth_redirect` | ✅ |

**증명**: `tests/test_api.py::test_chat_requires_login`, `test_pages.py` (리다이렉트/401 분기)

> ⚠️ `DEV_AUTH_BYPASS` 는 개발 편의용 우회다. **배포 환경에서는 반드시 `false`** 여야 하고,
> B 가 인증을 완성하면 `deps.py` 에서 블록째 삭제한다.

---

## 3. AI 챗봇 처리

| 요구 | 충족 위치 | 상태 |
|---|---|---|
| 서버가 질문 수신 → AI 호출 | `app/routers/chat.py::chat` | ✅ |
| **AI 호출은 서버에서만** (키 비노출) | `app/services/ai.py` — 키는 `.env` 에만 | ✅ |
| 문맥 유지 전략 | `app/services/context.py::build_messages` | ✅ |

**전략**: 시스템 프롬프트(상황 배역 + 학습 목표) + **같은 세션의 최근 N턴**(`AI_MAX_CONTEXT_TURNS`, 기본 5) + 이번 발화.
세션 단위로 끊는 이유는 상황이 바뀌면 앞 대화가 방해가 되기 때문이고, 전체 히스토리를 넣지 않는 이유는 토큰 한도 때문이다.

**증명**: `tests/test_context.py` — 최근 N턴만 전송, 실패한 턴은 문맥에서 제외, 상황별 배역·목표 주입

---

## 4. 대화 로그 저장 및 조회/추적

| 요구 | 충족 위치 | 상태 |
|---|---|---|
| 질문·응답 누적 저장 | `app/models.py::ChatLog` | ✅ |
| 최소 필드(사용자·시각·질문·응답) | `user_id`, `created_at`, `question`, `answer` | ✅ |
| 사용자 기준 조회 | `GET /api/me/chats`, `/sessions`, `/corrections`, `/stats` | ✅ |
| 조회 **화면** | `GET /history`, `GET /corrections` | ✅ |
| 확인용 스크립트 | `scripts/check_logs.sql`, `scripts/check_logs.py` | ✅ |
| 관리자 운영 로그 | `GET /api/admin/logs` | ✅ A |

**증명**: `tests/test_logs.py`, `test_corrections.py` — 집계 정확도와 **남의 기록이 섞이지 않는지**를 고정

---

## 5. 운영 및 유지보수

| 요구 | 충족 위치 | 상태 |
|---|---|---|
| 요청 수신 로그 | `app/main.py::log_requests` (`request_received`) | ✅ |
| AI 호출/응답/실패 로그 | `ai.py` (`ai_call_start` / `_success` / `_failed`) | ✅ |
| DB 저장 성공·실패 로그 | `chat.py::_save` (`db_save_success` / `_failed`) | ✅ |
| 로그 파일 + 로테이션 | `app/logging_config.py` (5MB × 5) | ✅ A |
| **실패 시 비정상 종료 방지** | `ai.py` 가 모든 예외를 `AIError` 로 흡수 | ✅ |
| **사용자에게 오류 안내** | 503 + `{"error", "message"}` | ✅ |
| 입력 검증 | `app/schemas.py::ChatRequest` | ✅ |

**타임아웃 정책**: 주 모델이 5xx·연결 실패면 보조 모델로 한 번 더 시도하되, **타임아웃에는 폴백하지 않는다.**
이미 기다린 사용자를 또 기다리게 하면 체감이 두 배로 나빠지므로 즉시 안내로 돌린다.

**입력 검증 4종**: 빈 입력 / 길이 초과 / 제어 문자 / 세션 번호 양수

**증명**: `tests/test_ai_failures.py` (15개), `test_validation.py` (12개)
— 실패해도 **500 이 아니라 503**, 실패한 턴도 `error_code` 와 함께 저장되어 추적 가능

---

## 6. 배포 및 접근성

| 요구 | 충족 위치 | 상태 |
|---|---|---|
| 외부 접속 가능한 URL | `https://cody-chatbot.koreacentral.cloudapp.azure.com` | ✅ |
| HTTPS | Let's Encrypt (A) | ✅ A |
| 배포·실행 방법 문서 | `README.md`, `deploy/README.md` | ✅ A |
| 환경 변수 설정 방법 | `README.md`, `.env.example` | ✅ |

**자동 배포**: `develop` 머지 시 GitHub Actions 가 서버에 반영 (`.github/workflows/deploy.yml`)

---

## 7. 협업 및 형상관리

| 요구 | 현황 | 상태 |
|---|---|---|
| 브랜치 전략 | `main` / `develop` / `feat/*` | ✅ |
| 기능 단위 작업 브랜치 | PR 기준 브랜치 분리 | ✅ |
| PR 기반 Merge 기록 | 다수 | ✅ |
| **팀원별 유의미한 커밋 10회+** | A ✅ · **B ⬜** · C ✅ | 🔵 |
| 문서의 역할·작업 요약 | `README.md` 15절 | 🔵 |

> `README.md` 의 **개인별 작업 요약**은 커밋이 모두 쌓인 뒤 Git 이력 기준으로 채운다.
> 요건에 *"Git 이력과 크게 모순되지 않아야 한다"* 가 있으므로, 실제 커밋과 맞추는 것이 중요하다.

---

## 남은 것

| 순위 | 항목 | 담당 |
|---|---|---|
| 1 | **회원가입·로그인** — 요건 2 전체가 여기에 걸려 있다 | **B** |
| 2 | 로딩 표시·오류 메시지 — 없으면 시연에서 먹통으로 보인다 | **B** |
| 3 | 관리자 권한 판정 — 아이디가 `admin` 이면 누구나 관리자가 된다 | A |
| 4 | README 개인별 작업 요약 | 전원 |
| 5 | 시연 리허설 | 전원 |

---

## 제출 직전 점검

- [ ] 서버 `.env` 의 `DEV_AUTH_BYPASS` 가 **`false`**
- [ ] VM 자동 종료 **해제**
- [ ] `https://.../health` 응답 확인
- [ ] 인증서 만료일이 평가일 이후인지
- [ ] AI API 키 만료일이 평가일 이후인지
- [ ] `python scripts/check_logs.py` 로 대화 기록이 보이는지
- [ ] README 개인별 작업 요약이 Git 이력과 일치하는지

---

## 시연 순서 (권장)

1. **회원가입 → 로그인** — 요건 2
2. 로그아웃 상태로 `/history` 접근 → `/login` 으로 튕김 — 접근 제어
3. 상황 선택 후 영어로 대화 — 요건 1·3
4. 어색한 표현 입력 → **한국어 교정** 확인
5. `"What did I just order?"` → **직전 대화를 기억** — 문맥 유지
6. `/history` → 세션 목록 → **이어하기** — 요건 4
7. `/corrections` → 상황별 교정 통계
8. `AI_TIMEOUT=0.001` 로 재시도 → **오류 안내 확인** (서버가 죽지 않음) — 요건 5
9. `python scripts/check_logs.py` → DB 에 쌓인 기록 확인
