# MCP MySQL Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that connects AI agents (Cursor, Claude Desktop, etc.) to MySQL databases, enabling schema exploration, data querying, and SQL execution through natural language.

Chinese docs: [README.zh.md](README.zh.md)

## Features

| Tool | Description |
|------|-------------|
| `list_tables` | List all tables in the database |
| `describe_table` | View table schema with column types and comments |
| `query` | Execute read-only queries (SELECT / SHOW / DESCRIBE / EXPLAIN) |
| `execute_sql` | Execute write operations (INSERT / UPDATE / DELETE / DDL), disabled in read-only mode |
| `get_table_indexes` | Show all indexes of a table |
| `get_create_table` | Get the CREATE TABLE statement |
| `get_database_info` | Get database overview (version, size, table count) |

## Installation

```bash
pip install mcp-mysql-explorer
```

## Usage in Cursor

Open **Cursor Settings -> MCP**, add a new server. Three ways to configure the database connection. SSH tunneling through a bastion/jump host is also supported.

### Option 1: Command-line arguments (recommended)

```json
{
  "mcpServers": {
    "mysql": {
      "command": "mcp-mysql-explorer",
      "args": [
        "--host", "your-mysql-host",
        "--port", "3306",
        "--user", "your-user",
        "--password", "your-password",
        "--database", "your-database"
      ]
    }
  }
}
```

Enable write mode explicitly:

```json
{
  "mcpServers": {
    "mysql": {
      "command": "mcp-mysql-explorer",
      "args": [
        "--host", "your-mysql-host",
        "--database", "your-database",
        "--allow-write"
      ]
    }
  }
}
```

If the database is only reachable through an SSH bastion, add `--ssh-*` arguments:

```json
{
  "mcpServers": {
    "mysql": {
      "command": "mcp-mysql-explorer",
      "args": [
        "--host", "mysql.internal",
        "--port", "3306",
        "--user", "your-db-user",
        "--password", "your-db-password",
        "--database", "your-database",
        "--ssh-host", "bastion.example.com",
        "--ssh-port", "22",
        "--ssh-user", "your-ssh-user",
        "--ssh-private-key", "/Users/you/.ssh/id_rsa"
      ]
    }
  }
}
```

> In SSH mode, `--host` / `MYSQL_HOST` is the MySQL address as seen from the SSH server. SSH tunneling is enabled automatically when `--ssh-host` or `MYSQL_SSH_HOST` is set. You can explicitly disable it with `--ssh-enabled false`.

### Option 2: Environment variables

```json
{
  "mcpServers": {
    "mysql": {
      "command": "mcp-mysql-explorer",
      "env": {
        "MYSQL_HOST": "your-mysql-host",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "your-user",
        "MYSQL_PASSWORD": "your-password",
        "MYSQL_DATABASE": "your-database",
        "MYSQL_READ_ONLY": "true",
        "MYSQL_SSH_HOST": "bastion.example.com",
        "MYSQL_SSH_PORT": "22",
        "MYSQL_SSH_USER": "your-ssh-user",
        "MYSQL_SSH_PRIVATE_KEY": "/Users/you/.ssh/id_rsa"
      }
    }
  }
}
```

SSH environment variables:

| Environment variable | Description |
|----------------------|-------------|
| `MYSQL_SSH_ENABLED` | Enable SSH tunneling (true/false). Defaults to enabled when `MYSQL_SSH_HOST` is set |
| `MYSQL_SSH_HOST` | SSH bastion/jump host |
| `MYSQL_SSH_PORT` | SSH port, defaults to `22` |
| `MYSQL_SSH_USER` | SSH username |
| `MYSQL_SSH_PASSWORD` | SSH password |
| `MYSQL_SSH_PRIVATE_KEY` | Path to SSH private key |
| `MYSQL_SSH_PRIVATE_KEY_PASSWORD` | SSH private key passphrase |
| `MYSQL_SSH_LOCAL_HOST` | Local forwarding bind host, defaults to `127.0.0.1` |
| `MYSQL_SSH_LOCAL_PORT` | Local forwarding bind port, defaults to `0` for automatic assignment |

### Option 3: `.env` file

Create a `.env` file in the working directory:

```env
MYSQL_HOST=your-mysql-host
MYSQL_PORT=3306
MYSQL_USER=your-user
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=your-database
MYSQL_READ_ONLY=true
MYSQL_SSH_HOST=bastion.example.com
MYSQL_SSH_USER=your-ssh-user
MYSQL_SSH_PRIVATE_KEY=/Users/you/.ssh/id_rsa
```

Then simply:

```json
{
  "mcpServers": {
    "mysql": {
      "command": "mcp-mysql-explorer"
    }
  }
}
```

> Priority: command-line args > environment variables > `.env` file

## Usage in Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mysql": {
      "command": "mcp-mysql-explorer",
      "args": [
        "--host", "your-mysql-host",
        "--user", "your-user",
        "--password", "your-password",
        "--database", "your-database"
      ]
    }
  }
}
```

## Run Manually

```bash
# With command-line arguments
mcp-mysql-explorer --host localhost --user root --password secret --database mydb

# Explicitly allow write operations
mcp-mysql-explorer --host localhost --user root --password secret --database mydb --allow-write

# Through an SSH bastion
mcp-mysql-explorer --host mysql.internal --user root --password secret --database mydb \
  --ssh-host bastion.example.com --ssh-user deploy --ssh-private-key ~/.ssh/id_rsa

# With .env file
mcp-mysql-explorer

# As a Python module
python -m mcp_mysql_explorer --host localhost --database mydb
```

## Testing

```bash
# Run unit tests (no real database needed)
python scripts/run_tests.py
```

```bash
# Optional manual smoke check (reads credentials from env only)
# Required env: MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
python scripts/manual_smoke_check.py --mode both
```

## Security Notes

- The `query` tool only allows SELECT / SHOW / DESCRIBE / EXPLAIN statements.
- Read-only mode is enabled by default (`MYSQL_READ_ONLY=true`).
- To enable writes, set `MYSQL_READ_ONLY=false` or pass `--allow-write`.
- The `execute_sql` tool can run write operations only when read-only mode is disabled.
- Query results are capped at 1000 rows by default.
- Table/column identifiers are backtick-wrapped to prevent SQL injection.

## License

MIT
