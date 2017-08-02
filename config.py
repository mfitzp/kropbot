import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    DEBUG = True
    TESTING = False
    CSRF_ENABLED = True
    # This secret key should be replaced in production (overwrite via env var)
    SECRET_KEY = os.environ.get('SECRET_KEY', '4;,(218ca}Ok,A3i1k.]h6v2{*y2@lI>UI1|NlX2JRE#W7j7x,"JS}4!^2MrVPw')
    # Env var to replace database URL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///sqlite.db')
    # Secret endpoint for robot WS
    ROBOT_WS_SECRET = os.getenv('ROBOT_WS_SECRET', '')