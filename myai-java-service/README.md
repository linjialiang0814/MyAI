# MyAI Java 服务层

`myai-java-service` 是 MyAI 项目的服务层。
它基于 Spring Boot 构建，负责用户可见页面、账号系统、安全控制、数据库持久化，
以及与 Python 智能层的交互。

## 功能

- 用户注册、登录、退出登录和基于会话的访问控制。
- 使用 Spring Security 对密码进行加密存储。
- 使用 Thymeleaf 渲染主要 Web 页面。
- 提供聊天、记忆画像、知识库和任务执行等页面入口。
- 持久化保存对话历史，包括消息保存、历史加载、继续对话和 Markdown 导出。
- 默认使用 MySQL 持久化用户、会话和聊天消息；本地模式可使用 SQLite。
- 支持本地自动登录模式，用于个人单机使用和快速启动。
- 代理调用 Python FastAPI 服务，对接：
  - AI 对话
  - 长期记忆
  - 个人知识库 / RAG
  - 任务规划与工具执行

## 项目结构

```text
myai-java-service/
|-- src/main/java/com/test/login/
|   |-- config/        # Spring Security、WebClient、MVC 配置
|   |-- controller/    # 页面控制器和 REST 接口
|   |-- dto/           # 请求和响应 DTO
|   |-- model/         # JPA 实体
|   |-- repository/    # Spring Data JPA 仓库
|   `-- service/       # 业务逻辑和 Python 服务代理
|-- src/main/resources/
|   |-- templates/     # Thymeleaf 页面
|   |-- static/        # 静态资源
|   `-- application.properties
|-- pom.xml
|-- mvnw
`-- mvnw.cmd
```

## 运行环境

- JDK 17 或更高版本
- MySQL 8.x，或本地模式下使用 SQLite
- Maven Wrapper，项目已包含 `mvnw` / `mvnw.cmd`
- Python 智能服务需要单独运行，通常地址为 `http://127.0.0.1:8000`

## 配置

服务会读取以下环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `SERVER_PORT` | `8080` | Java Web 服务端口 |
| `PYTHON_SERVICE_BASE_URL` | `http://127.0.0.1:8000` | Python FastAPI 服务地址 |
| `DB_URL` | `jdbc:mysql://localhost:3306/login_demo?...` | MySQL JDBC 地址 |
| `DB_USERNAME` | `root` | MySQL 用户名 |
| `DB_PASSWORD` | 空 | MySQL 密码 |
| `MYAI_AUTH_MODE` | 默认登录态 | 设置为 `local` 时启用本地自动登录 |
| `MYAI_LOCAL_USERNAME` | `local-user` | 本地模式自动用户名称 |

示例：

```powershell
$env:DB_URL="jdbc:mysql://localhost:3306/login_demo?useSSL=false&serverTimezone=UTC&characterEncoding=utf8"
$env:DB_USERNAME="root"
$env:DB_PASSWORD="your_mysql_password"
$env:PYTHON_SERVICE_BASE_URL="http://127.0.0.1:8000"
```

## 运行

Windows：

```powershell
.\mvnw.cmd spring-boot:run
```

macOS 或 Linux：

```bash
./mvnw spring-boot:run
```

启动后访问：

```text
http://127.0.0.1:8080
```

## 推荐启动方式

本地正常使用时，建议在项目根目录启动整个 MyAI 系统：

```powershell
.\start-myai.cmd
```

该脚本会尽可能启动 MySQL、启动 Python 服务、启动当前 Java 服务，并支持通过 `Ctrl+C` 停止 Java 和 Python 服务。

如果只想在个人电脑上快速运行，不依赖 MySQL 和手动登录，可以使用本地模式：

```powershell
.\start-myai.cmd -LocalMode
```

本地模式会启用 SQLite 数据库和自动本地用户，数据库文件默认为 `myai-local.db`。

## 说明

- 本模块不负责模型推理，智能体核心能力由 `myai-python-agent` 提供。
- 默认模式下 MySQL 必须可连接；本地模式下不需要 MySQL。
- 数据库表结构会通过 `spring.jpa.hibernate.ddl-auto=update` 自动更新。

---

# MyAI Java Service

`myai-java-service` is the Web entry module of MyAI. It is built with Spring Boot and provides the user-facing pages, account system, security control, database persistence, and proxy access to the Python AI service.

## Features

- User registration, login, logout, and session-based access control.
- Password encryption with Spring Security.
- Main Web interface rendered with Thymeleaf.
- Chat page, memory profile page, knowledge base page, and task execution page.
- Conversation history persistence, including message saving, history loading, continued chat, and Markdown export.
- MySQL persistence by default, with an optional SQLite local mode.
- Local automatic authentication mode for single-user desktop use.
- Proxy integration with the Python FastAPI service for:
  - AI chat
  - long-term memory
  - personal knowledge base / RAG
  - task planning and tool execution

## Project Structure

```text
myai-java-service/
|-- src/main/java/com/test/login/
|   |-- config/        # Spring Security, WebClient, MVC config
|   |-- controller/    # Page controllers and REST endpoints
|   |-- dto/           # Request and response DTOs
|   |-- model/         # JPA entities
|   |-- repository/    # Spring Data JPA repositories
|   `-- service/       # Business logic and Python service proxy
|-- src/main/resources/
|   |-- templates/     # Thymeleaf pages
|   |-- static/        # Static assets
|   `-- application.properties
|-- pom.xml
|-- mvnw
`-- mvnw.cmd
```

## Required Environment

- JDK 17 or later
- MySQL 8.x, or SQLite in local mode
- Maven Wrapper, included as `mvnw` / `mvnw.cmd`
- Python AI service running separately, usually at `http://127.0.0.1:8000`

## Configuration

The service reads these environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `SERVER_PORT` | `8080` | Java Web service port |
| `PYTHON_SERVICE_BASE_URL` | `http://127.0.0.1:8000` | Python FastAPI service address |
| `DB_URL` | `jdbc:mysql://localhost:3306/login_demo?...` | MySQL JDBC URL |
| `DB_USERNAME` | `root` | MySQL username |
| `DB_PASSWORD` | empty | MySQL password |
| `MYAI_AUTH_MODE` | default session login | Set to `local` to enable automatic local auth |
| `MYAI_LOCAL_USERNAME` | `local-user` | Local mode automatic username |

Example:

```powershell
$env:DB_URL="jdbc:mysql://localhost:3306/login_demo?useSSL=false&serverTimezone=UTC&characterEncoding=utf8"
$env:DB_USERNAME="root"
$env:DB_PASSWORD="your_mysql_password"
$env:PYTHON_SERVICE_BASE_URL="http://127.0.0.1:8000"
```

## Run

On Windows:

```powershell
.\mvnw.cmd spring-boot:run
```

On macOS or Linux:

```bash
./mvnw spring-boot:run
```

After startup, open:

```text
http://127.0.0.1:8080
```

## Recommended Startup Method

For normal local use, start the whole MyAI system from the project root:

```powershell
.\start-myai.cmd
```

That script starts MySQL if possible, starts the Python service, starts this Java service, and lets you press `Ctrl+C` to stop the Java and Python services.

For fast single-machine use without MySQL or manual login:

```powershell
.\start-myai.cmd -LocalMode
```

Local mode enables SQLite and an automatic local user. The default database file is `myai-local.db`.

## Notes

- This module is not responsible for model inference. AI capabilities are handled by `myai-python-agent`.
- MySQL must be reachable in the default mode. Local mode does not require MySQL.
- The database schema is updated automatically by JPA through `spring.jpa.hibernate.ddl-auto=update`.
