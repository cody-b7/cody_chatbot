-- 평가자/팀원이 DB를 직접 확인할 때 쓰는 쿼리
--   sqlite3 data/chatbot.db < scripts/check_logs.sql

.headers on
.mode column

SELECT '--- 사용자 ---' AS "";
SELECT id, username, created_at FROM users ORDER BY id;

SELECT '--- 최근 대화 20건 ---' AS "";
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

SELECT '--- 사용자별 누적 ---' AS "";
SELECT u.username,
       COUNT(*)                                   AS turns,
       SUM(c.error_code IS NOT NULL)              AS errors,
       SUM(c.correction IS NOT NULL)              AS corrections,
       ROUND(AVG(c.latency_ms), 0)                AS avg_latency_ms
FROM chat_logs c JOIN users u ON u.id = c.user_id
GROUP BY u.id ORDER BY turns DESC;
