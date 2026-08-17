# Quick Start

This guide starts MyAI on Windows in local-first mode.

Local mode is recommended for first use because it uses SQLite and automatic local authentication. You do not need MySQL or a manual login flow.

## Portable App Demo On Another Computer

Use the Stage 4 ZIP when running outside a source checkout. The target computer needs
Windows 10/11 x64, Python 3.12 x64, Java 17+, and network access for the first pinned
dependency installation unless a complete wheel directory is supplied.

After extracting both the ZIP and its adjacent checksum:

```powershell
.\setup.cmd
.\doctor.cmd
.\start.cmd
```

Open `http://127.0.0.1:8080`, and stop with `.\stop.cmd`. See
[Portable Windows App](PORTABLE_APP.md) for verification, reset, real-model settings,
and the exact packaging boundary.

## Development Checkout

## Requirements

- Windows PowerShell
- JDK available to the startup script
- Python virtual environment under `myai-python-agent/.venv`
- Project dependencies installed for Java and Python

## 1. Check The Environment

From the project root:

```powershell
.\start-myai.cmd doctor -LocalMode
```

`FAIL` means startup is likely to fail. `WARN` means MyAI may still run, but the item should be reviewed.

## 2. Start MyAI

```powershell
.\start-myai.cmd -LocalMode
```

You can also double-click `start-myai.cmd`; the no-argument path starts LocalMode by default.

The script starts:

- Python Agent on `http://127.0.0.1:8000`
- Java web app on `http://127.0.0.1:8080`

Open:

```text
http://127.0.0.1:8080
```

Keep the terminal open. Press `Ctrl+C` to stop services.

## 3. Stop MyAI

```powershell
.\start-myai.cmd stop
```

If custom ports were used, pass the same ports:

```powershell
.\start-myai.cmd stop -PythonPort 8011 -JavaPort 8091
```

## 4. Run In Background

```powershell
.\start-myai.cmd -LocalMode -NoPause
```

Stop it later with:

```powershell
.\start-myai.cmd stop
```

## 5. Optional MySQL Mode

Use MySQL mode only when you want the classic login/database setup.

Copy:

```text
scripts/start-myai.env.example
```

to:

```text
scripts/start-myai.env
```

Then fill in local MySQL values. Do not commit real passwords.

Start:

```powershell
.\start-myai.cmd
```

## 6. First Things To Try

- Open the Demo workspace and run a guided scenario.
- Use Chat as the main agent cockpit.
- Upload a small `.txt`, `.pdf`, or `.docx` file in Knowledge.
- Ask a task-oriented prompt such as checking runtime status.
- Open Settings and review System Health.

## 7. Useful Commands

```powershell
.\start-myai.cmd status
.\start-myai.cmd restart -LocalMode
.\start-myai.cmd doctor -LocalMode
```

Python tests:

```powershell
cd myai-python-agent
.\.venv\Scripts\python.exe -m unittest
```

Java tests:

```powershell
cd myai-java-service
$env:JAVA_HOME='<path-to-jdk-17-or-newer>'
.\mvnw.cmd -q test
```
