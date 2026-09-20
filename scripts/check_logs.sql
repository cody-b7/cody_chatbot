-- 대화 로그 확인용 쿼리 (평가자·팀원이 DB를 직접 들여다볼 때)
--
--   sqlite3 data/chatbot.db < scripts/check_logs.sql
--
-- sqlite3 명령이 없는 환경(특히 Windows)에서는 같은 내용을 돌려주는
-- 파이썬 스크립트를 쓰면 된다:
--
--   python scripts/check_logs.py

.headers on
.mode column
.width 4 12 6 10 40 40 10 8 20

SELECT '=== 1. 사용자 ===' AS "";
SELECT id, username, created_at FROM users ORDER BY id;

SELECT '=== 2. 세션 ===' AS "";
SELECT s.id,
       u.username,
       s.scenario,
       COUNT(c.id)                   AS turns,
       COUNT(c.correction)           AS corrections,
       s.created_at
FROM roleplay_sessions s
JOIN users u          ON u.id = s.user_id
LEFT JOIN chat_logs c ON c.session_id = s.id
GROUP BY s.id
ORDER BY s.id DESC
LIMIT 20;

SELECT '=== 3. 최근 대화 20건 ===' AS "";
SELECT c.id,
       u.username,
       c.session_id,
       s.scenario,
       substr(c.question, 1, 40) AS question,
       substr(c.answer,   1, 40) AS answer,
       c.error_code,
       c.latency_ms,
       c.created_at
FROM chat_logs c
JOIN users u             ON u.id = c.user_id
JOIN roleplay_sessions s ON s.id = c.session_id
ORDER BY c.id DESC
LIMIT 20;

SELECT '=== 4. 받은 교정 (최근 10건) ===' AS "";
SELECT s.scenario,
       substr(c.question,   1, 35) AS said,
       substr(c.correction, 1, 60) AS correction,
       c.created_at
FROM chat_logs c
JOIN roleplay_sessions s ON s.id = c.session_id
WHERE c.correction IS NOT NULL
ORDER BY c.id DESC
LIMIT 10;

SELECT '=== 5. 사용자별 누적 ===' AS "";
SELECT u.username,
       COUNT(*)                      AS turns,
       COUNT(c.correction)           AS corrections,
       SUM(c.error_code IS NOT NULL) AS errors,
       ROUND(AVG(c.latency_ms), 0)   AS avg_latency_ms
FROM chat_logs c
JOIN users u ON u.id = c.user_id
GROUP BY u.id
ORDER BY turns DESC;

SELECT '=== 6. 실패한 호출 (원인 추적) ===' AS "";
SELECT c.id,
       u.username,
       c.error_code,
       substr(c.question, 1, 40) AS question,
       c.created_at
FROM chat_logs c
JOIN users u ON u.id = c.user_id
WHERE c.error_code IS NOT NULL
ORDER BY c.id DESC
LIMIT 10;
