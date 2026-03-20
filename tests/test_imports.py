try:
    import flask
    import sqlalchemy
    import pymysql
    import flask_sqlalchemy
    print('All imports successful!')
    print(f'Flask version: {flask.__version__}')
    print(f'SQLAlchemy version: {sqlalchemy.__version__}')
except Exception as e:
    print(f'Import error: {e}')

