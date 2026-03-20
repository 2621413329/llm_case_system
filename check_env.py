import sys
import os

print('Python executable:', sys.executable)
print('Python version:', sys.version)
print('Python path:', sys.path)

# 检查pip
try:
    import pip
    print('Pip version:', pip.__version__)
    print('Pip location:', os.path.dirname(pip.__file__))
except ImportError:
    print('Pip not found')

# 检查环境变量
print('\nEnvironment variables:')
if 'PATH' in os.environ:
    print('PATH:', os.environ['PATH'])

if 'PYTHONPATH' in os.environ:
    print('PYTHONPATH:', os.environ['PYTHONPATH'])