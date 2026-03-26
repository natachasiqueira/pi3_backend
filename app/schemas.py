import re
from marshmallow import Schema, fields, validate, validates, validates_schema, ValidationError

class UsuarioSchema(Schema):
    id = fields.Int(dump_only=True)
    nome_completo = fields.Str(required=True, validate=validate.Length(max=255))
    email = fields.Email(required=True, validate=validate.Length(max=100))
    telefone = fields.Str(required=True)
    senha = fields.Str(required=True, load_only=True)
    confirmar_senha = fields.Str(required=True, load_only=True) # [RI-09]
    role = fields.Str(dump_only=True)
    criado_em = fields.DateTime(dump_only=True)

    @validates('telefone')
    def validate_telefone(self, value):
        # Padrão (XX) XXXXX-XXXX [PD-04]
        if not re.match(r'^\(\d{2}\) \d{5}-\d{4}$', value):
            raise ValidationError("O telefone deve estar no formato (XX) XXXXX-XXXX")

    @validates('senha')
    def validate_senha(self, value):
        # Mínimo 8 caracteres, letras, números e uma maiúscula [PD-06] [MSG-04]
        if len(value) < 8 or not re.search(r'[A-Z]', value) or not re.search(r'[a-z]', value) or not re.search(r'\d', value):
            raise ValidationError("A senha deve conter no mínimo 8 caracteres, incluindo letras, números e pelo menos uma letra maiúscula.")

    @validates_schema
    def validate_passwords(self, data, **kwargs):
        # [RI-09, MSG-08]
        if 'senha' in data and 'confirmar_senha' in data:
            if data['senha'] != data['confirmar_senha']:
                raise ValidationError("As senhas informadas não coincidem. Verifique e tente novamente.", field_name="confirmar_senha")

class LoginSchema(Schema):
    email = fields.Email(required=True)
    senha = fields.Str(required=True)

class UpdatePerfilSchema(Schema):
    nome_completo = fields.Str(validate=validate.Length(max=255))
    email = fields.Email(validate=validate.Length(max=100))
    telefone = fields.Str()
    senha_atual = fields.Str(load_only=True)
    nova_senha = fields.Str(load_only=True)
    confirmar_nova_senha = fields.Str(load_only=True) # [RI-09]

    @validates('telefone')
    def validate_telefone(self, value):
        if value and not re.match(r'^\(\d{2}\) \d{5}-\d{4}$', value):
            raise ValidationError("O telefone deve estar no formato (XX) XXXXX-XXXX")

    @validates('nova_senha')
    def validate_senha(self, value):
        if value:
            # [PD-06] [MSG-04]
            if len(value) < 8 or not re.search(r'[A-Z]', value) or not re.search(r'[a-z]', value) or not re.search(r'\d', value):
                raise ValidationError("A senha deve conter no mínimo 8 caracteres, incluindo letras, números e pelo menos uma letra maiúscula.")

    @validates_schema
    def validate_passwords(self, data, **kwargs):
        # [RI-09, MSG-08]
        if 'nova_senha' in data and 'confirmar_nova_senha' in data:
            if data['nova_senha'] != data['confirmar_nova_senha']:
                raise ValidationError("As senhas informadas não coincidem. Verifique e tente novamente.", field_name="confirmar_nova_senha")

class CategoriaServicoSchema(Schema):
    id = fields.Int(dump_only=True)
    nome_categoria = fields.Str(required=True, validate=validate.Length(max=100))

class ServicoSchema(Schema):
    id = fields.Int(dump_only=True)
    id_categoria = fields.Int(required=True)
    nome_servico = fields.Str(required=True, validate=validate.Length(max=255))
    duracao_minutos = fields.Int(required=True)
    valor = fields.Decimal(required=True, as_string=True)
    ativo = fields.Bool(dump_only=True)
    nome_categoria = fields.Str(dump_only=True)

class HorarioTrabalhoSchema(Schema):
    id = fields.Int(dump_only=True)
    id_funcionario = fields.Int(dump_only=True)
    dia_semana = fields.Int(required=True, validate=validate.Range(min=0, max=6))
    hora_inicio = fields.Time(required=True, format='%H:%M') # [PD-01]
    hora_fim = fields.Time(required=True, format='%H:%M') # [PD-01]

class BloqueioAgendaSchema(Schema):
    id = fields.Int(dump_only=True)
    id_funcionario = fields.Int(dump_only=True)
    data_bloqueio = fields.Date(required=True, format='%d/%m/%Y') # [PD-01]
    motivo = fields.Str(validate=validate.Length(max=255))

class FuncionarioSchema(UsuarioSchema):
    # Herança para concentrar validações de usuário [US-10]
    ids_categorias = fields.List(fields.Int(), load_only=True)
    categorias = fields.List(fields.Nested(CategoriaServicoSchema), dump_only=True)
    ativo = fields.Bool(dump_only=True)

class AgendamentoSchema(Schema):
    id = fields.Int(dump_only=True)
    id_cliente = fields.Int() # Removido dump_only para permitir que Admin envie
    id_funcionario = fields.Int(required=True)
    id_servico = fields.Int(required=True)
    data_atendimento = fields.Date(required=True, format='%d/%m/%Y') # [PD-01]
    hora_inicio = fields.Time(required=True, format='%H:%M') # [PD-01]
    hora_fim = fields.Time(dump_only=True, format='%H:%M') # [PD-01]
    valor_aplicado = fields.Method("get_valor_formatado", dump_only=True) # [PD-02]
    status = fields.Str(dump_only=True)
    nome_cliente = fields.Str(dump_only=True)
    nome_funcionario = fields.Str(dump_only=True)
    nome_servico = fields.Str(dump_only=True)
    duracao_minutos = fields.Int(dump_only=True)

def get_valor_formatado(self, obj):
        # Pega o valor dependendo do schema (valor_aplicado ou valor)
        valor_original = getattr(obj, 'valor_aplicado', getattr(obj, 'valor', 0))
        
        # 1. Formata no padrão americano (ex: 1,500.00)
        valor_us = f"{valor_original:,.2f}"
        
        # 2. Faz a mudança dos caracteres para o padrão BR
        valor_br = valor_us.replace(',', 'X').replace('.', ',').replace('X', '.')
        
        # [PD-02] Valores Financeiros: R$ 00,00
        return f"R$ {valor_br}"

class LancamentoFinanceiroSchema(Schema):
    id = fields.Int(dump_only=True)
    id_categoria_financeira = fields.Int(dump_only=True)
    id_agendamento = fields.Int(dump_only=True)
    nome_lancamento = fields.Str(dump_only=True)
    valor = fields.Method("get_valor_formatado", dump_only=True) # [PD-02]
    forma_pagamento = fields.Str(required=True, validate=validate.OneOf(['Dinheiro', 'Pix', 'Débito', 'Crédito'])) # [PD-07]
    status_pagamento = fields.Str(dump_only=True)
    data_pagamento = fields.DateTime(dump_only=True, format='%d/%m/%Y %H:%M') # [PD-01]
    data_criacao = fields.DateTime(dump_only=True, format='%d/%m/%Y %H:%M') # [PD-01]

    def get_valor_formatado(self, obj):
        return f"R$ {obj.valor:,.2f}".replace('.', ',')

class LogAuditoriaSchema(Schema):
    id = fields.Int(dump_only=True)
    id_agendamento = fields.Int(dump_only=True)
    status_anterior = fields.Str(dump_only=True)
    status_novo = fields.Str(dump_only=True)
    data_alteracao = fields.DateTime(dump_only=True, format='%d/%m/%Y %H:%M') # [PD-01]
    id_responsavel = fields.Int(dump_only=True)
    nome_responsavel = fields.Str(dump_only=True)



