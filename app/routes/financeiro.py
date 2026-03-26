from flask import request, jsonify
from flask_smorest import Blueprint
from flask_jwt_extended import jwt_required, get_jwt
from app.models import db, LancamentoFinanceiro, LogAuditoria, Agendamento, CategoriaFinanceira, Servico, Funcionario, Usuario
from app.schemas import LancamentoFinanceiroSchema, LogAuditoriaSchema
from marshmallow import ValidationError
from datetime import datetime
from sqlalchemy import func
import os
import pytz

financeiro_bp = Blueprint('financeiro', __name__, url_prefix='/api/financeiro', description='Gestão Financeira e Dashboards')

def get_now():
    tz = pytz.timezone(os.environ.get('TIMEZONE', 'America/Sao_Paulo'))
    return datetime.now(tz)

# --- GESTÃO FINANCEIRA [US-15] ---

@financeiro_bp.route('/lancamentos', methods=['GET'])
@jwt_required()
def listar_lancamentos():
    claims = get_jwt()
    roles = claims.get("roles", [])
    if "ADMIN" not in roles:
        return jsonify({"message": "Acesso restrito a administradores."}), 403

    # RI-08: Paginação de 50 itens
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    query = LancamentoFinanceiro.query
    
    # Filtros [US-15.3]
    id_categoria_financeira = request.args.get('id_categoria_financeira', type=int)
    if id_categoria_financeira:
        query = query.filter_by(id_categoria_financeira=id_categoria_financeira)
        
    data_inicio = request.args.get('data_inicio')
    if data_inicio:
        try:
            di = datetime.strptime(data_inicio, '%d/%m/%Y').date()
            query = query.filter(func.date(LancamentoFinanceiro.data_criacao) >= di)
        except ValueError:
            return jsonify({"message": "Formato de data inválido. Use DD/MM/AAAA."}), 400

    forma_pagamento = request.args.get('forma_pagamento')
    if forma_pagamento:
        query = query.filter_by(forma_pagamento=forma_pagamento)

    lancamentos_pagination = query.order_by(LancamentoFinanceiro.data_criacao.desc()).paginate(page=page, per_page=per_page)
    
    schema = LancamentoFinanceiroSchema(many=True)
    
    return jsonify({
        "items": schema.dump(lancamentos_pagination.items),
        "total": lancamentos_pagination.total,
        "pages": lancamentos_pagination.pages,
        "current_page": lancamentos_pagination.page
    }), 200

@financeiro_bp.route('/lancamentos/<int:id>/pagamento', methods=['PATCH'])
@jwt_required()
def conciliar_pagamento(id):
    claims = get_jwt()
    roles = claims.get("roles", [])
    if "ADMIN" not in roles:
        return jsonify({"message": "Acesso restrito a administradores."}), 403

    lancamento = LancamentoFinanceiro.query.get_or_404(id)
    schema = LancamentoFinanceiroSchema(only=['forma_pagamento'])
    
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 400

    # Complementar a transação [US-15.2, PD-07]
    lancamento.forma_pagamento = data['forma_pagamento']
    lancamento.status_pagamento = 'PAGO'
    lancamento.data_pagamento = get_now()

    db.session.commit()
    return jsonify({"message": "Operação realizada com sucesso!"}), 200 # [MSG-09]

# --- DASHBOARDS [US-13, US-16] ---

@financeiro_bp.route('/dashboard/operacional', methods=['GET'])
@jwt_required()
def dashboard_operacional():
    claims = get_jwt()
    roles = claims.get("roles", [])
    if "ADMIN" not in roles:
        return jsonify({"message": "Acesso restrito a administradores."}), 403

    # 1. Total de atendimentos por status (inclui cancelamentos e ausências)
    status_counts = db.session.query(Agendamento.status, func.count(Agendamento.id)).group_by(Agendamento.status).all()
    
    # 2. Serviços mais realizados
    servicos_populares = db.session.query(
        Servico.nome_servico, func.count(Agendamento.id).label('total')
    ).join(Agendamento).group_by(Servico.id).order_by(func.count(Agendamento.id).desc()).limit(5).all()

    # 3. Serviços com maior duração [US-13]
    servicos_longos = Servico.query.order_by(Servico.duracao_minutos.desc()).limit(5).all()

    # 4. Dias de maior demanda (baseado em agendamentos) [US-13]
    dias_demanda = db.session.query(
        func.to_char(Agendamento.data_atendimento, 'Day').label('dia'), 
        func.count(Agendamento.id)
    ).group_by('dia').order_by(func.count(Agendamento.id).desc()).all()

    # 5. Horários de maior demanda [US-13]
    horarios_demanda = db.session.query(
        Agendamento.hora_inicio, func.count(Agendamento.id)
    ).group_by(Agendamento.hora_inicio).order_by(func.count(Agendamento.id).desc()).limit(5).all()

    return jsonify({
        "atendimentos_por_status": dict(status_counts),
        "servicos_mais_realizados": [{"servico": s[0], "total": s[1]} for s in servicos_populares],
        "servicos_maior_duracao": [{"servico": s.nome_servico, "duracao": s.duracao_minutos} for s in servicos_longos],
        "dias_maior_demanda": [{"dia": d[0].strip(), "total": d[1]} for d in dias_demanda],
        "horarios_maior_demanda": [{"horario": h[0].strftime('%H:%M'), "total": h[1]} for h in horarios_demanda]
    }), 200

@financeiro_bp.route('/dashboard/financeiro', methods=['GET'])
@jwt_required()
def dashboard_financeiro():
    claims = get_jwt()
    roles = claims.get("roles", [])
    if "ADMIN" not in roles:
        return jsonify({"message": "Acesso restrito a administradores."}), 403

    # Filtro de período opcional [US-16]
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    
    query_base = LancamentoFinanceiro.query.filter(LancamentoFinanceiro.status_pagamento == 'PAGO')
    query_agendamentos = Agendamento.query.filter(Agendamento.status == 'REALIZADO')

    if data_inicio:
        di = datetime.strptime(data_inicio, '%d/%m/%Y').date()
        query_base = query_base.filter(func.date(LancamentoFinanceiro.data_pagamento) >= di)
        query_agendamentos = query_agendamentos.filter(Agendamento.data_atendimento >= di)
    if data_fim:
        df = datetime.strptime(data_fim, '%d/%m/%Y').date()
        query_base = query_base.filter(func.date(LancamentoFinanceiro.data_pagamento) <= df)
        query_agendamentos = query_agendamentos.filter(Agendamento.data_atendimento <= df)

    # 1. Receita por forma de pagamento [US-16]
    receita_pagamento = db.session.query(
        LancamentoFinanceiro.forma_pagamento, func.sum(LancamentoFinanceiro.valor)
    ).filter(LancamentoFinanceiro.id.in_([l.id for l in query_base.all()])).group_by(LancamentoFinanceiro.forma_pagamento).all()

    # 2. Receita por serviço [US-16]
    receita_servico = db.session.query(
        Servico.nome_servico, func.sum(Agendamento.valor_aplicado)
    ).join(Agendamento).filter(Agendamento.id.in_([a.id for a in query_agendamentos.all()])).group_by(Servico.nome_servico).all()

    # 3. Ticket Médio (Receita Total / Total de Realizados) [US-16]
    total_receita = db.session.query(func.sum(LancamentoFinanceiro.valor)).filter(LancamentoFinanceiro.id.in_([l.id for l in query_base.all()])).scalar() or 0
    total_realizados = query_agendamentos.count()
    ticket_medio = total_receita / total_realizados if total_realizados > 0 else 0

    # 4. Cálculo da Taxa de No-Show [RN-06]
    total_ausentes = Agendamento.query.filter_by(status='AUSENTE')
    if data_inicio: total_ausentes = total_ausentes.filter(Agendamento.data_atendimento >= di)
    if data_fim: total_ausentes = total_ausentes.filter(Agendamento.data_atendimento <= df)
    count_ausentes = total_ausentes.count()
    
    taxa_no_show = (count_ausentes / (total_realizados + count_ausentes)) * 100 if (total_realizados + count_ausentes) > 0 else 0

    # 5. Receita por período [US-16]
    receita_por_data = db.session.query(
        func.date(LancamentoFinanceiro.data_pagamento).label('data'),
        func.sum(LancamentoFinanceiro.valor)
    ).filter(LancamentoFinanceiro.id.in_([l.id for l in query_base.all()]))\
     .group_by('data')\
     .order_by('data').all()

    return jsonify({
        "receita_por_pagamento": [{"forma": r[0], "valor": float(r[1])} for r in receita_pagamento if r[0]],
        "receita_por_servico": [{"servico": r[0], "valor": float(r[1])} for r in receita_servico],
        "receita_por_periodo": [{"data": r[0].strftime('%d/%m/%Y'), "valor": float(r[1])} for r in receita_por_data],
        "receita_total": f"R$ {total_receita:,.2f}".replace('.', ','),
        "ticket_medio": f"R$ {ticket_medio:,.2f}".replace('.', ','),
        "taxa_no_show": f"{taxa_no_show:.2f}%"
    }), 200

# --- AUDITORIA ---

@financeiro_bp.route('/auditoria/<int:id_agendamento>', methods=['GET'])
@jwt_required()
def listar_logs_auditoria(id_agendamento):
    claims = get_jwt()
    roles = claims.get("roles", [])
    if "ADMIN" not in roles:
        return jsonify({"message": "Acesso restrito a administradores."}), 403

    logs = LogAuditoria.query.filter_by(id_agendamento=id_agendamento).order_by(LogAuditoria.data_alteracao.asc()).all()
    schema = LogAuditoriaSchema(many=True)
    return jsonify(schema.dump(logs)), 200
