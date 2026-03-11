# MCP MySQL 服务器

这是一个 [模型上下文协议（MCP）](https://modelcontextprotocol.io) 服务器，可将 AI 助手（如 Cursor、Claude Desktop）连接到 MySQL 数据库，支持通过自然语言进行库表结构查看、数据查询与 SQL 执行。

英文文档： [README.md](README.md)

## 功能列表

| 工具 | 说明 |
|------|------|
| `list_tables` | 列出当前数据库中的所有表 |
| `describe_table` | 查看指定表的字段结构、类型与注释 |
| `query` | 执行只读查询（SELECT / SHOW / DESCRIBE / EXPLAIN） |
| `execute_sql` | 执行写操作（INSERT / UPDATE / DELETE / DDL），只读模式下会被禁用 |
| `get_table_indexes` | 查看指定表的索引信息 |
| `get_create_table` | 获取指定表的 CREATE TABLE 语句 |
| `get_database_info` | 获取数据库概览（版本、表数量、库大小） |

## 安装

```bash
pip install mcp-mysql-explorer
```

## 在 Cursor 中使用

打开 **Cursor 设置 -> MCP**，新增一个服务器。数据库连接支持三种配置方式。

### 方式一：命令行参数（推荐）

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

如果需要开启可写模式（允许写 SQL），显式追加 `--allow-write`：

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

### 方式二：环境变量

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
        "MYSQL_READ_ONLY": "true"
      }
    }
  }
}
```

### 方式三：`.env` 文件

在工作目录创建 `.env`：

```env
MYSQL_HOST=your-mysql-host
MYSQL_PORT=3306
MYSQL_USER=your-user
MYSQL_PASSWORD=your-password
MYSQL_DATABASE=your-database
MYSQL_READ_ONLY=true
```

然后直接启动：

```json
{
  "mcpServers": {
    "mysql": {
      "command": "mcp-mysql-explorer"
    }
  }
}
```

> 配置优先级：命令行参数 > 环境变量 > `.env` 文件

## 在 Claude Desktop 中使用

在 `claude_desktop_config.json` 中加入：

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

## 手动运行

```bash
# 命令行参数方式
mcp-mysql-explorer --host localhost --user root --password secret --database mydb

# 显式开启可写模式
mcp-mysql-explorer --host localhost --user root --password secret --database mydb --allow-write

# .env 方式
mcp-mysql-explorer

# 模块方式
python -m mcp_mysql_explorer --host localhost --database mydb
```

## 测试脚本

```bash
# 运行单元测试（不需要真实数据库）
python scripts/run_tests.py
```

```bash
# 可选：手动冒烟验证（仅从环境变量读取连接信息）
# 必需环境变量：MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
python scripts/manual_smoke_check.py --mode both
```

## 安全说明

- `query` 仅允许 SELECT / SHOW / DESCRIBE / EXPLAIN。
- 默认开启只读模式（`MYSQL_READ_ONLY=true`）。
- 如需开启写入，设置 `MYSQL_READ_ONLY=false` 或传入 `--allow-write`。
- 仅当关闭只读模式时，`execute_sql` 才会执行写操作。
- 查询结果默认最多返回 1000 行。
- 表名与列名会进行反引号包裹，降低标识符注入风险。

## 许可证

MIT
