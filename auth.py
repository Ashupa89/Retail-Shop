from flask import Blueprint, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.form
    user = User.query.filter_by(username=data.get('username')).first()
    if not user or not check_password_hash(user.password_hash, data.get('password','')):
        return {'error': 'Invalid credentials'}, 401
    session['user_id'] = user.id
    session['is_admin'] = user.is_admin
    return {'ok': True}

@auth_bp.route('/register-admin')
def register_admin():
    if User.query.first():
        return {'error': 'Already initialized'}, 400
    pw = generate_password_hash('admin')
    u = User(username='admin', password_hash=pw, is_admin=True)
    db.session.add(u); db.session.commit()
    return {'ok': True}
