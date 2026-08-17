# MyAI Startup Scripts

Windows:

```powershell
.\start-myai.cmd
```

Running `start-myai.cmd` with no arguments, including double-clicking it in Explorer, starts MyAI in LocalMode by default.

After startup, keep the terminal window open. Press `Ctrl+C` in that window to stop the Python and Java services and release their ports.

Stop services and release ports:

```powershell
.\start-myai.cmd stop
```

Check status or restart:

```powershell
.\start-myai.cmd status
.\start-myai.cmd restart
```

Run first-run diagnostics without starting services:

```powershell
.\start-myai.cmd doctor
.\start-myai.cmd doctor -LocalMode
```

Run repeatable LocalMode product-path smoke:

```powershell
.\local-smoke.cmd
```

The local smoke command verifies startup doctor, LocalMode start, Python/Java readiness, frontend `/home` and CSRF, observability, memory, knowledge, task APIs, chat submit, task execution, stop, and port release.

Useful smoke options:

```powershell
.\local-smoke.cmd -KeepRunning
.\local-smoke.cmd -SkipStartStop
.\local-smoke.cmd -IncludeLiveModelProbe
.\local-smoke.cmd -SkipChatSmoke
.\local-smoke.cmd -SkipTaskSmoke
```

The default smoke does not require real model connectivity. Use `-IncludeLiveModelProbe` when you explicitly want to check the external provider.

Common options:

```powershell
.\start-myai.cmd -MysqlServiceName MySQL80
.\start-myai.cmd -DbUsername root -DbPassword your_password
.\start-myai.cmd -SkipMysql
.\start-myai.cmd -LocalMode
.\start-myai.cmd -NoPause
```

Local mode uses SQLite and automatic local authentication, so MySQL and manual login are not required:

```powershell
.\start-myai.cmd -LocalMode
```

This is equivalent to the no-argument double-click path.

To avoid typing the MySQL password every time, copy `scripts/start-myai.env.example` to `scripts/start-myai.env` and fill in your local values:

```text
MYSQL_SERVICE_NAME=MySQL83
DB_USERNAME=root
DB_PASSWORD=your_mysql_password
```

The script starts:

- MySQL, when it can find a local MySQL Windows service and port `3306` is not already open. MySQL is skipped when `-LocalMode` is used
- Python FastAPI service on `127.0.0.1:8000`
- Java Spring Boot service on `127.0.0.1:8080`

For Java startup, the script first uses a built jar from `myai-java-service/target` when one exists. If no jar is found, it falls back to `mvnw.cmd spring-boot:run` while forcing Maven to use the project-local `.maven-home` and `.m2repo` directories.

Service logs are written to `scripts/logs/python-service.log` and `scripts/logs/java-service.log`.

The stop command releases the Python and Java ports, but leaves MySQL running by default.

When `-NoPause` is used, the script exits after startup and services continue in the background. In that mode, use `.\start-myai.cmd stop` to stop them later.

If you started MyAI with custom ports, pass the same ports when stopping:

```powershell
.\start-myai.cmd -LocalMode -NoPause -PythonPort 8011 -JavaPort 8091
.\start-myai.cmd stop -PythonPort 8011 -JavaPort 8091
```

The stop command uses the tracked launcher pids first, then releases any remaining Python/Java process still listening on the configured ports.

The `doctor` command checks:

- project directories
- Python executable and key imports
- Java/JDK and Maven wrapper or built jar
- startup env file
- Python `.env` for model/provider readiness
- configured ports
- MySQL or SQLite/local mode readiness
- writable runtime/log/storage directories

It does not start or stop services. A `FAIL` means startup is likely to fail; a `WARN` means startup may still work but may need attention.
