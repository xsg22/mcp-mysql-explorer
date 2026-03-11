import argparse
import json
import os

import pymysql
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()


def _parse_bool(value: str | bool | None, *, default: bool) -> bool:
    """Parse a truthy/falsy value from args/env with a fallback default."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    normalized = value.strip().lower()
    truthy = {"1", "true", "yes", "y", "on"}
    falsy = {"0", "false", "no", "n", "off"}
    if normalized in truthy:
        return True
    if normalized in falsy:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def _parse_args():
    parser = argparse.ArgumentParser(description="MCP MySQL Server")
    parser.add_argument("--host", help="MySQL host")
    parser.add_argument("--port", type=int, help="MySQL port")
    parser.add_argument("--user", help="MySQL user")
    parser.add_argument("--password", help="MySQL password")
    parser.add_argument("--database", help="MySQL database name")
    parser.add_argument(
        "--read-only",
        dest="read_only",
        help="Enable or disable read-only mode (true/false). Default: true",
    )
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Shortcut for --read-only false.",
    )
    return parser.parse_args()


_args = _parse_args()
READ_ONLY_MODE = (
    False
    if _args.allow_write
    else _parse_bool(
        _args.read_only,
        default=_parse_bool(os.getenv("MYSQL_READ_ONLY"), default=True),
    )
)

MYSQL_CONFIG = {
    "host": _args.host or os.getenv("MYSQL_HOST", "localhost"),
    "port": _args.port or int(os.getenv("MYSQL_PORT", "3306")),
    "user": _args.user or os.getenv("MYSQL_USER", "root"),
    "password": _args.password or os.getenv("MYSQL_PASSWORD", ""),
    "database": _args.database or os.getenv("MYSQL_DATABASE", ""),
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "connect_timeout": 10,
}

MAX_ROWS = 1000

mcp = FastMCP(
    "MySQL Explorer",
    instructions=(
        "MCP server for MySQL. Supports schema exploration and SQL execution. "
        f"Current mode: {'read-only' if READ_ONLY_MODE else 'read-write'}."
    ),
)


def _get_connection():
    return pymysql.connect(**MYSQL_CONFIG)


def _format_rows(rows: list[dict], max_rows: int = MAX_ROWS) -> str:
    if not rows:
        return "No results."
    truncated = rows[:max_rows]
    result = json.dumps(truncated, default=str, ensure_ascii=False, indent=2)
    if len(rows) > max_rows:
        result += f"\n\n... truncated, showing {max_rows} of {len(rows)} rows"
    return result


@mcp.tool()
def list_tables() -> str:
    """List all tables in the connected MySQL database."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in cur.fetchall()]
        return json.dumps(tables, ensure_ascii=False, indent=2)
    finally:
        conn.close()


@mcp.tool()
def describe_table(table_name: str) -> str:
    """Get the schema (columns, types, keys) of a specific table.

    Args:
        table_name: Name of the table to describe.
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DESCRIBE %s" % _safe_identifier(table_name))
            columns = cur.fetchall()

            cur.execute(
                "SELECT TABLE_COMMENT FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (MYSQL_CONFIG["database"], table_name),
            )
            table_info = cur.fetchone()
            table_comment = table_info["TABLE_COMMENT"] if table_info else ""

            cur.execute(
                "SELECT COLUMN_NAME, COLUMN_COMMENT FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (MYSQL_CONFIG["database"], table_name),
            )
            col_comments = {r["COLUMN_NAME"]: r["COLUMN_COMMENT"] for r in cur.fetchall()}

        for col in columns:
            col["Comment"] = col_comments.get(col["Field"], "")

        result = {"table": table_name, "comment": table_comment, "columns": columns}
        return json.dumps(result, default=str, ensure_ascii=False, indent=2)
    finally:
        conn.close()


@mcp.tool()
def query(sql: str) -> str:
    """Execute a read-only SQL query (SELECT / SHOW / DESCRIBE / EXPLAIN).

    Only SELECT, SHOW, DESCRIBE, and EXPLAIN statements are allowed.

    Args:
        sql: The SQL query to execute.
    """
    normalized = sql.strip().upper()
    allowed_prefixes = ("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN")
    if not any(normalized.startswith(p) for p in allowed_prefixes):
        if READ_ONLY_MODE:
            return "Error: Read-only mode is enabled. Only SELECT / SHOW / DESCRIBE / EXPLAIN queries are allowed."
        return "Error: Only SELECT / SHOW / DESCRIBE / EXPLAIN queries are allowed. Use execute_sql for write operations."

    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
        return _format_rows(rows)
    except Exception as e:
        return f"Query error: {e}"
    finally:
        conn.close()


@mcp.tool()
def execute_sql(sql: str) -> str:
    """Execute a write SQL statement (INSERT / UPDATE / DELETE / ALTER / CREATE / DROP, etc).

    Use with caution: this modifies the database.

    Args:
        sql: The SQL statement to execute.
    """
    if READ_ONLY_MODE:
        return (
            "Error: Server is running in read-only mode. "
            "Write SQL is disabled. Set MYSQL_READ_ONLY=false or pass --allow-write to enable writes."
        )

    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            affected = cur.execute(sql)
            conn.commit()

            if cur.description:
                rows = cur.fetchall()
                return _format_rows(rows)

        return f"OK - {affected} row(s) affected."
    except Exception as e:
        conn.rollback()
        return f"Execution error: {e}"
    finally:
        conn.close()


@mcp.tool()
def get_table_indexes(table_name: str) -> str:
    """Show all indexes of a specific table.

    Args:
        table_name: Name of the table.
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW INDEX FROM %s" % _safe_identifier(table_name))
            indexes = cur.fetchall()
        return json.dumps(indexes, default=str, ensure_ascii=False, indent=2)
    finally:
        conn.close()


@mcp.tool()
def get_create_table(table_name: str) -> str:
    """Get the CREATE TABLE statement of a specific table.

    Args:
        table_name: Name of the table.
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW CREATE TABLE %s" % _safe_identifier(table_name))
            result = cur.fetchone()
        return result.get("Create Table", str(result)) if result else "Table not found."
    finally:
        conn.close()


@mcp.tool()
def get_database_info() -> str:
    """Get overview information about the connected database, including size, table count, and charset."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            db = MYSQL_CONFIG["database"]
            cur.execute(
                "SELECT COUNT(*) as table_count FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s",
                (db,),
            )
            table_count = cur.fetchone()["table_count"]

            cur.execute(
                "SELECT ROUND(SUM(DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024, 2) AS size_mb "
                "FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s",
                (db,),
            )
            size = cur.fetchone()["size_mb"]

            cur.execute("SELECT VERSION() AS version")
            version = cur.fetchone()["version"]

        info = {
            "database": db,
            "mysql_version": version,
            "table_count": table_count,
            "size_mb": float(size) if size else 0,
        }
        return json.dumps(info, ensure_ascii=False, indent=2)
    finally:
        conn.close()


def _safe_identifier(name: str) -> str:
    """Backtick-wrap a table/column name to prevent SQL injection in identifiers."""
    if "`" in name:
        raise ValueError(f"Invalid identifier: {name}")
    return f"`{name}`"


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
