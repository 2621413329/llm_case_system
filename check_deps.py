import sys
import os

print('Python executable:', sys.executable)
print('Python version:', sys.version)
print('Current directory:', os.getcwd())

# 检查已安装的包
try:
    import pip
    print('\nInstalled packages:')
    for package in pip.get_installed_distributions():
        print(f'{package.name}=={package.version}')
except ImportError:
    print('Pip not found')

# 检查cryptography是否安装
try:
    import cryptography
    print(f'\ncryptography version: {cryptography.__version__}')
except ImportError:
    print('\ncryptography not installed')

# 检查其他依赖
try:
    import flask
    print(f'Flask version: {flask.__version__}')
except ImportError:
    print('Flask not installed')

try:
    import flask_sqlalchemy
    print(f'Flask-SQLAlchemy version: {flask_sqlalchemy.__version__}')
except ImportError:
    print('Flask-SQLAlchemy not installed')

try:
    import pymysql
    print(f'PyMySQL version: {pymysql.__version__}')
except ImportError:
    print('PyMySQL not installed')

try:
    import sqlalchemy
    print(f'SQLAlchemy version: {sqlalchemy.__version__}')
except ImportError:
    print('SQLAlchemy not installed')