#!/usr/bin/env python3

print("Testing Python environment...")
import sys
import os

# 写入测试文件
with open('test_output.txt', 'w') as f:
    f.write(f"Python version: {sys.version}\n")
    f.write(f"Current directory: {os.getcwd()}\n")
    f.write("Test completed successfully!\n")

print("Test completed. Check test_output.txt for results.")
