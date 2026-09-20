"""대화 로그 확인 스크립트.

check_logs.sql 과 같은 내용을 보여주되, sqlite3 명령줄 도구가 없어도 돌아간다.
Windows 에는 sqlite3 가 기본 설치돼 있지 않아서, SQL 파일만 두면
"명령을 찾을 수 없습니다" 에서 막힌다.

    python scripts/check_logs.py
    python scripts/check_logs.py --db data/chatbot.db --limit 30
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def _rows(cur: sqlite3.Cursor, sql: str, *params) -> tuple[list[str], list[tuple]]:
    cur.execute(sql, params)
    headers = [d[0] for d in cur.description]
    return headers, cur.fetchall()


def _print_table(title: str, headers: list[str], rows: list[tuple]) -> None:
    print(f"\n=== {title} ===")
    if not rows:
        print("  (없음)")
        return

    cells = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [
        min(42, max(len(h), *(len(r[i]) for r in cells)))
        for i, h in enumerate(headers)
    ]

    def line(values: list[str]) -> str:
        return "  ".join(
            v[: widths[i]].ljust(widths[i]) for i, v in enumerate(values)
        )

    print("  " + line(headers))
    print("  " + "  ".join("-" * w for w in widths))
    for row in cells:
        print("  " + line(row))


def main() -> int:
    parser = argparse.ArgumentParser(description="대화 로그 확인")
    parser.add_argument("--db", default="data/chatbot.db", help="SQLite 파일 경로")
    parser.add_argument("--limit", type=int, default=20, help="목록에 보여줄 건수")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB 파일이 없습니다: {db_path}", file=sys.stderr)
        print("서버를 한 번 실행하면 생성됩니다.", file=sys.stderr)
        return 1

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    print(f"DB: {db_path.resolve()}")

    _print_table(
        "1. 사용자",
        *_rows(cur, "SELECT id, username, created_at FROM users ORDER BY id"),
    )

    _print_table(
        "2. 세션",
        *_rows(
            cur,
            """
            SELECT s.id, u.username, s.scenario,
                   COUNT(c.id)         AS turns,
                   COUNT(c.correction) AS corrections,
                   s.created_at
            FROM roleplay_sessions s
            JOIN users u          ON u.id = s.user_id
            LEFT JOIN chat_logs c ON c.session_id = s.id
            GROUP BY s.id ORDER BY s.id DESC LIMIT ?
            """,
            args.limit,
        ),
    )

    _print_table(
        f"3. 최근 대화 {args.limit}건",
        *_rows(
            cur,
            """
            SELECT c.id, u.username, c.session_id, s.scenario,
                   substr(c.question, 1, 40) AS question,
                   substr(c.answer,   1, 40) AS answer,
                   c.error_code, c.latency_ms, c.created_at
            FROM chat_logs c
            JOIN users u             ON u.id = c.user_id
            JOIN roleplay_sessions s ON s.id = c.session_id
            ORDER BY c.id DESC LIMIT ?
            """,
            args.limit,
        ),
    )

    _print_table(
        "4. 받은 교정",
        *_rows(
            cur,
            """
            SELECT s.scenario,
                   substr(c.question,   1, 35) AS said,
                   substr(c.correction, 1, 60) AS correction,
                   c.created_at
            FROM chat_logs c
            JOIN roleplay_sessions s ON s.id = c.session_id
            WHERE c.correction IS NOT NULL
            ORDER BY c.id DESC LIMIT ?
            """,
            args.limit,
        ),
    )

    _print_table(
        "5. 사용자별 누적",
        *_rows(
            cur,
            """
            SELECT u.username,
                   COUNT(*)                      AS turns,
                   COUNT(c.correction)           AS corrections,
                   SUM(c.error_code IS NOT NULL) AS errors,
                   ROUND(AVG(c.latency_ms), 0)   AS avg_latency_ms
            FROM chat_logs c
            JOIN users u ON u.id = c.user_id
            GROUP BY u.id ORDER BY turns DESC
            """,
        ),
    )

    _print_table(
        "6. 실패한 호출 (원인 추적)",
        *_rows(
            cur,
            """
            SELECT c.id, u.username, c.error_code,
                   substr(c.question, 1, 40) AS question,
                   c.created_at
            FROM chat_logs c
            JOIN users u ON u.id = c.user_id
            WHERE c.error_code IS NOT NULL
            ORDER BY c.id DESC LIMIT ?
            """,
            args.limit,
        ),
    )

    conn.close()
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
