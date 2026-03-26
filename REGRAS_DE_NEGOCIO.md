# Mapeamento de Regras de Negócio (RN) e Histórias de Usuário (US)

Este documento detalha onde cada regra do PRD foi implementada no código do back-end.

## 📌 Regras de Negócio (RN)

| Regra | Descrição | Localização no Código |
|:--- |:--- |:--- |
| **RN-01** | Antecedência de 3h para agendamento | `app/routes/agendamentos.py` (linhas 85-90) |
| **RN-02** | Antecedência de 2h para cancelamento | `app/routes/agendamentos.py` (linhas 255-260) |
| **RN-03** | Evitar Overbooking / Concorrência | `app/routes/agendamentos.py` (função `is_slot_available`) |
| **RN-04** | Atribuição e Snapshot de Preço | `app/routes/agendamentos.py` (linha 165) |
| **RN-05** | Auditoria Contínua | `app/routes/agendamentos.py` e `app/routes/financeiro.py` |
| **RN-06** | Cálculo Taxa No-Show | `app/routes/financeiro.py` (linhas 160-166) |
| **RN-07** | Status Inicial 'AGENDADO' | `app/routes/agendamentos.py` (linha 173) |
| **RN-08** | Transição de Status (Cliente) | `app/routes/agendamentos.py` (linhas 248-265) |
| **RN-09** | Transição de Status (Funcionário) | `app/routes/agendamentos.py` (linhas 268-272) |
| **RN-10** | Gatilho de Receita | `app/routes/agendamentos.py` (linhas 288-300) |
| **RN-11** | Anonimização LGPD | `app/routes/auth.py` (função `anonimizar_conta`) |
| **RN-13** | Filtro de Escala e Bloqueios | `app/routes/agendamentos.py` (linhas 70-80) |
| **RN-14** | Arredondamento Slots 30min | `app/routes/agendamentos.py` (função `arredondar_duracao`) |

## 📊 Padronização de Dados (PD)

- **PD-01 (Datas/Horas):** Centralizado em `app/schemas.py` usando formatos `%d/%m/%Y` e `%H:%M`.
- **PD-02 (Valores):** Implementado via `fields.Method` no `AgendamentoSchema` e `LancamentoFinanceiroSchema`.
- **PD-04 (Telefone):** Validado via Regex no `UsuarioSchema` em `app/schemas.py`.
- **PD-06 (Senha):** Validação de força implementada no `UsuarioSchema`.
- **PD-07 (Pagamentos):** Restrição de valores via `validate.OneOf` no `LancamentoFinanceiroSchema`.

## 👤 Histórias de Usuário (US) - Back-end

- **Épico 1 (Autenticação):** Implementado em `app/routes/auth.py`.
- **Épico 2 (Área Cliente):** Implementado em `app/routes/agendamentos.py`.
- **Épico 3 (Área Funcionário):** Implementado em `app/routes/agendamentos.py` (listagem e status).
- **Épico 4 (Administração):** Implementado em `app/routes/admin.py`.
- **Épico 5 (Financeiro):** Implementado em `app/routes/financeiro.py`.

---
Este mapeamento garante que todos os requisitos do PRD foram transformados em código funcional.
