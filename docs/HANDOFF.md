# 트랙별 작업 인수인계

> 이 문서는 프로젝트의 최종 구현 상태와 담당 범위를 정리한다.  
> 프로젝트는 초기 A/B/C 3인 체제로 시작했으나 진행 중 B가 이탈하여, 남은 인증 및 화면 작업을 A와 C가 분담했다.  
> 아래 역할은 최종 구현 내용과 Git 작업 이력을 기준으로 정리한다.

## 서비스 개요

**영어 회화 롤플레이 파트너 Cody**

사용자가 카페·공항·쇼핑 등의 상황을 선택하면 AI가 해당 상황의 상대역을 연기하고, 어색한 영어 표현이 나오면 한국어 교정을 함께 제공한다.

- 로그인이 필요한 이유 → 교정 기록과 연습 이력을 사용자별로 저장하기 위해
- 문맥이 필요한 이유 → 롤플레이가 직전 대화에 이어져야 자연스럽게 진행되기 때문에
- 로그를 저장하는 이유 → 사용자별 대화·교정 기록 및 학습 통계를 제공하기 위해

---

## 공용 계약

| 대상 | 위치 | 설명 |
|---|---|---|
| DB 스키마 | `app/models.py` | `users`, `roleplay_sessions`, `chat_logs` |
| 요청·응답 스키마 | `app/schemas.py` | 챗 API 요청·응답 및 입력 검증 |
| 사용자 인증 | `app/deps.py`의 `get_current_user` | 세션의 `user_id`를 기준으로 로그인 사용자 확인 |
| 관리자 인증 | `app/deps.py`의 `get_admin_user` | `users.is_admin` 값을 기준으로 관리자 확인 |
| AI 오류 코드 | `AI_TIMEOUT`, `AI_ERROR`, `INTERNAL_ERROR` | AI 실패 응답에 사용 |
| DB | SQLite | 기본 경로 `data/chatbot.db` |
| 운영 서버 | Azure Ubuntu VM | Nginx + Uvicorn + systemd 구성 |

---

## 로컬 실행 방법

Python 3.12 이상을 사용한다.

### 가상환경 생성

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\activate
```

Linux / macOS:

```bash
source .venv/bin/activate
```

### 패키지 설치

```bash
python -m pip install -r requirements.txt
```

### 환경변수 파일 생성

Linux / macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

`SESSION_SECRET_KEY`가 필요한 경우 다음과 같이 생성할 수 있다.

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

실제 AI API를 사용하지 않을 때는 다음과 같이 설정한다.

```env
AI_MOCK=true
```

### 서버 실행

```bash
uvicorn app.main:app --reload
```

로컬 접속 주소:

```text
http://127.0.0.1:8000
```

---

# 트랙 A — 인프라 · DB · 배포 · 인증

A는 프로젝트의 서버·DB·배포 환경과 인증 백엔드 및 관리자 권한 기능을 담당했다.

## 인프라 및 배포

- [x] Azure Ubuntu VM 구성
- [x] 운영 서버 고정 주소 확보
- [x] Python 3.12 및 가상환경 구성
- [x] Uvicorn 기반 FastAPI 실행
- [x] `cody.service` systemd 서비스 구성
- [x] Nginx 리버스 프록시 구성
- [x] HTTP → HTTPS 리다이렉트 구성
- [x] Let's Encrypt / Certbot HTTPS 적용
- [x] Certbot 자동 갱신 확인
- [x] GitHub Actions 기반 `develop` 자동 배포 구성
- [x] GitHub Secrets 기반 SSH 배포 설정
- [x] 운영 서버 서비스 상태 확인 절차 구성

운영 서비스 주소:

```text
https://cody-chatbot.koreacentral.cloudapp.azure.com
```

운영 서버 프로젝트 경로:

```text
/home/azureuser/cody_chatbot
```

서비스 상태 확인:

```bash
sudo systemctl status cody.service --no-pager
```

---

## DB

- [x] SQLAlchemy 기반 DB 연결 구성
- [x] SQLite WAL 모드 적용
- [x] Foreign Key 활성화
- [x] `users` 모델 구성
- [x] `roleplay_sessions` 모델 구성
- [x] `chat_logs` 모델 구성
- [x] `users.is_admin` 관리자 필드 추가
- [x] 기존 운영 DB용 `is_admin` migration 작성
- [x] GitHub Actions 배포 과정에 migration 단계 추가
- [x] DB 백업 스크립트 작성
- [x] DB 복구 스크립트 작성
- [x] 복구 전 안전 백업 생성
- [x] ERD 문서화

기존 운영 DB migration:

```bash
./.venv/bin/python scripts/migrate_add_is_admin.py
```

해당 스크립트는 `is_admin` 컬럼이 이미 존재하면 다시 추가하지 않는다.

---

## 인증

- [x] bcrypt 기반 비밀번호 해싱
- [x] 비밀번호 검증
- [x] 회원가입
- [x] 사용자명 중복 검사
- [x] 빈 사용자명 검증
- [x] 빈 비밀번호 및 bcrypt 최대 바이트 제한 검증
- [x] 로그인
- [x] 로그인 성공 시 `request.session["user_id"]` 저장
- [x] 로그아웃
- [x] 로그인 성공·실패 로그 기록
- [x] 로그아웃 로그 기록
- [x] 비로그인 사용자의 `/` 접근 차단
- [x] 로그인·회원가입 화면 연결
- [x] 개발용 인증 우회 기능 제거
- [x] `admin` 예약 사용자명 일반 회원가입 차단

예약 사용자명은 대소문자와 관계없이 차단한다.

예:

```text
admin
Admin
ADMIN
```

---

## 관리자 권한

관리자 여부는 사용자명이 아니라 `users.is_admin` 필드를 기준으로 판단한다.

일반 회원가입으로 생성된 사용자는 기본적으로:

```text
is_admin = false
```

상태이다.

관리자 권한 부여:

```bash
./.venv/bin/python -m scripts.set_admin <username> true
```

예:

```bash
./.venv/bin/python -m scripts.set_admin codyadmin true
```

관리자 권한 해제:

```bash
./.venv/bin/python -m scripts.set_admin <username> false
```

관리자 운영 로그 API:

```text
GET /api/admin/logs
```

접근 권한:

```text
비로그인 사용자 → 401
일반 사용자     → 403
관리자          → 200
```

운영 환경에서 `codyadmin` 계정에 관리자 권한을 부여하고 `/api/admin/logs` 접근까지 확인했다.

---

## 운영 로그

- [x] 콘솔 로그
- [x] `logs/app.log` 파일 로그
- [x] `RotatingFileHandler` 적용
- [x] 로그 최대 크기 5 MB
- [x] 백업 로그 최대 5개
- [x] 관리자용 최근 로그 조회 API 구현

로그 파일:

```text
logs/app.log
```

---

# 트랙 C — AI 파이프라인 · 대화 기능 · 운영

C는 사용자 질문부터 AI 응답, 문맥 유지, 대화 저장 및 학습 기록 조회까지의 핵심 AI 파이프라인을 담당했다.

## AI 연동

- [x] 코디세이 AI Gateway 연동
- [x] OpenAI 호환 `/v1/chat/completions` 방식 사용
- [x] 개발용 API Key 검증
- [x] Base URL 확인
- [x] 사용 가능 모델 확인
- [x] 주 모델 `gemini-3-flash` 적용
- [x] 폴백 모델 `gpt-5-mini` 적용
- [x] 공급사별 모델 제약 확인
- [x] AI 응답 JSON 형식 검증
- [x] 실제 왕복 대화 검증
- [x] DB 저장 확인

Base URL:

```text
https://copa.codyssey.kr/v1
```

모델:

```text
Primary  : gemini-3-flash
Fallback : gpt-5-mini
```

주 모델에서 5xx 또는 연결 실패가 발생하면 폴백 모델을 사용한다.

타임아웃 발생 시에는 추가 폴백을 수행하지 않고 `AI_TIMEOUT`을 반환한다.

---

## 대화 문맥

- [x] 동일 세션의 최근 대화 문맥 유지
- [x] 롤플레이 세션 단위 문맥 분리
- [x] `session_id` 기반 이어하기
- [x] 이전 세션 상세 조회
- [x] 대화 이어하기 기능 구현

카페 대화 후 새로운 공항 세션을 만들 경우 기존 카페 대화가 새 문맥에 섞이지 않도록 세션을 분리한다.

---

## 사용자 기록

- [x] 사용자 질문 저장
- [x] AI 응답 저장
- [x] 교정 내용 저장
- [x] 사용 모델 저장
- [x] 응답 시간 저장
- [x] 오류 코드 저장
- [x] 사용자별 대화 기록 조회
- [x] 교정 기록 조회
- [x] 상황별 교정 통계
- [x] 세션 목록 조회
- [x] 세션 상세 조회
- [x] 학습 통계 조회

주요 API:

```text
GET /api/me/chats
GET /api/me/corrections
GET /api/me/corrections/by-scenario
GET /api/me/sessions
GET /api/me/sessions/{session_id}
GET /api/me/stats
```

모든 사용자 기록은 로그인한 사용자의 ID를 기준으로 제한한다.

---

## 오류 처리

AI 호출 관련 오류 코드는 다음과 같다.

| 코드 | 의미 |
|---|---|
| `AI_TIMEOUT` | AI Gateway 응답 시간 초과 |
| `AI_ERROR` | AI 호출 실패 또는 유효하지 않은 응답 |
| `INTERNAL_ERROR` | 기타 서버 내부 오류 |

AI 호출 오류 시 서버 프로세스를 종료하지 않고 사용자에게 안내 메시지를 반환한다.

---

# 화면 및 인증 작업 재분배

프로젝트 초기에는 B가 인증 및 웹 UI 전체를 담당할 예정이었다.

진행 중 B가 이탈하여 남은 작업을 A와 C가 분담했다.

최종적으로 A가 담당한 인증 및 화면 관련 작업:

- 회원가입 백엔드
- 로그인 백엔드
- 로그아웃 백엔드
- 세션 기반 접근 제어
- 로그인·회원가입 화면 연결
- 비로그인 메인 화면 접근 차단
- 인증 성공·실패 로그
- 관리자 권한 구조
- 관리자 예약 아이디 처리

C가 추가로 담당한 화면 작업이 있는 경우 최종 Git 이력 기준으로 역할을 추가 기록한다.

---

# 운영 준비 사항

| 항목 | 상태 |
|---|---|
| Azure VM | 완료 |
| 운영 URL | 완료 |
| HTTPS | 완료 |
| systemd 서비스 | 완료 |
| Nginx | 완료 |
| GitHub Actions 자동 배포 | 완료 |
| DB migration | 완료 |
| DB 백업·복구 | 완료 |
| 사용자 인증 | 완료 |
| 관리자 권한 | 완료 |
| 관리자 로그 API | 완료 |
| 운영 관리자 계정 | 완료 |
| AI Gateway 연동 | 완료 |
| 대화 로그 저장 | 완료 |
| 사용자 기록 조회 | 완료 |

---

# 최종 테스트

전체 테스트:

```bash
pytest -q
```

코드 스타일 검사:

```bash
ruff check .
```

로컬 서버:

```bash
uvicorn app.main:app --reload
```

확인할 주요 흐름:

```text
비로그인 /
→ /login

회원가입
→ 로그인 상태로 /
→ 챗봇 사용

로그아웃
→ /login

관리자
→ /api/admin/logs 접근 가능

일반 사용자
→ /api/admin/logs 접근 시 403
```

---

# 협업 규칙

브랜치:

```text
main
develop
feat/*
chore/*
docs/*
```

작업 흐름:

```text
Issue 생성
→ 작업 브랜치 생성
→ Commit / Push
→ Pull Request
→ 팀원 Review / Approve
→ CI 통과
→ develop Merge
```

- `main`, `develop`에 직접 Push하지 않는다.
- 모든 기능 변경은 Pull Request를 통해 반영한다.
- PR은 팀원 최소 1명의 승인을 받는다.
- CI 통과 후 Merge한다.
- 개인별 커밋 기록을 유지한다.