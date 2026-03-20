import os
import sys
import subprocess

# 虚拟环境路径
venv_path = 'venv'
venv_python = os.path.join(venv_path, 'Scripts', 'python.exe')
venv_pip = os.path.join(venv_path, 'Scripts', 'pip.exe')

print(f'Virtual environment Python: {venv_python}')
print(f'Virtual environment pip: {venv_pip}')

# 检查虚拟环境是否存在
if not os.path.exists(venv_python):
    print('Virtual environment not found, creating...')
    subprocess.run([sys.executable, '-m', 'venv', venv_path], check=True)

# 安装依赖
print('Installing dependencies in virtual environment...')
dependencies = ['Flask', 'Flask-SQLAlchemy', 'PyMySQL', 'SQLAlchemy']
for dep in dependencies:
    print(f'Installing {dep}...')
    subprocess.run([venv_pip, 'install', dep], check=True)

print('All dependencies installed successfully in virtual environment!')

# 验证安装
try:
    # 激活虚拟环境并验证
    activate_script = os.path.join(venv_path, 'Scripts', 'activate.bat')
    verify_script = '''
    @echo off
    call "{activate_script}"
    python -c "import flask; print('Flask version:', flask.__version__)"
    python -c "import flask_sqlalchemy; print('Flask-SQLAlchemy version:', flask_sqlalchemy.__version__)"
    python -c "import pymysql; print('PyMySQL version:', pymysql.__version__)"
    python -c "import sqlalchemy; print('SQLAlchemy version:', sqlalchemy.__version__)"
    '''.format(activate_script=activate_script)
    
    with open('verify_env.bat', 'w') as f:
        f.write(verify_script)
    
    print('\nVerifying installation...')
    subprocess.run(['verify_env.bat'], check=True)
    
    # 清理临时文件
    os.remove('verify_env.bat')
    
    print('\nVerification successful!')
    print('You can now run the application using: venv\Scripts\python app.py')
    
except Exception as e:
    print(f'Error: {e}')