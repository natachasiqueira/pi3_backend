# API do Sistema de Agendamento e Gestão - PI3

Este repositório contém o back-end completo do Sistema de Agendamento para Estúdio de Beleza, desenvolvido como parte do Projeto Integrador III. A API foi construída seguindo rigorosamente o PRD (Product Requirements Document) e o ERD (Entity Relationship Diagram), com foco em escalabilidade, segurança (LGPD) e regras de negócio complexas.

## 🚀 Tecnologias Utilizadas

- **Linguagem:** Python 3.13+
- **Framework:** Flask (Padrão Application Factory)
- **Banco de Dados:** PostgreSQL (Hospedado na Neon.tech)
- **ORM:** SQLAlchemy
- **Migrações:** Flask-Migrate
- **Autenticação:** JWT (JSON Web Tokens) com suporte a múltiplas roles
- **Validação de Dados:** Marshmallow (Esquemas estritos)
- **Documentação:** OpenAPI 3.0 (Swagger) via Flask-Smorest
- **Deploy:** Vercel

## 📂 Estrutura do Projeto

O projeto utiliza o padrão **Application Factory** e **Blueprints** para garantir organização modular:

```text
pi3_backend/
├── app/                        # Núcleo da aplicação
│   ├── routes/                 # Blueprints (Auth, Admin, Agendamentos, Financeiro)
│   ├── models.py               # Definições do banco de dados (SQLAlchemy)
│   ├── schemas.py              # Esquemas de validação (Marshmallow)
│   └── __init__.py             # Configuração da Factory e Extensões
├── venv/                       # Ambiente virtual (recomendado)
├── app.py                      # Ponto de entrada para o servidor
├── requirements.txt            # Dependências do sistema
├── seed.py                     # Script para inicializar dados básicos (Ellen Patrício)
└── vercel.json                 # Configuração para deploy na Vercel
```

## 🛠️ Configuração e Instalação

1.  **Clonar o repositório:**
    ```bash
    git clone https://github.com/natachasiqueira/pi3_backend.git
    cd pi3_backend
    ```

2.  **Criar e ativar o ambiente virtual:**
    ```bash
    python -m venv venv
    .\venv\Scripts\activate  # Windows
    # source venv/bin/activate  # Linux/Mac
    ```

3.  **Instalar dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar Variáveis de Ambiente:**
    Crie um arquivo `.env` na raiz do projeto com as seguintes chaves:
    ```env
    DATABASE_URL=seu_link_do_postgresql_neon
    JWT_SECRET_KEY=sua_chave_secreta_segura
    TIMEZONE=America/Sao_Paulo
    ```

5.  **Inicializar o Banco de Dados (Seed):**
    ```bash
    python seed.py
    ```

6.  **Executar a API:**
    ```bash
    python app.py
    ```

## 📖 Documentação da API (Swagger)

Com a API rodando, acesse a documentação interativa em:
`http://localhost:5000/swagger`

Lá você encontrará todos os endpoints, modelos de entrada/saída e poderá testar as requisições diretamente pelo navegador utilizando o Token JWT.

## ⚖️ Diferenciais e Conformidade (PRD)

Esta API implementa 100% das regras de negócio exigidas no PRD:
- **Múltiplas Roles por Usuário**: Suporte nativo para usuários com mais de um papel (ex: ADMIN + FUNCIONARIO).
- **Motor de Disponibilidade [RN-03, RN-13, RN-14]**: Algoritmo inteligente que evita overbooking, respeita escalas, bloqueios e aplica granularidade de 30 minutos.
- **Hierarquia Administrativa**: O Admin possui liberdade total para agendar por clientes e cancelar atendimentos sem as travas de antecedência (3h/2h).
- **Conformidade LGPD [RN-11]**: Rota de exclusão de conta com anonimização irreversível dos dados pessoais.
- **Padronização Estrita [PD-01 a PD-07]**: Datas em `DD/MM/AAAA`, horários `24h` e valores em `R$ 00,00`.
- **Auditoria [RN-05]**: Log detalhado de cada mudança de status de agendamento.

## 👤 Usuário Seed (Acesso Inicial)

O banco de dados é inicializado com a usuária administradora para testes:
- **E-mail:** `ellenpatricio@studio.com.br`
- **Senha:** `Admin123`
- **Roles:** `ADMIN,FUNCIONARIO`
