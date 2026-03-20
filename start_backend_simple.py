#!/usr/bin/env python3

"""
简单的后端服务器启动脚本
"""

import os
import sys

print("=== LLM Case System Backend ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# 检查上传目录
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
print(f"Upload folder: {UPLOAD_FOLDER}")
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Created upload folder: {UPLOAD_FOLDER}")
else:
    print(f"Upload folder exists: {UPLOAD_FOLDER}")

# 导入必要的模块
try:
    from flask import Flask, request, jsonify, send_from_directory
    import json
    print("Flask imported successfully")
except Exception as e:
    print(f"Error importing Flask: {e}")
    sys.exit(1)

# 创建Flask应用
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 允许跨域
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS')
    return response

# 根路径
@app.route('/')
def index():
    return 'LLM Case System Backend'

# 上传接口
@app.route('/api/upload', methods=['POST'])
def upload_file():
    print("Received upload request")
    if 'file' not in request.files:
        print("No file part in request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        print("No selected file")
        return jsonify({'error': 'No selected file'}), 400
    
    # 保存文件
    filename = file.filename
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    print(f"File saved: {file_path}")
    
    # 解析文件名生成菜单结构
    name_without_ext = os.path.splitext(filename)[0]
    parts = name_without_ext.split('_')
    system_name = parts[0] if parts else '未知系统'
    menu_items = parts[1:] if len(parts) > 1 else []
    
    # 生成菜单结构数据
    menu_structure_data = []
    for i, item in enumerate(menu_items):
        menu_structure_data.append({
            'level': i + 1,
            'name': item
        })
    
    # 生成响应
    response = {
        'file_name': filename,
        'file_path': file_path,
        'system_name': system_name,
        'menu_structure': menu_structure_data,
        'screenshot_id': 1
    }
    
    print(f"Upload successful: {filename}")
    return jsonify(response), 201

# 获取历史记录接口
@app.route('/api/history', methods=['GET'])
def get_history():
    print("Received history request")
    # 模拟历史记录
    history = [
        {
            'id': 1,
            'screenshot_id': 1,
            'file_name': '测试系统_一级菜单_二级菜单.png',
            'system_name': '测试系统',
            'operation_type': 'upload',
            'operation_time': '2026-03-17 10:00:00'
        }
    ]
    return jsonify(history)

# 删除历史记录接口
@app.route('/api/history/<int:history_id>', methods=['DELETE'])
def delete_history(history_id):
    print(f"Received delete request for history ID: {history_id}")
    return jsonify({'message': 'History record deleted successfully'}), 200

# 提供上传文件的访问
@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    print(f"Serving file: {filename}")
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    print("Starting Flask server...")
    print("Server will be available at http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    app.run(debug=True, host='0.0.0.0', port=5000)
