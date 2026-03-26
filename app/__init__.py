from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_smorest import Api
from dotenv import load_dotenv
import os

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)

    # Configurações para flask-smorest / Swagger
    app.config['API_TITLE'] = 'Sistema de Agendamento PI3 API'
    app.config['API_VERSION'] = 'v1'
    app.config['OPENAPI_VERSION'] = '3.0.3'
    app.config['OPENAPI_URL_PREFIX'] = '/'
    app.config['OPENAPI_SWAGGER_UI_PATH'] = '/swagger'
    app.config['OPENAPI_SWAGGER_UI_URL'] = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist/'
    app.config['OPENAPI_JSON_PATH'] = 'api-spec.json'

    # Configurações de Banco e JWT
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY')
    app.config['TIMEZONE'] = os.environ.get('TIMEZONE', 'America/Sao_Paulo')

    # Inicialização das extensões
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    api = Api(app)

    # Registro de Blueprints via Smorest API
    from run.routes.auth import auth_bp
    from run.routes.admin import admin_bp
    from run.routes.agendamentos import agendamentos_bp
    from run.routes.financeiro import financeiro_bp
    
    api.register_blueprint(auth_bp)
    api.register_blueprint(admin_bp)
    api.register_blueprint(agendamentos_bp)
    api.register_blueprint(financeiro_bp)

    # Importação dos models para o Migrate
    from run.models import (
        Usuario, Funcionario, CategoriaServico, Servico, 
        HorarioTrabalho, BloqueioAgenda, Agendamento, 
        CategoriaFinanceira, LancamentoFinanceiro, LogAuditoria
    )

    @app.route('/')
    def index():
        return {"message": "API do Sistema de Agendamento PI3 operacional. Acesse /swagger para documentação."}, 200

    return app
