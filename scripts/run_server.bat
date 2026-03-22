@echo off
cd /d "%~dp0.."

:: 启动简单的后端服务器（优先使用项目 .venv）
echo Starting LLM Case System Backend...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" backend\simple_server.py
) else (
  python backend\simple_server.py
)

pause
