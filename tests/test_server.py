import importlib
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


MODULE_NAME = "mcp_mysql_explorer.server"
MYSQL_ENV_KEYS = (
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DATABASE",
    "MYSQL_READ_ONLY",
)


def load_server(argv: list[str] | None = None, env_overrides: dict[str, str] | None = None):
    """Import server module with controlled argv/env for deterministic tests."""
    argv = argv or []
    env = dict(os.environ)
    for key in MYSQL_ENV_KEYS:
        env.pop(key, None)
    env["PYTHON_DOTENV_DISABLED"] = "1"
    if env_overrides:
        env.update(env_overrides)

    with patch.dict(os.environ, env, clear=True):
        with patch.object(sys, "argv", ["mcp-mysql-explorer", *argv]):
            sys.modules.pop(MODULE_NAME, None)
            return importlib.import_module(MODULE_NAME)


def make_connection_and_cursor():
    conn = MagicMock()
    cur = MagicMock()
    cursor_cm = MagicMock()
    cursor_cm.__enter__.return_value = cur
    cursor_cm.__exit__.return_value = None
    conn.cursor.return_value = cursor_cm
    return conn, cur


class ServerBehaviorTests(unittest.TestCase):
    def test_default_read_only_mode_enabled(self):
        server = load_server()
        self.assertTrue(server.READ_ONLY_MODE)

    def test_read_only_can_be_disabled_by_env(self):
        server = load_server(env_overrides={"MYSQL_READ_ONLY": "false"})
        self.assertFalse(server.READ_ONLY_MODE)

    def test_allow_write_cli_has_priority(self):
        server = load_server(argv=["--allow-write"], env_overrides={"MYSQL_READ_ONLY": "true"})
        self.assertFalse(server.READ_ONLY_MODE)

    def test_query_blocks_write_sql_in_read_only(self):
        server = load_server()
        with patch.object(server, "_get_connection") as mock_conn:
            result = server.query("UPDATE users SET active = 1")
        self.assertIn("Read-only mode is enabled", result)
        mock_conn.assert_not_called()

    def test_query_select_success(self):
        server = load_server()
        conn, cur = make_connection_and_cursor()
        cur.fetchall.return_value = [{"ok": 1}]

        with patch.object(server, "_get_connection", return_value=conn):
            result = server.query("SELECT 1 AS ok")

        self.assertIn('"ok": 1', result)
        cur.execute.assert_called_once_with("SELECT 1 AS ok")
        conn.close.assert_called_once()

    def test_query_blocks_write_like_sql_even_when_write_mode_enabled(self):
        server = load_server(argv=["--allow-write"])
        with patch.object(server, "_get_connection") as mock_conn:
            result = server.query("DELETE FROM users")
        self.assertIn("Use execute_sql for write operations", result)
        mock_conn.assert_not_called()

    def test_execute_sql_blocked_in_read_only_mode(self):
        server = load_server()
        with patch.object(server, "_get_connection") as mock_conn:
            result = server.execute_sql("DELETE FROM users")
        self.assertIn("running in read-only mode", result)
        mock_conn.assert_not_called()

    def test_execute_sql_success_in_write_mode(self):
        server = load_server(argv=["--allow-write"])
        conn, cur = make_connection_and_cursor()
        cur.execute.return_value = 2
        cur.description = None

        with patch.object(server, "_get_connection", return_value=conn):
            result = server.execute_sql("UPDATE users SET active = 1")

        self.assertEqual("OK - 2 row(s) affected.", result)
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()
        conn.close.assert_called_once()

    def test_execute_sql_returns_rows_when_cursor_has_description(self):
        server = load_server(argv=["--allow-write"])
        conn, cur = make_connection_and_cursor()
        cur.execute.return_value = 1
        cur.description = ("value",)
        cur.fetchall.return_value = [{"value": "ok"}]

        with patch.object(server, "_get_connection", return_value=conn):
            result = server.execute_sql("SELECT 'ok' AS value")

        self.assertIn('"value": "ok"', result)
        conn.commit.assert_called_once()

    def test_list_tables_returns_name_list(self):
        server = load_server()
        conn, cur = make_connection_and_cursor()
        cur.fetchall.return_value = [
            {"Tables_in_db": "users"},
            {"Tables_in_db": "orders"},
        ]

        with patch.object(server, "_get_connection", return_value=conn):
            result = server.list_tables()

        self.assertEqual(["users", "orders"], json.loads(result))

    def test_describe_table_merges_column_comments(self):
        server = load_server()
        conn, cur = make_connection_and_cursor()
        cur.fetchall.side_effect = [
            [
                {
                    "Field": "id",
                    "Type": "int",
                    "Null": "NO",
                    "Key": "PRI",
                    "Default": None,
                    "Extra": "auto_increment",
                }
            ],
            [
                {"COLUMN_NAME": "id", "COLUMN_COMMENT": "primary key"},
            ],
        ]
        cur.fetchone.return_value = {"TABLE_COMMENT": "user table"}

        with patch.object(server, "_get_connection", return_value=conn):
            result = server.describe_table("users")

        payload = json.loads(result)
        self.assertEqual("users", payload["table"])
        self.assertEqual("user table", payload["comment"])
        self.assertEqual("primary key", payload["columns"][0]["Comment"])

    def test_get_database_info_output(self):
        server = load_server()
        conn, cur = make_connection_and_cursor()
        cur.fetchone.side_effect = [
            {"table_count": 4},
            {"size_mb": 12.5},
            {"version": "8.0.36"},
        ]

        with patch.object(server, "_get_connection", return_value=conn):
            result = server.get_database_info()

        payload = json.loads(result)
        self.assertEqual(4, payload["table_count"])
        self.assertEqual(12.5, payload["size_mb"])
        self.assertEqual("8.0.36", payload["mysql_version"])

    def test_safe_identifier_rejects_backtick(self):
        server = load_server()
        with self.assertRaises(ValueError):
            server._safe_identifier("bad`name")


if __name__ == "__main__":
    unittest.main(verbosity=2)
