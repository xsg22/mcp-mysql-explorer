# MCP MySQL Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that connects AI agents (Cursor, Claude Desktop, etc.) to MySQL databases — enabling schema exploration, data querying, and SQL execution through natural language.

## Features

| Tool | Description |
|------|-------------|
| `list_tables` | List all tables in the database |
| `describe_table` | View table schema with column types and comments |
| `query` | Execute read-only queries (SELECT / SHOW / DESCRIBE / EXPLAIN) |
| `execute_sql` | Execute write operations (INSERT / UPDATE / DELETE / DDL) |
| `get_table_indexes` | Show all indexes of a table |
| `get_create_table` | Get the CREATE TABLE statement |
| `get_database_info` | Get database overview (version, size, table count) |

## Installation

```bash
pip install mcp-mysql-explorer
```

## Usage in Cursor

Open **Cursor Settings → MCP**, add a new server. Three ways to configure the database connection:

### Option 1: Command-line arguments (recommended)

```json
{
  "mcpServers": {
    "mysql": {
      "command": "mcp-mysql-server",
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

### Option 2: Environment variables

```json
{
  "mcpServers": {
    "mysql": {
      "command": "mcp-mysql-server",
      "env": {
        "MYSQL_HOST": "your-mysql-host",
        "MYSQL_PORT": "3306",
        "MYSQL_USER": "your-user",
        "MYSQL_PASSWORD": "your-password",
        "MYSQL_DATABASE": "your-database"
      }
    }
  }
}
```

### Option 3: `.env` file

Create a `.env` file in the working directory:

```env
MYSQL_HOST=your-mysql-host
MYSQL_PORT=3306
MYSQL_USER=your-user
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=your-database
```

Then simply:

```json
{
  "mcpServers": {
    "mysql": {
      "command": "mcp-mysql-server"
    }
  }
}
```

> **Priority**: command-line args > environment variables > `.env` file

## Usage in Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mysql": {
      "command": "mcp-mysql-server",
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
mcp-mysql-server --host localhost --user root --password secret --database mydb

# With .env file
mcp-mysql-server

# As a Python module
python -m mcp_mysql_server --host localhost --database mydb
```

## Security Notes

- The `query` tool only allows SELECT / SHOW / DESCRIBE / EXPLAIN statements.
- The `execute_sql` tool can run write operations — use with caution.
- Query results are capped at 1000 rows by default.
- Table/column identifiers are backtick-wrapped to prevent SQL injection.

## License

MIT
