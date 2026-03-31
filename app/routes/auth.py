from flask import request, jsonify
from flask_smorest import Blueprint
from flask_jwt_extended import (
    create_access_token, get_jwt_identity, jwt_required, 
    get_jwt
)
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import Usuario, db
from app.schemas import UsuarioSchema, LoginSchema, UpdatePerfilSchema
from marshmallow import ValidationError
from datetime import timedelta

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth', description='Autenticação e Perfil')

@auth_bp.route('/cadastro', methods=['POST'])
def cadastro():
    schema = UsuarioSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    # Validação de Senha Dupla [RI-09, MSG-08]
    if data['senha'] != data['confirmar_senha']:
        return jsonify({"message": "As senhas informadas não coincidem. Verifique e tente novamente."}), 400

    # Verificar e-mail duplicado [MSG-02]
    if Usuario.query.filter_by(email=data['email']).first():
        return jsonify({"message": "Este e-mail já está cadastrado em nosso sistema. Clique aqui para realizar o login."}), 409

    # Criar novo usuário como cliente por padrão [US-01]
    novo_usuario = Usuario(
        nome_completo=data['nome_completo'],
        email=data['email'],
        telefone=data['telefone'],
        senha=generate_password_hash(data['senha']),
        role='CLIENTE'
    )

    db.session.add(novo_usuario)
    db.session.commit()

    return jsonify({"message": "Conta criada com sucesso! Faça login para continuar."}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    schema = LoginSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    usuario = Usuario.query.filter_by(email=data['email']).first()

    # Validar credenciais [MSG-01]
    if not usuario or not check_password_hash(usuario.senha, data['senha']):
        return jsonify({"message": "E-mail ou senha inválidos. Tente novamente."}), 401

    # Gerar Token com 30 min de expiração [RNF-08]
    access_token = create_access_token(
        identity=str(usuario.id), 
        additional_claims={"roles": usuario.roles_list},
        expires_delta=timedelta(minutes=30)
    )

    return jsonify({
        "access_token": access_token,
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome_completo,
            "roles": usuario.roles_list
        }
    }), 200

@auth_bp.route('/perfil', methods=['GET'])
@jwt_required()
def get_perfil():
    id_usuario = get_jwt_identity()
    usuario = Usuario.query.get(id_usuario)
    
    if not usuario:
        return jsonify({"message": "Usuário não encontrado."}), 404

    return jsonify({
        "id": usuario.id,
        "nome_completo": usuario.nome_completo,
        "email": usuario.email,
        "telefone": usuario.telefone,
        "roles": usuario.roles_list
    }), 200

@auth_bp.route('/perfil', methods=['PUT'])
@jwt_required()
def update_perfil():
    id_usuario = get_jwt_identity()
    usuario = Usuario.query.get(id_usuario)
    
    schema = UpdatePerfilSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    # Atualizar dados básicos
    if 'nome_completo' in data:
        usuario.nome_completo = data['nome_completo']
    if 'email' in data:
        # Verificar se novo e-mail já existe em outro usuário
        existente = Usuario.query.filter_by(email=data['email']).first()
        if existente and existente.id != usuario.id:
            return jsonify({"message": "E-mail já em uso por outro usuário."}), 409
        usuario.email = data['email']
    if 'telefone' in data:
        usuario.telefone = data['telefone']

    # Atualizar senha se fornecida [RI-09]
    if 'nova_senha' in data:
        # Validação de senha dupla [RI-09, MSG-08]
        if data['nova_senha'] != data.get('confirmar_nova_senha'):
            return jsonify({"message": "As senhas informadas não coincidem. Verifique e tente novamente."}), 400
            
        if not data.get('senha_atual') or not check_password_hash(usuario.senha, data['senha_atual']):
            return jsonify({"message": "Senha atual incorreta."}), 401
        usuario.senha = generate_password_hash(data['nova_senha'])

    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 200

@auth_bp.route('/excluir-conta', methods=['DELETE'])
@jwt_required()
def excluir_conta():
    id_usuario = get_jwt_identity()
    usuario = Usuario.query.get(id_usuario)

    if not usuario:
        return jsonify({"message": "Usuário não encontrado."}), 404

    # Padrão de Anonimização [RN-11]
    usuario.nome_completo = "Anonimizado"
    usuario.email = f"{usuario.id}@anonimizado.com"
    usuario.telefone = "(00) 00000-0000"
    usuario.senha = "Anonimizado123"
    # A role permanece a mesma conforme RN-11 para manter integridade
    
    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 200
