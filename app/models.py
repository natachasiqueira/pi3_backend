from app import db
from datetime import datetime
import pytz
import os

def get_now():
    tz = pytz.timezone(os.environ.get('TIMEZONE', 'America/Sao_Paulo'))
    return datetime.now(tz)

# Tabela Associativa para Especialidades (N:N entre Funcionário e Categoria de Serviço)
categorias_funcionarios = db.Table('categorias_funcionarios',
    db.Column('id_funcionario', db.Integer, db.ForeignKey('funcionarios.id'), primary_key=True),
    db.Column('id_categoria', db.Integer, db.ForeignKey('categorias_servicos.id'), primary_key=True)
)

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.String(255), nullable=False)
    telefone = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    senha = db.Column(db.String(255), nullable=False) # Aumentado para hash de senha
    role = db.Column(db.String(50), nullable=False) # Suporta múltiplas roles [PRD]
    data_criacao = db.Column(db.DateTime, default=get_now)

    @property
    def roles_list(self):
        return [r.strip() for r in self.role.split(',')] if self.role else []

    # Relacionamento 1:1 com Funcionario
    funcionario = db.relationship('Funcionario', backref='usuario', uselist=False)
    
    # Relacionamentos para Agendamentos e Auditoria
    agendamentos = db.relationship('Agendamento', backref='cliente', lazy=True)
    logs_auditados = db.relationship('LogAuditoria', backref='responsavel', lazy=True)

class Funcionario(db.Model):
    __tablename__ = 'funcionarios'
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False, unique=True)
    ativo = db.Column(db.Boolean, default=True)

    # Relacionamentos
    horarios = db.relationship('HorarioTrabalho', backref='funcionario', lazy=True)
    bloqueios = db.relationship('BloqueioAgenda', backref='funcionario', lazy=True)
    agendamentos = db.relationship('Agendamento', backref='funcionario', lazy=True)
    
    # N:N com Categorias de Serviço
    categorias = db.relationship('CategoriaServico', secondary=categorias_funcionarios, 
                                backref=db.backref('funcionarios', lazy='dynamic'))

class CategoriaServico(db.Model):
    __tablename__ = 'categorias_servicos'
    id = db.Column(db.Integer, primary_key=True)
    nome_categoria = db.Column(db.String(100), nullable=False, unique=True)
    
    servicos = db.relationship('Servico', backref='categoria', lazy=True)

class Servico(db.Model):
    __tablename__ = 'servicos'
    id = db.Column(db.Integer, primary_key=True)
    id_categoria = db.Column(db.Integer, db.ForeignKey('categorias_servicos.id'), nullable=False)
    nome_servico = db.Column(db.String(255), nullable=False)
    duracao_minutos = db.Column(db.Integer, nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    ativo = db.Column(db.Boolean, default=True)

    agendamentos = db.relationship('Agendamento', backref='servico', lazy=True)

class HorarioTrabalho(db.Model):
    __tablename__ = 'horarios_trabalho'
    id = db.Column(db.Integer, primary_key=True)
    id_funcionario = db.Column(db.Integer, db.ForeignKey('funcionarios.id'), nullable=False)
    dia_semana = db.Column(db.Integer, nullable=False) # 0-6 (Seg-Dom)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fim = db.Column(db.Time, nullable=False)

class BloqueioAgenda(db.Model):
    __tablename__ = 'bloqueios_agenda'
    id = db.Column(db.Integer, primary_key=True)
    id_funcionario = db.Column(db.Integer, db.ForeignKey('funcionarios.id'), nullable=False)
    data_bloqueio = db.Column(db.Date, nullable=False)
    motivo = db.Column(db.String(255))

class Agendamento(db.Model):
    __tablename__ = 'agendamentos'
    id = db.Column(db.Integer, primary_key=True)
    id_cliente = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    id_funcionario = db.Column(db.Integer, db.ForeignKey('funcionarios.id'), nullable=False)
    id_servico = db.Column(db.Integer, db.ForeignKey('servicos.id'), nullable=False)
    data_atendimento = db.Column(db.Date, nullable=False)
    hora_inicio = db.Column(db.Time, nullable=False)
    hora_fim = db.Column(db.Time, nullable=False)
    valor_aplicado = db.Column(db.Numeric(10, 2), nullable=False) # Snapshot do preço [RN-04]
    status = db.Column(db.String(20), nullable=False, default='AGENDADO')
    data_criacao = db.Column(db.DateTime, default=get_now)
    data_atualizacao = db.Column(db.DateTime, default=get_now, onupdate=get_now)

    # Relacionamentos
    lancamentos = db.relationship('LancamentoFinanceiro', backref='agendamento', lazy=True)
    logs = db.relationship('LogAuditoria', backref='agendamento', lazy=True)

class CategoriaFinanceira(db.Model):
    __tablename__ = 'categorias_financeiras'
    id = db.Column(db.Integer, primary_key=True)
    nome_categoria = db.Column(db.String(100), nullable=False, unique=True)
    tipo_movimentacao = db.Column(db.String(20), nullable=False) # RECEITA ou DESPESA

    lancamentos = db.relationship('LancamentoFinanceiro', backref='categoria_financeira', lazy=True)

class LancamentoFinanceiro(db.Model):
    __tablename__ = 'lancamentos_financeiros'
    id = db.Column(db.Integer, primary_key=True)
    id_categoria_financeira = db.Column(db.Integer, db.ForeignKey('categorias_financeiras.id'), nullable=False)
    id_agendamento = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=True)
    nome_lancamento = db.Column(db.String(255), nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    forma_pagamento = db.Column(db.String(50), nullable=True)
    status_pagamento = db.Column(db.String(20), nullable=False, default='PENDENTE')
    data_pagamento = db.Column(db.DateTime, nullable=True)
    data_criacao = db.Column(db.DateTime, default=get_now)

class LogAuditoria(db.Model):
    __tablename__ = 'logs_auditoria'
    id = db.Column(db.Integer, primary_key=True)
    id_agendamento = db.Column(db.Integer, db.ForeignKey('agendamentos.id'), nullable=False)
    status_anterior = db.Column(db.String(20), nullable=True)
    status_novo = db.Column(db.String(20), nullable=False)
    data_alteracao = db.Column(db.DateTime, default=get_now)
    id_responsavel = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    nome_responsavel = db.Column(db.String(255), nullable=False)
