# 트랙별 작업 인수인계

> 이 문서는 각자 **독립적으로** 작업을 시작할 수 있게 만드는 것이 목적이다.
> 공용 계약(스키마·API·의존성 시그니처)은 이미 코드에 박혀 있으니,
> 아래 체크리스트만 자기 것부터 채우면 서로 기다릴 일이 없다.

## 서비스 개요

**영어 회화 롤플레이 파트너.** 사용자가 상황(카페·공항·쇼핑 등)을 고르면
AI가 상대역을 연기하고, 어색한 표현이 나오면 한국어로 교정해 준다.

- 로그인이 필요한 이유 → 교정 기록과 연습 이력이 개인 자산이기 때문
- 문맥이 필요한 이유 → 롤플레이는 직전 대사에 이어져야 성립하기 때문
- 로그를 쌓는 이유 → "내가 자주 틀리는 표현" 화면의 데이터가 되기 때문

## 이미 정해진 계약 (건드리지 말 것)

| 대상 | 위치 | 비고 |
|---|---|---|
| DB 스키마 | `app/models.py` | `users` / `roleplay_sessions` / `chat_logs`. 필드 추가는 A에게 요청 |
| 요청·응답 | `app/schemas.py` | 이 파일이 API 명세의 원본 |
| 인증 진입점 | `app/deps.py` 의 `get_current_user` | **시그니처와 반환 타입(User) 고정.** B는 내부만 교체 |
| 에러 코드 | `AI_TIMEOUT` / `AI_ERROR` / `INTERNAL_ERROR` | 실패 응답은 `{"error", "message"}` 형태, HTTP 503 |

## 지금 바로 돌려보는 법

**Python 3.12 필요** (3.9 에서는 의존성 빌드가 실패한다).
Git Bash 에서 — CMD 는 `cp`·`./` 문법이 달라 아래 명령이 안 먹는다.

```bash
py -3.12 -m venv .venv          # mac: python3.12 -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env          # AI_MOCK=true, DEV_AUTH_BYPASS=true 상태로 시작
python -c "import secrets; print(secrets.token_hex(32))"   # SESSION_SECRET_KEY 에 붙여넣기
uvicorn app.main:app --reload
```

`AI_MOCK=true` 면 **API 키 없이도** 전체 흐름이 돈다. A와 B는 이 상태로 개발하면
C의 월 토큰 한도를 쓰지 않는다.

---

## 트랙 A — 인프라 · DB · 배포

가장 먼저 끝나야 하는 것은 **고정 IP**다. 이게 없으면 C가 운영 키를 못 만든다.

- [ ] 클라우드 VM(Ubuntu) 생성
- [ ] **고정 공인 IP 예약 → C에게 전달** ★ C를 막고 있음
- [ ] 보안그룹 **그리고** OS 방화벽(ufw) 양쪽에서 80/443 개방
- [ ] 서버에 Python 3.12 + venv + 코드 배포
- [ ] systemd 서비스로 uvicorn 상주
- [ ] nginx 리버스 프록시
- [ ] HTTPS (도메인이 없으면 생략 가능, 대신 http 접속 URL 확보)
- [ ] **기능이 "Hello World" 수준일 때 한 번 배포해 볼 것** — 막판에 하면 못 고침
- [ ] `app/logging_config.py` 의 `TODO(A)`: 파일 핸들러(로테이션) 추가
- [ ] SQLite 파일 경로·권한 정리, 백업 스크립트
- [ ] ERD 작성 (`app/models.py` 기준)
- [ ] README 의 "배포·실행 방법", "환경 변수" 섹션

## 트랙 B — 인증 · 웹 UI

`app/routers/auth.py`, `app/routers/pages.py`, `app/templates/`, `app/static/` 전부 B 소유.

- [x] ~~`app/security.py` — 해싱/검증~~ (완료: `hash_password` / `verify_password`)
      passlib 은 bcrypt 5.x 와 호환되지 않아 제거했다. bcrypt 를 직접 쓴다.
- [ ] `auth.py` 회원가입 — 아이디 중복 검사, 비밀번호 길이 제한
- [ ] `auth.py` 로그인 — 성공 시 `request.session["user_id"] = user.id`
- [ ] `login_success` / `login_failed` 로그 남기기
- [ ] **`app/deps.py` 의 `DEV_AUTH_BYPASS` 블록 삭제** ★ 인증 완료 신호
- [ ] `pages.py` — 비로그인으로 `/` 접근 시 `/login` 리다이렉트
- [ ] `templates/login.html` — 로그인·회원가입 폼
- [ ] `templates/index.html` — 채팅 화면 제대로 만들기 (현재는 동작 확인용 최소본)
- [ ] 503 응답의 `message` 를 사용자에게 보여주는 에러 UI
- [ ] 전송 중 로딩 표시

## 트랙 C — AI 파이프라인 · 운영

- [x] ~~개발용 API 키 발급~~ (OpenAI 호환 방식으로 발급 완료)
- [x] ~~Base URL 확인~~ → `https://copa.codyssey.kr/v1`
- [x] ~~모델 확정~~ → 주 `gemini-3-flash` / 폴백 `gpt-5-mini`
- [x] ~~규격 확인~~ — claude-* 는 OpenAI 키로 불가, gpt-5* 는 temperature 고정
- [x] ~~실제 연동 검증~~ (왕복 2턴 + DB 저장 확인)
- [x] ~~JSON 형식 확인~~ — gemini-3-flash 는 규칙을 지킨다
- [ ] **운영용 키 발급** (A의 고정 IP 받은 뒤, 그 IP만 허용) ★ A 의존
- [ ] 타임아웃 강제 재현 (`AI_TIMEOUT=0.001`) → 503 + `AI_TIMEOUT` 확인
- [x] ~~컨텍스트 검증~~ — "What did I just order?" 에 직전 주문을 기억함
- [ ] 시스템 프롬프트 튜닝 (`services/context.py`)
- [ ] README 의 "API 명세", "DB 확인 가이드" 섹션

---

## 외부 준비물 (코딩으로 해결 안 되는 것)

| 항목 | 담당 | 지금 해야 하는 이유 |
|---|---|---|
| 클라우드 계정·VM | A | 계정 승인에 하루 이틀 걸릴 수 있음 |
| 고정 공인 IP | A | 없으면 재부팅 때 IP가 바뀌어 평가 당일 API가 죽음 |
| 개발용 API 키 | C | 없으면 실제 연동 검증을 못 함 |
| 운영용 API 키 | C | A의 IP가 나온 뒤에야 발급 가능 |
| 키 만료일 | C | 평가일 이전 만료 = 복구 불가 |

**키 값은 최초 1회만 표시된다.** 발급 즉시 안전한 곳에 복사할 것.
`.env` 는 `.gitignore` 대상이라 레포에 올라가지 않는다 — 팀원 간 공유는 개별 전달.
