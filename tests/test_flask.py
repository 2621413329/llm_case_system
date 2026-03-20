#!/usr/bin/env python3

print("Testing Flask basic functionality...")

# 测试基本导入
try:
    import flask
    print(f"Flask version: {flask.__version__}")
    print("Flask import successful")
except Exception as e:
    print(f"Flask import failed: {e}")
    import traceback
    traceback.print_exc()

# 测试简单的Flask应用
try:
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def hello():
        return 'Hello, World!'
    
    print("Flask app created successfully")
    print("Basic Flask functionality: OK")
except Exception as e:
    print(f"Flask app creation failed: {e}")
    import traceback
    traceback.print_exc()

print("Test completed.")

