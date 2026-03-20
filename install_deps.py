import os
import sys
import subprocess

# 检查Python版本
print(f'Python version: {sys.version}')

# 安装pip
try:
    import pip
    print('Pip is already installed')
except ImportError:
    print('Installing pip...')
    # 下载get-pip.py并运行
    subprocess.run([sys.executable, '-m', 'ensurepip', '--upgrade'], check=True)

# 安装依赖
print('Installing dependencies...')
dependencies = ['Flask', 'Flask-SQLAlchemy', 'PyMySQL', 'SQLAlchemy']
for dep in dependencies:
    print(f'Installing {dep}...')
    subprocess.run([sys.executable, '-m', 'pip', 'install', dep], check=True)

print('All dependencies installed successfully!')

# 验证安装
try:
    import flask
    import flask_sqlalchemy
    import pymysql
    import sqlalchemy
    print('\nVerification successful:')
    print(f'Flask version: {flask.__version__}')
    print(f'Flask-SQLAlchemy version: {flask_sqlalchemy.__version__}')
    print(f'PyMySQL version: {pymysql.__version__}')
    print(f'SQLAlchemy version: {sqlalchemy.__version__}')
except ImportError as e:
    print(f'Error: {e}')