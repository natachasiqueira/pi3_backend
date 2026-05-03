from flask import request, jsonify
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt
from app.models import db, CategoriaServico, Servico, Funcionario, Usuario, HorarioTrabalho, BloqueioAgenda, Agendamento
from app.schemas import CategoriaServicoSchema, ServicoSchema, FuncionarioSchema, HorarioTrabalhoSchema, BloqueioAgendaSchema, UsuarioSchema, UpdatePerfilSchema
from marshmallow import ValidationError
from functools import wraps

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin', description='Administração do Sistema')

# Decorador para restringir acesso apenas a ADMIN [PRD - Seção 2]
def admin_required():
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorator(*args, **kwargs):
            claims = get_jwt()
            roles = claims.get("roles", [])
            if "ADMIN" not in roles:
                return jsonify({"message": "Acesso restrito a administradores."}), 403
            return fn(*args, **kwargs)
        return decorator
    return wrapper


# CATEGORIAS E SERVIÇOS [US-09]

@admin_bp.route('/categorias', methods=['GET'])
@jwt_required()
def listar_categorias():
    somente_ativos = request.args.get('somente_ativos')
    query = CategoriaServico.query
    if somente_ativos == 'true':
        query = query.filter_by(ativo=True)

    categorias = query.all()
    schema = CategoriaServicoSchema(many=True)
    return jsonify(schema.dump(categorias)), 200

@admin_bp.route('/categorias', methods=['POST'])
@admin_required()
def criar_categoria():
    schema = CategoriaServicoSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    if CategoriaServico.query.filter_by(nome_categoria=data['nome_categoria']).first():
        return jsonify({"message": "Categoria já existe."}), 409

    nova_categoria = CategoriaServico(nome_categoria=data['nome_categoria'])
    db.session.add(nova_categoria)
    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 201

@admin_bp.route('/categorias/<int:id>', methods=['PUT'])
@admin_required()
def editar_categoria(id):
    categoria = CategoriaServico.query.get_or_404(id)
    schema = CategoriaServicoSchema(partial=True)
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    if 'nome_categoria' in data:
        # Verifica duplicidade
        existente = CategoriaServico.query.filter_by(nome_categoria=data['nome_categoria']).first()
        if existente and existente.id != categoria.id:
            return jsonify({"message": "Categoria já existe."}), 409
        categoria.nome_categoria = data['nome_categoria']
    if 'ativo' in data:
        categoria.ativo = data['ativo']
        # Se a categoria for desativada, desativará os serviços abaixo dela
        if not data['ativo']:
            for servico in categoria.servicos:
                servico.ativo = False
        
    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 200 # [MSG-09]

@admin_bp.route('/servicos', methods=['GET'])
@jwt_required()
def listar_servicos():
    # Paginação de 50 itens [RI-08]
    page = request.args.get('page', 1, type=int)
    per_page = 50
    somente_ativos = request.args.get('somente_ativos')
    
    query = Servico.query.join(CategoriaServico)
    
    # Filtra somente serviços ativos
    if somente_ativos == 'true':
        query = query.filter_by(ativo=True)

    servicos_pagination = Servico.query.paginate(page=page, per_page=per_page)
    schema = ServicoSchema(many=True)
    
    return jsonify({
        "items": schema.dump(servicos_pagination.items),
        "total": servicos_pagination.total,
        "pages": servicos_pagination.pages,
        "current_page": servicos_pagination.page
    }), 200

@admin_bp.route('/servicos', methods=['POST'])
@admin_required()
def criar_servico():
    schema = ServicoSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    categoria_alvo = CategoriaServico.query.get(data['id_categoria'])
    if categoria_alvo and not categoria_alvo.ativo:
        return jsonify({"message": "Não é possível criar um serviço em uma categoria inativada."}), 400

    novo_servico = Servico(
        id_categoria=data['id_categoria'],
        nome_servico=data['nome_servico'],
        duracao_minutos=data['duracao_minutos'],
        valor=data['valor']
    )
    db.session.add(novo_servico)
    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 201

@admin_bp.route('/servicos/<int:id>', methods=['PUT'])
@admin_required()
def editar_servico(id):
    servico = Servico.query.get_or_404(id)
    schema = ServicoSchema(partial=True)
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    if novo_status_ativo:
        categoria_alvo = CategoriaServico.query.get(nova_categoria_id)
        if categoria_alvo and not categoria_alvo.ativo:
            return jsonify({"message": "Este serviço está atrelado a uma categoria inativada. Você precisa mudar a categoria do serviço ou ativar a categoria primeiro."}), 400

    if 'id_categoria' in data: servico.id_categoria = data['id_categoria']
    if 'nome_servico' in data: servico.nome_servico = data['nome_servico']
    if 'duracao_minutos' in data: servico.duracao_minutos = data['duracao_minutos']
    if 'valor' in data: servico.valor = data['valor']
    if 'ativo' in data: servico.ativo = data['ativo']

    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 200


# FUNCIONÁRIOS [US-10]

@admin_bp.route('/funcionarios', methods=['GET'])
@admin_required()
def listar_funcionarios():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    query = Funcionario.query.join(Usuario)
    
    # Filtros de Funcionários [US-10]
    nome = request.args.get('nome')
    if nome: query = query.filter(Usuario.nome_completo.ilike(f'%{nome}%'))
    
    telefone = request.args.get('telefone')
    if telefone: query = query.filter(Usuario.telefone.ilike(f'%{telefone}%'))
    
    email = request.args.get('email')
    if email: query = query.filter(Usuario.email.ilike(f'%{email}%'))
    
    data_cadastro = request.args.get('data_cadastro')
    if data_cadastro:
        try:
            from datetime import datetime
            dc = datetime.strptime(data_cadastro, '%d/%m/%Y').date()
            query = query.filter(func.date(Usuario.data_criacao) == dc)
        except ValueError:
            return jsonify({"message": "Formato de data inválido. Use DD/MM/AAAA."}), 400

    query = query.order_by(Usuario.nome_completo.asc())

    funcionarios_pagination = query.paginate(page=page, per_page=per_page)
    
    results = []
    for f in funcionarios_pagination.items:
        results.append({
            "id": f.id,
            "id_usuario": f.id_usuario,
            "nome_completo": f.usuario.nome_completo,
            "email": f.usuario.email,
            "telefone": f.usuario.telefone,
            "ativo": f.ativo,
            "categorias": [{"id": c.id, "nome": c.nome_categoria} for c in f.categorias]
        })

    return jsonify({
        "items": results,
        "total": funcionarios_pagination.total,
        "pages": funcionarios_pagination.pages,
        "current_page": funcionarios_pagination.page
    }), 200

@admin_bp.route('/funcionarios/<int:id>', methods=['GET'])
@admin_required()
def obter_funcionario(id):
    # Obter dados de um funcionário específico [US-10]
    f = Funcionario.query.get_or_404(id)
    return jsonify({
        "id": f.id,
        "id_usuario": f.id_usuario,
        "nome_completo": f.usuario.nome_completo,
        "email": f.usuario.email,
        "telefone": f.usuario.telefone,
        "ativo": f.ativo,
        "categorias": [{"id": c.id, "nome": c.nome_categoria} for c in f.categorias]
    }), 200

@admin_bp.route('/funcionarios', methods=['POST'])
@admin_required()
def criar_funcionario():
    schema = FuncionarioSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    # 1. Verificar se usuário já existe [MSG-02]
    if Usuario.query.filter_by(email=data['email']).first():
        return jsonify({"message": "Este e-mail já está cadastrado em nosso sistema. Clique aqui para realizar o login."}), 409

    from werkzeug.security import generate_password_hash
    
    # 2. Criar Usuário com role FUNCIONARIO
    novo_usuario = Usuario(
        nome_completo=data['nome_completo'],
        email=data['email'],
        telefone=data['telefone'],
        senha=generate_password_hash(data['senha']),
        role='FUNCIONARIO'
    )
    db.session.add(novo_usuario)
    db.session.flush()

    # 3. Criar vínculo na tabela Funcionário
    novo_func = Funcionario(id_usuario=novo_usuario.id, ativo=True)
    
    # 4. Vínculo com categorias (Especialidades N:N) [US-10.3]
    ids_categorias = data.get('ids_categorias', [])
    if ids_categorias:
        categorias = CategoriaServico.query.filter(CategoriaServico.id.in_(ids_categorias)).all()
        novo_func.categorias = categorias

    db.session.add(novo_func)
    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 201

@admin_bp.route('/funcionarios/<int:id>', methods=['PUT'])
@admin_required()
def editar_funcionario_admin(id):
    # Edição de dados do funcionário pelo Admin [US-10]
    funcionario = Funcionario.query.get_or_404(id)
    usuario = funcionario.usuario
    
    schema = UpdatePerfilSchema(partial=True, unknown='exclude')
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    if 'nome_completo' in data: usuario.nome_completo = data['nome_completo']
    if 'email' in data:
        existente = Usuario.query.filter_by(email=data['email']).first()
        if existente and existente.id != usuario.id:
            return jsonify({"message": "E-mail já em uso por outro usuário."}), 409
        usuario.email = data['email']
    if 'telefone' in data: usuario.telefone = data['telefone']
    if 'ativo' in request.json: funcionario.ativo = request.json.get('ativo')
    
    # Vincular categorias via checkbox [US-10.3]
    ids_categorias = request.json.get('ids_categorias')
    if ids_categorias is not None:
        categorias = CategoriaServico.query.filter(CategoriaServico.id.in_(ids_categorias)).all()
        funcionario.categorias = categorias

    # Alteração manual de senha pelo Admin [US-10]
    if 'nova_senha' in data:
        from werkzeug.security import generate_password_hash
        usuario.senha = generate_password_hash(data['nova_senha'])

    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 200 # [MSG-09]

@admin_bp.route('/funcionarios/<int:id>/horarios', methods=['GET'])
@admin_required()
def obter_horarios_funcionario(id):
    # Visualizar horários de trabalho atuais de um funcionário [US-10]
    # Verifica se o funcionário existe
    Funcionario.query.get_or_404(id)
    
    # Busca os horários ordenados por dia da semana e hora de início
    horarios = HorarioTrabalho.query.filter_by(id_funcionario=id)\
        .order_by(HorarioTrabalho.dia_semana.asc(), HorarioTrabalho.hora_inicio.asc()).all()
    
    schema = HorarioTrabalhoSchema(many=True)
    return jsonify(schema.dump(horarios)), 200

@admin_bp.route('/funcionarios/<int:id>/horarios', methods=['POST'])
@admin_required()
def configurar_horarios(id):
    funcionario = Funcionario.query.get_or_404(id)
    schema = HorarioTrabalhoSchema(many=True)
    try:
        horarios_data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    # Limpa horários antigos para redefinir
    HorarioTrabalho.query.filter_by(id_funcionario=id).delete()
    
    for h in horarios_data:
        novo_horario = HorarioTrabalho(
            id_funcionario=id,
            dia_semana=h['dia_semana'],
            hora_inicio=h['hora_inicio'],
            hora_fim=h['hora_fim']
        )
        db.session.add(novo_horario)
    
    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 200

@admin_bp.route('/funcionarios/<int:id>/bloqueios', methods=['POST'])
@admin_required()
def adicionar_bloqueio(id):
    funcionario = Funcionario.query.get_or_404(id)
    schema = BloqueioAgendaSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    novo_bloqueio = BloqueioAgenda(
        id_funcionario=id,
        data_bloqueio=data['data_bloqueio'],
        motivo=data.get('motivo')
    )
    db.session.add(novo_bloqueio)
    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 201


# CLIENTES [US-11]

@admin_bp.route('/clientes', methods=['GET'])
@admin_required()
def listar_clientes():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    query = Usuario.query.filter(Usuario.role.contains('CLIENTE'))
    
    # Filtros de Clientes [US-11]
    nome = request.args.get('nome')
    if nome: query = query.filter(Usuario.nome_completo.ilike(f'%{nome}%'))
    
    telefone = request.args.get('telefone')
    if telefone: query = query.filter(Usuario.telefone.ilike(f'%{telefone}%'))
    
    email = request.args.get('email')
    if email: query = query.filter(Usuario.email.ilike(f'%{email}%'))
    
    data_cadastro = request.args.get('data_cadastro')
    if data_cadastro:
        try:
            from datetime import datetime
            dc = datetime.strptime(data_cadastro, '%d/%m/%Y').date()
            query = query.filter(func.date(Usuario.data_criacao) == dc)
        except ValueError:
            return jsonify({"message": "Formato de data inválido. Use DD/MM/AAAA."}), 400

    query = query.order_by(Usuario.nome_completo.asc())

    clientes_pagination = query.paginate(page=page, per_page=per_page)
    
    schema = UsuarioSchema(many=True)
    return jsonify({
        "items": schema.dump(clientes_pagination.items),
        "total": clientes_pagination.total,
        "pages": clientes_pagination.pages,
        "current_page": clientes_pagination.page
    }), 200

@admin_bp.route('/clientes', methods=['POST'])
@admin_required()
def criar_cliente_admin():
    # Cadastro de cliente pelo Admin [US-11]
    schema = UsuarioSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    if Usuario.query.filter_by(email=data['email']).first():
        return jsonify({"message": "Este e-mail já está cadastrado em nosso sistema. Clique aqui para realizar o login."}), 409

    from werkzeug.security import generate_password_hash
    
    novo_cliente = Usuario(
        nome_completo=data['nome_completo'],
        email=data['email'],
        telefone=data['telefone'],
        senha=generate_password_hash(data['senha']),
        role='CLIENTE'
    )
    db.session.add(novo_cliente)
    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 201

@admin_bp.route('/clientes/<int:id>', methods=['PUT'])
@admin_required()
def editar_cliente_admin(id):
    # Edição de dados do perfil pelo Admin [US-11]
    # Filtra por ID e garante que o usuário tenha a role CLIENTE
    usuario = Usuario.query.filter(Usuario.id == id, Usuario.role.contains('CLIENTE')).first_or_404()
    schema = UpdatePerfilSchema(partial=True)
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    if 'nome_completo' in data: usuario.nome_completo = data['nome_completo']
    if 'email' in data:
        existente = Usuario.query.filter_by(email=data['email']).first()
        if existente and existente.id != usuario.id:
            return jsonify({"message": "E-mail já em uso por outro usuário."}), 409
        usuario.email = data['email']
    if 'telefone' in data: usuario.telefone = data['telefone']
    
    # Alteração manual de senha pelo Admin [US-11]
    if 'nova_senha' in data:
        from werkzeug.security import generate_password_hash
        usuario.senha = generate_password_hash(data['nova_senha'])

    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 200 # [MSG-09]


# AGENDAMENTOS [US-12]

@admin_bp.route('/agendamentos', methods=['GET'])
@admin_required()
def listar_todos_agendamentos():
    # Visão Global de Agendamentos [US-12]
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    query = Agendamento.query.join(Servico)
    
    # Filtros combinados [US-12.2]
    status = request.args.get('status')
    if status: query = query.filter(Agendamento.status == status)
    
    id_cliente = request.args.get('id_cliente', type=int)
    if id_cliente: query = query.filter(Agendamento.id_cliente == id_cliente)
    
    id_funcionario = request.args.get('id_funcionario', type=int)
    if id_funcionario: query = query.filter(Agendamento.id_funcionario == id_funcionario)
    
    id_servico = request.args.get('id_servico', type=int)
    if id_servico: query = query.filter(Agendamento.id_servico == id_servico)
    
    id_categoria = request.args.get('id_categoria', type=int)
    if id_categoria: query = query.filter(Servico.id_categoria == id_categoria)
    
    data_atendimento = request.args.get('data_atendimento')
    if data_atendimento:
        try:
            from datetime import datetime
            da = datetime.strptime(data_atendimento, '%d/%m/%Y').date()
            query = query.filter(Agendamento.data_atendimento == da)
        except ValueError:
            return jsonify({"message": "Formato de data inválido. Use DD/MM/AAAA."}), 400

    agendamentos_pagination = query.order_by(Agendamento.data_atendimento.desc()).paginate(page=page, per_page=per_page)
    
    results = []
    for a in agendamentos_pagination.items:
        results.append({
            "id": a.id,
            "data": a.data_atendimento.strftime('%d/%m/%Y'),
            "horario": f"{a.hora_inicio.strftime('%H:%M')} - {a.hora_fim.strftime('%H:%M')}",
            "servico": a.servico_aplicado,
            "cliente": a.cliente.nome_completo,
            "funcionario": a.funcionario.usuario.nome_completo,
            "valor": f"R$ {a.valor_aplicado:,.2f}".replace('.', ','),
            "status": a.status
        })

    return jsonify({
        "items": results,
        "total": agendamentos_pagination.total,
        "pages": agendamentos_pagination.pages,
        "current_page": agendamentos_pagination.page
    }), 200