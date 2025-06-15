from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

def create_app(config_name='development'):
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///velib_tracker.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['DEBUG'] = os.environ.get('FLASK_ENV') == 'development'
    app.config['ENV'] = os.environ.get('FLASK_ENV', 'production')
    
    # SQLite optimizations for concurrent access
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_timeout': 10,
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'connect_args': {
            'timeout': 10,
            'check_same_thread': False
        }
    }
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Register blueprints
    from app.api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Register routes
    from app.routes import register_routes
    register_routes(app)
    
    # Create tables
    with app.app_context():
        db.create_all()
    
    return app