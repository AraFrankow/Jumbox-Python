import os
from flask import Flask, render_template
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

bcrypt = Bcrypt()

def create_app():
    load_dotenv()

    app = Flask(__name__, static_folder='../static')
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "clave_secreta_super_segura")
    app.config["DB_NAME"] = "jumbox.db"

    bcrypt.init_app(app)

    # Registrar blueprints
    from .main.routes import main_bp
    from .auth.routes import auth_bp
    from .user.routes import user_bp
    from .sucursal.routes import sucursal_bp
    from .admin.routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(sucursal_bp)
    app.register_blueprint(admin_bp)

    @app.errorhandler(404)
    def pagina_no_encontrada(e):
        return render_template('404.html'), 404

    @app.errorhandler(405)
    def metodo_no_permitido(e):
        return render_template('404.html'), 405

    return app