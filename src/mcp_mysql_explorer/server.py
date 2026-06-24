import argparse
import atexit
import json
import os
import threading

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
    parser.add_argument(
        "--ssh-enabled",
        help="Enable or disable SSH tunnel mode (true/false). Default: enabled when --ssh-host or MYSQL_SSH_HOST is set.",
    )
    parser.add_argument("--ssh-host", help="SSH bastion/jump host")
    parser.add_argument("--ssh-port", type=int, help="SSH port")
    parser.add_argument("--ssh-user", help="SSH user")
    parser.add_argument("--ssh-password", help="SSH password")
    parser.add_argument("--ssh-private-key", help="Path to SSH private key")
    parser.add_argument("--ssh-private-key-password", help="SSH private key passphrase")
    parser.add_argument("--ssh-local-host", help="Local host for SSH port forwarding")
    parser.add_argument("--ssh-local-port", type=int, help="Local port for SSH port forwarding")
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

_ssh_enabled_default = _parse_bool(
    os.getenv("MYSQL_SSH_ENABLED"),
    default=bool(os.getenv("MYSQL_SSH_HOST")),
)
if _args.ssh_host:
    _ssh_enabled_default = True

SSH_CONFIG = {
    "enabled": _parse_bool(_args.ssh_enabled, default=_ssh_enabled_default),
    "host": _args.ssh_host or os.getenv("MYSQL_SSH_HOST", ""),
    "port": _args.ssh_port or int(os.getenv("MYSQL_SSH_PORT", "22")),
    "user": _args.ssh_user or os.getenv("MYSQL_SSH_USER", ""),
    "password": _args.ssh_password or os.getenv("MYSQL_SSH_PASSWORD", ""),
    "private_key": _args.ssh_private_key or os.getenv("MYSQL_SSH_PRIVATE_KEY", ""),
    "private_key_password": _args.ssh_private_key_password
    or os.getenv("MYSQL_SSH_PRIVATE_KEY_PASSWORD", ""),
    "local_host": _args.ssh_local_host or os.getenv("MYSQL_SSH_LOCAL_HOST", "127.0.0.1"),
    "local_port": _args.ssh_local_port
    or int(os.getenv("MYSQL_SSH_LOCAL_PORT", "0")),
}

MAX_ROWS = 1000
_SSH_TUNNEL = None
_SSH_TUNNEL_LOCK = threading.Lock()

mcp = FastMCP(
    "MySQL Explorer",
    instructions=(
        "MCP server for MySQL. Supports schema exploration and SQL execution. "
        f"Current mode: {'read-only' if READ_ONLY_MODE else 'read-write'}."
    ),
)


def _get_ssh_tunnel_forwarder_class():
    try:
        from sshtunnel import SSHTunnelForwarder
    except ImportError as exc:
        raise RuntimeError(
            "SSH tunnel mode requires the 'sshtunnel' package. "
            "Install mcp-mysql-explorer with its latest dependencies."
        ) from exc
    return SSHTunnelForwarder


def _ensure_ssh_tunnel():
    global _SSH_TUNNEL
    if not SSH_CONFIG["enabled"]:
        return None

    with _SSH_TUNNEL_LOCK:
        if _SSH_TUNNEL and _SSH_TUNNEL.is_active:
            return _SSH_TUNNEL

        if not SSH_CONFIG["host"]:
            raise ValueError("SSH tunnel mode is enabled, but SSH host is not configured.")

        forwarder_cls = _get_ssh_tunnel_forwarder_class()
        credentials = {}
        if SSH_CONFIG["user"]:
            credentials["ssh_username"] = SSH_CONFIG["user"]
        if SSH_CONFIG["password"]:
            credentials["ssh_password"] = SSH_CONFIG["password"]
        if SSH_CONFIG["private_key"]:
            credentials["ssh_pkey"] = SSH_CONFIG["private_key"]
        if SSH_CONFIG["private_key_password"]:
            credentials["ssh_private_key_password"] = SSH_CONFIG["private_key_password"]

        tunnel = forwarder_cls(
            (SSH_CONFIG["host"], SSH_CONFIG["port"]),
            remote_bind_address=(MYSQL_CONFIG["host"], MYSQL_CONFIG["port"]),
            local_bind_address=(SSH_CONFIG["local_host"], SSH_CONFIG["local_port"]),
            **credentials,
        )
        tunnel.start()
        _SSH_TUNNEL = tunnel
        return _SSH_TUNNEL


def _close_ssh_tunnel():
    global _SSH_TUNNEL
    if _SSH_TUNNEL:
        _SSH_TUNNEL.stop()
        _SSH_TUNNEL = None


def _get_connection():
    tunnel = _ensure_ssh_tunnel()
    connect_config = dict(MYSQL_CONFIG)
    if tunnel:
        connect_config["host"] = tunnel.local_bind_host
        connect_config["port"] = tunnel.local_bind_port
    return pymysql.connect(**connect_config)


atexit.register(_close_ssh_tunnel)


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
