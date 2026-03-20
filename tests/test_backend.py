#!/usr/bin/env python3

"""
测试后端服务器是否能够正常运行
"""

import os
import sys
import subprocess
import time

print("=== Testing Backend Server ===")

# 检查Python环境
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# 检查上传目录
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'uploads')
UPLOAD_FOLDER = os.path.abspath(UPLOAD_FOLDER)
print(f"Upload folder: {UPLOAD_FOLDER}")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Created upload folder: {UPLOAD_FOLDER}")
else:
    print(f"Upload folder exists: {UPLOAD_FOLDER}")

# 启动后端服务器（使用标准库版本）
print("\nStarting backend server...")
server_process = subprocess.Popen(
    [sys.executable, os.path.join(os.path.dirname(__file__), '..', 'backend', 'simple_server.py')],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# 等待服务器启动
time.sleep(2)

# 检查服务器状态
print("\nChecking server status...")
try:
    import requests
    response = requests.get("http://localhost:5000/")
    print(f"Server response: {response.status_code} - {response.text}")
    print("Backend server is running successfully!")
except Exception as e:
    print(f"Error connecting to server: {e}")
    print("Server output:")
    try:
        stdout, stderr = server_process.communicate(timeout=3)
        print(f"STDOUT:\n{stdout}")
        print(f"STDERR:\n{stderr}")
    except Exception:
        pass
    server_process.terminate()

print("\nTest completed.")

