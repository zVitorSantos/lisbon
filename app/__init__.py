from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import verify 
from flask import Flask
from app.routes import bp as routes_bp

def run_verify_script():
    verify.buscar_pdf() 

def create_app():
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_pyfile('instance\\config.py')  

    # Inicializa o agendador
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=run_verify_script, trigger="interval", days=1, start_date='2023-10-31 14:50:00')
    scheduler.start()

    # Encerra o agendador se o web app for encerrado
    atexit.register(lambda: scheduler.shutdown())

    from app import routes
    app.register_blueprint(routes_bp)

    return app
