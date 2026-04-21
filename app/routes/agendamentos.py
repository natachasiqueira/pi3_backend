from flask import request, jsonify
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app.models import db, Agendamento, Servico, Funcionario, HorarioTrabalho, BloqueioAgenda, Usuario, LogAuditoria
from app.schemas import AgendamentoSchema
from app.models import CategoriaFinanceira, LancamentoFinanceiro
from marshmallow import ValidationError
from datetime import datetime, timedelta, time, date
import os
import pytz
import math

agendamentos_bp = Blueprint('agendamentos', __name__, url_prefix='/api/agendamentos', description='Motor de Agendamentos')

def get_now():
    tz = pytz.timezone(os.environ.get('TIMEZONE', 'America/Sao_Paulo'))
    return datetime.now(tz)

def arredondar_duracao(duracao_minutos):
    # Granularidade e arredondamento de slots de 30 minutos [RN-14]
    return math.ceil(duracao_minutos / 30) * 30

def time_to_minutes(t):
    return t.hour * 60 + t.minute

def minutes_to_time(m):
    return time(hour=m // 60, minute=m % 60)

def is_slot_available(id_funcionario, data_atendimento, inicio_minutos, fim_minutos, id_agendamento=None):
    # Concorrência e disponibilidade (evitar overbooking) [RN-03]
    conflitos = Agendamento.query.filter(
        Agendamento.id_funcionario == id_funcionario,
        Agendamento.data_atendimento == data_atendimento,
        Agendamento.status.in_(['AGENDADO', 'CONFIRMADO', 'REALIZADO'])
    )
    
    if id_agendamento:
        conflitos = conflitos.filter(Agendamento.id != id_agendamento)
        
    for a in conflitos.all():
        a_inicio = time_to_minutes(a.hora_inicio)
        a_fim = time_to_minutes(a.hora_fim)
        # Verificar sobreposição de horários
        if max(inicio_minutos, a_inicio) < min(fim_minutos, a_fim):
            return False
    return True

@agendamentos_bp.route('/disponibilidade', methods=['GET'])
@jwt_required()
def listar_disponibilidade():
    # Visualizar horários disponíveis [US-03]
    id_servico = request.args.get('id_servico', type=int)
    data_str = request.args.get('data') # DD/MM/AAAA [PD-01]
    
    if not id_servico or not data_str:
        return jsonify({"message": "Serviço e data são obrigatórios."}), 400
        
    try:
        # Ajustado para o padrão DD/MM/AAAA [PD-01]
        data_consulta = datetime.strptime(data_str, '%d/%m/%Y').date()
    except ValueError:
        return jsonify({"message": "Formato de data inválido. Use DD/MM/AAAA."}), 400

    servico = Servico.query.get_or_404(id_servico)
    duracao_efetiva = arredondar_duracao(servico.duracao_minutos)
    
    # Buscar profissionais por categoria de serviço [RN-04]
    funcionarios = Funcionario.query.filter(
        Funcionario.ativo == True,
        Funcionario.categorias.any(id=servico.id_categoria)
    ).all()
    
    if not funcionarios:
        return jsonify({"message": "Nenhum profissional disponível para este serviço."}), 404

    agora = get_now()
    disponibilidade_final = []

    for func in funcionarios:
        # Horário de trabalho e bloqueio de datas [RN-13]
        dia_semana = data_consulta.weekday() # 0-6
        horarios_trabalho = HorarioTrabalho.query.filter_by(
            id_funcionario=func.id, dia_semana=dia_semana
        ).all()
        
        bloqueio = BloqueioAgenda.query.filter_by(
            id_funcionario=func.id, data_bloqueio=data_consulta
        ).first()
        
        if not horarios_trabalho or bloqueio:
            continue

        slots_funcionario = []
        for h in horarios_trabalho:
            atual_minutos = time_to_minutes(h.hora_inicio)
            fim_jornada = time_to_minutes(h.hora_fim)
            
            while atual_minutos + duracao_efetiva <= fim_jornada:
                hora_inicio = minutes_to_time(atual_minutos)
                hora_fim = minutes_to_time(atual_minutos + duracao_efetiva)
                
                # Antecedência de 3 horas [RN-01]
                dt_inicio = datetime.combine(data_consulta, hora_inicio)
                dt_inicio = pytz.timezone(os.environ.get('TIMEZONE', 'America/Sao_Paulo')).localize(dt_inicio)
                
                if dt_inicio > agora + timedelta(hours=3):
                    # Overbooking (evitar sobreposição de horários) [RN-03]
                    if is_slot_available(func.id, data_consulta, atual_minutos, atual_minutos + duracao_efetiva):
                        slots_funcionario.append({
                            "hora_inicio": hora_inicio.strftime('%H:%M'), # [PD-01]
                            "hora_fim": hora_fim.strftime('%H:%M') # [PD-01]
                        })
                
                atual_minutos += 30 # Incremento fixo de 30 min conforme [RN-14]
        
        if slots_funcionario:
            disponibilidade_final.append({
                "id_funcionario": func.id,
                "nome_funcionario": func.usuario.nome_completo,
                "slots": slots_funcionario
            })

    # Ordenação por nome em caso de empate de horários [RN-04]
    disponibilidade_final.sort(key=lambda x: x['nome_funcionario'])

    if not disponibilidade_final:
        return jsonify({"message": "Não há horários disponíveis para esta data. Por favor, selecione outro dia."}), 404 # [MSG-07]

    return jsonify(disponibilidade_final), 200

@agendamentos_bp.route('', methods=['POST'])
@jwt_required()
def criar_agendamento():
    # Novo agendamento [US-03]
    claims = get_jwt()
    roles = claims.get("roles", [])
    
    # Cliente e admin podem realizar novos agendamentos [US-03]
    if "CLIENTE" not in roles and "ADMIN" not in roles:
        return jsonify({"message": "Acesso negado."}), 403

    schema = AgendamentoSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    # Determinar o id do cliente quando o agendamento for realizado pelo admin
    if "ADMIN" in roles:
        id_cliente = request.json.get('id_cliente')
        if not id_cliente:
            return jsonify({"message": "Para agendamentos feitos por admin, o campo 'id_cliente' é obrigatório."}), 400
        # Verificar se o cliente existe
        if not Usuario.query.get(id_cliente):
            return jsonify({"message": "Cliente não encontrado."}), 404
    else:
        id_cliente = int(get_jwt_identity())

    servico = Servico.query.get_or_404(data['id_servico'])
    duracao_efetiva = arredondar_duracao(servico.duracao_minutos)
    
    inicio_minutos = time_to_minutes(data['hora_inicio'])
    fim_minutos = inicio_minutos + duracao_efetiva
    hora_fim = minutes_to_time(fim_minutos)

    # Revalidação de regras no momento da criação
    agora = get_now()
    dt_inicio = datetime.combine(data['data_atendimento'], data['hora_inicio'])
    dt_inicio = pytz.timezone(os.environ.get('TIMEZONE', 'America/Sao_Paulo')).localize(dt_inicio)

    # Ignorar a antecedência de 3 horas [RN-01] para admin
    if "ADMIN" not in roles and dt_inicio <= agora + timedelta(hours=3):
        return jsonify({"message": "Agendamento para as próximas 3 horas? Gentileza ligar para (11) 98765-4321 e confirmar a disponibilidade."}), 400 # [MSG-05]

    if not is_slot_available(data['id_funcionario'], data['data_atendimento'], inicio_minutos, fim_minutos):
        return jsonify({"message": "Este horário acabou de ser reservado por outra pessoa. Por favor, escolha outro."}), 409 # [MSG-03]

    # Status inicial do agendamento [RN-07] e valor [RN-04]
    novo_agendamento = Agendamento(
        id_cliente=id_cliente,
        id_funcionario=data['id_funcionario'],
        id_servico=data['id_servico'],
        data_atendimento=data['data_atendimento'],
        hora_inicio=data['hora_inicio'],
        hora_fim=hora_fim,
        valor_aplicado=servico.valor,
        servico_aplicado=servico.nome_servico, 
        categoria_aplicada=servico.categoria.nome_categoria,
        status='AGENDADO'
    )
    
    db.session.add(novo_agendamento)
    db.session.flush()

    # Log de Auditoria [RN-05]
    id_usuario_logado = int(get_jwt_identity())
    usuario_logado = Usuario.query.get(id_usuario_logado)
    log = LogAuditoria(
        id_agendamento=novo_agendamento.id,
        status_anterior=None,
        status_novo='AGENDADO',
        id_responsavel=id_usuario_logado,
        nome_responsavel=usuario_logado.nome_completo
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"message": "Seu agendamento foi realizado com sucesso!"}), 201 # [MSG-11]

@agendamentos_bp.route('/meus', methods=['GET'])
@jwt_required()
def listar_meus_agendamentos():
    # Meus Agendamentos (cliente ou funcionário) [US-04, US-06]
    id_usuario = int(get_jwt_identity())
    claims = get_jwt()
    roles = claims.get("roles", [])

    query = Agendamento.query
    
    # [PRD] Se tiver role de cliente, verá seus agendamentos.
    # [PRD] Se tiver role de funcionário, verá sua agenda de trabalho.
    if "CLIENTE" in roles:
        query = query.filter_by(id_cliente=id_usuario)
    elif "FUNCIONARIO" in roles:
        func = Funcionario.query.filter_by(id_usuario=id_usuario).first()
        if not func: return jsonify([]), 200
        query = query.filter_by(id_funcionario=func.id)
    else:
        # Administradores usam a rota global de admin, não a área pessoal.
        return jsonify([]), 200
    
    # Filtros de data e status para a agenda pessoal [US-04.1, US-06.1]
    status = request.args.get('status')
    if status: query = query.filter_by(status=status)
    
    data_ini_str = request.args.get('data_inicio')
    if data_ini_str:
        try:
            # Mensagem de erro se fora do padrão DD/MM/AAAA [PD-01]
            data_ini = datetime.strptime(data_ini_str, '%d/%m/%Y').date()
            query = query.filter(Agendamento.data_atendimento >= data_ini)
        except ValueError:
            return jsonify({"message": "Formato de data inválido. Use DD/MM/AAAA."}), 400

    agendamentos = query.order_by(Agendamento.data_atendimento.desc(), Agendamento.hora_inicio.desc()).all()
    
    results = []
    for a in agendamentos:
        results.append({
            "id": a.id,
            "data": a.data_atendimento.strftime('%d/%m/%Y'), # [PD-01]
            "horario": f"{a.hora_inicio.strftime('%H:%M')} - {a.hora_fim.strftime('%H:%M')}", # [PD-01]
            "servico": a.servico.servico_aplicado, 
            "cliente": a.cliente.nome_completo,
            "funcionario": a.funcionario.usuario.nome_completo,
            "valor": f"R$ {a.valor_aplicado:,.2f}".replace('.', ','), # [PD-02]
            "status": a.status
        })

    return jsonify(results), 200

@agendamentos_bp.route('/<int:id>/status', methods=['PATCH'])
@jwt_required()
def mudar_status(id):
    agendamento = Agendamento.query.get_or_404(id)
    id_usuario = int(get_jwt_identity())
    usuario_logado = Usuario.query.get(id_usuario)
    claims = get_jwt()
    roles = claims.get("roles", [])
    
    novo_status = request.json.get('status')
    status_anterior = agendamento.status
    agora = get_now()

    # Regra de status do admin [US-12.3]
    if "ADMIN" in roles:
        if novo_status in ['REALIZADO', 'AUSENTE']:
            dt_atendimento = datetime.combine(agendamento.data_atendimento, agendamento.hora_inicio)
            dt_atendimento = pytz.timezone(os.environ.get('TIMEZONE', 'America/Sao_Paulo')).localize(dt_atendimento)
            if agora < dt_atendimento:
                return jsonify({"message": "Status só pode ser marcado após o horário do atendimento."}), 400
        # Admin pode CANCELAR ou CONFIRMAR sem restrição de 2h
        pass

    # Regra de status do cliente [RN-08]
    elif "CLIENTE" in roles:
        if agendamento.id_cliente != id_usuario:
            return jsonify({"message": "Acesso negado."}), 403
        
        if novo_status == 'CANCELADO':
            # [RN-02] Antecedência de 2 horas para cancelamento
            dt_atendimento = datetime.combine(agendamento.data_atendimento, agendamento.hora_inicio)
            dt_atendimento = pytz.timezone(os.environ.get('TIMEZONE', 'America/Sao_Paulo')).localize(dt_atendimento)
            if dt_atendimento < agora + timedelta(hours=2):
                return jsonify({"message": "Este cancelamento precisa ser realizado por telefone. Gentileza ligar para (11) 98765-4321."}), 400 # [MSG-06]
            
            if status_anterior not in ['AGENDADO', 'CONFIRMADO']:
                return jsonify({"message": "Transição de status inválida para cliente."}), 400
        elif novo_status == 'CONFIRMADO':
            if status_anterior != 'AGENDADO':
                return jsonify({"message": "Transição de status inválida para cliente."}), 400
        else:
            return jsonify({"message": "Cliente não tem permissão para este status."}), 403

    # Regra de status do funcionário [RN-09]
    elif "FUNCIONARIO" in roles:
        if novo_status in ['REALIZADO', 'AUSENTE']:
            dt_atendimento = datetime.combine(agendamento.data_atendimento, agendamento.hora_inicio)
            dt_atendimento = pytz.timezone(os.environ.get('TIMEZONE', 'America/Sao_Paulo')).localize(dt_atendimento)
            if agora < dt_atendimento:
                return jsonify({"message": "Status só pode ser marcado após o horário do atendimento."}), 400
        else:
            return jsonify({"message": "Funcionário não tem permissão para este status."}), 403

    # Atualizar status
    agendamento.status = novo_status
    
    # Auditoria [RN-05]
    log = LogAuditoria(
        id_agendamento=agendamento.id,
        status_anterior=status_anterior,
        status_novo=novo_status,
        id_responsavel=id_usuario,
        nome_responsavel=usuario_logado.nome_completo
    )
    db.session.add(log)

    # Gerar receita a partir do agendamento [RN-10]
    if novo_status == 'REALIZADO':
        from app.models import CategoriaFinanceira, LancamentoFinanceiro
        cat_receita = CategoriaFinanceira.query.filter_by(nome_categoria='Serviços Realizados').first()
        if cat_receita:
            lancamento = LancamentoFinanceiro(
                id_categoria_financeira=cat_receita.id,
                id_agendamento=agendamento.id,
                nome_lancamento=f"Receita: {agendamento.servico.servico_aplicado} - {agendamento.cliente.nome_completo}",
                valor=agendamento.valor_aplicado,
                status_pagamento='PENDENTE' # [RN-12]
            )
            db.session.add(lancamento)

    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 200 # [MSG-09]
