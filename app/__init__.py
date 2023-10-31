from flask import Flask
from app.routes import bp as routes_bp

def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_pyfile('instance\\config.py')  

    from app import routes
    app.register_blueprint(routes_bp)

    return app

