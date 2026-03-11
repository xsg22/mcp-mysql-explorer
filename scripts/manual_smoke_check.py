import argparse
import importlib
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MODULE_NAME = "mcp_mysql_explorer.server"
REQUIRED_ENV_KEYS = (
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DATABASE",
)

def load_server(allow_write: bool):
    argv = [
        "mcp-mysql-explorer",
        "--host",
        os.environ["MYSQL_HOST"],
        "--port",
        os.environ["MYSQL_PORT"],
        "--user",
        os.environ["MYSQL_USER"],
        "--password",
        os.environ["MYSQL_PASSWORD"],
        "--database",
        os.environ["MYSQL_DATABASE"],
    ]
    if allow_write:
        argv.append("--allow-write")

    sys.modules.pop(MODULE_NAME, None)
    old_argv = sys.argv
    try:
        sys.argv = argv
        return importlib.import_module(MODULE_NAME)
    finally:
        sys.argv = old_argv


def run_mode(allow_write: bool):
    server = load_server(allow_write=allow_write)
    mode = "write" if allow_write else "read-only"
    print(f"\n=== Mode: {mode} (READ_ONLY_MODE={server.READ_ONLY_MODE}) ===")

    read_result = server.query("SELECT 1 AS ok")
    write_result = server.execute_sql("SET @mcp_rw_test = 1")

    print("[READ ] query('SELECT 1 AS ok')")
    print(read_result)
    print("[WRITE] execute_sql('SET @mcp_rw_test = 1')")
    print(write_result)


def main():
    parser = argparse.ArgumentParser(
        description="Manual smoke test for MCP MySQL server modes. "
        "This script never stores credentials and reads them only from env.",
    )
    parser.add_argument(
        "--mode",
        choices=("readonly", "write", "both"),
        default="both",
        help="Which mode(s) to test. Default: both",
    )
    args = parser.parse_args()

    missing = [key for key in REQUIRED_ENV_KEYS if not os.getenv(key)]
    if missing:
        raise SystemExit(
            "Missing required environment variables: "
            + ", ".join(missing)
            + "\nSet them in your shell first, then run again."
        )

    if args.mode in ("readonly", "both"):
        run_mode(allow_write=False)
    if args.mode in ("write", "both"):
        run_mode(allow_write=True)


if __name__ == "__main__":
    main()
