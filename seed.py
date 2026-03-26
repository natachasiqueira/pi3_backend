from run import create_app, db
from run.models import Usuario, Funcionario, CategoriaServico, CategoriaFinanceira
from werkzeug.security import generate_password_hash

def seed():
    app = create_app()
    with app.app_context():
        # Criar tabelas (caso não existam via migrations ainda)
        db.create_all()

        # 1. Usuário Seed (Ellen Patrício) [PRD - Seção 2]
        email_seed = 'ellenpatricio@studio.com.br'
        if not Usuario.query.filter_by(email=email_seed).first():
            ellen = Usuario(
                nome_completo='Ellen Patrício',
                telefone='(11) 98765-4321',
                email=email_seed,
                senha=generate_password_hash('Admin123'),
                role='ADMIN,FUNCIONARIO' # Múltiplas roles conforme PRD
            )
            db.session.add(ellen)
            db.session.flush() # Para pegar o ID da Ellen

            # Criar vínculo de Funcionário
            ellen_func = Funcionario(
                id_usuario=ellen.id,
                ativo=True
            )
            db.session.add(ellen_func)
            
            print("Usuário Seed criado com sucesso!")

        # 2. Categorias Financeiras Iniciais 
        cat_servicos = CategoriaFinanceira.query.filter_by(nome_categoria='Serviços Realizados').first()
        if not cat_servicos:
            nova_cat = CategoriaFinanceira(
                nome_categoria='Serviços Realizados',
                tipo_movimentacao='RECEITA'
            )
            db.session.add(nova_cat)
            print("Categoria Financeira 'Serviços Realizados' criada!")

        db.session.commit()
        print("Seed finalizado.")

        if __name__ == '__main__':
            seed()