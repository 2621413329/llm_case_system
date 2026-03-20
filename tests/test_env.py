#!/usr/bin/env python3

print("Testing Python environment...")

# 测试基本Python功能
try:
    print("Python version:", __import__("sys").version)
    print("Python path:", __import__("sys").path)
    print("Current directory:", __import__("os").getcwd())
    print("Basic Python functionality: OK")
except Exception as e:
    print("Basic Python functionality: ERROR", e)

# 测试Flask导入
try:
    import flask
    print("Flask version:", flask.__version__)
    print("Flask import: OK")
except Exception as e:
    print("Flask import: ERROR", e)

# 测试SQLAlchemy导入
try:
    import sqlalchemy
    print("SQLAlchemy version:", sqlalchemy.__version__)
    print("SQLAlchemy import: OK")
except Exception as e:
    print("SQLAlchemy import: ERROR", e)

# 测试PyMySQL导入
try:
    import pymysql
    print("PyMySQL import: OK")
except Exception as e:
    print("PyMySQL import: ERROR", e)

print("Environment test completed.")

