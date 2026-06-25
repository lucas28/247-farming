# 24/7 Farming — Guild Hub

Plataforma Streamlit para a guilda **24/7 Farming** (Summoners War): dashboard, guias, banco de defesas, calculadora de speed tuning e painel administrativo.

## Funcionalidades

- Login por nickname (auto-cadastro de novos membros)
- Líder/Vice: PIN em secrets + painel admin
- Banco de defesas com eficiência e imagens SWARFARM
- **Meta de Defesa** — ranking de monstros do meta global (SWGT.io)
- Calculadora de speed tuning (simulação de ticks GW/Siege)
- Guias WGB e Siege editáveis pelo admin

## Requisitos

- Python 3.11+
- `pip install -r requirements.txt`

## Rodar localmente

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/macOS

pip install -r requirements.txt

copy .streamlit\secrets.toml.example .streamlit\secrets.toml
# Edite admin_pin no secrets.toml

streamlit run app.py
```

Acesse: http://localhost:8501

O banco SQLite é criado em `data/guilda.db` na primeira execução (quando `DATABASE_URL` não está definida).

## Secrets

Arquivo `.streamlit/secrets.toml` (não commitar):

```toml
admin_pin = "seu_pin_forte"

# Produção (Supabase) — omita para usar SQLite local:
# DATABASE_URL = "postgresql://postgres.[ref]:[SENHA]@aws-0-[regiao].pooler.supabase.com:5432/postgres"
```

Sem `admin_pin`, Líder e Vice **não conseguem** entrar como administradores.

## Banco de dados (SQLite local vs Supabase)

| Ambiente | Configuração | Persistência |
|----------|--------------|--------------|
| Local | Sem `DATABASE_URL` | `data/guilda.db` |
| Produção | `DATABASE_URL` nos secrets | PostgreSQL (Supabase) |

O `database.py` usa a **mesma API** nos dois backends; só muda a connection string.

### Configurar Supabase (produção)

> **Atenção:** o Supabase mostra um wizard com `npm install @supabase/supabase-js` e arquivos Next.js (`.env.local`, `page.tsx`, middleware). **Ignore isso** — o 24/7 Farming é **Streamlit + Python** e já conecta ao Postgres via `psycopg2` e `DATABASE_URL`.

1. Projeto criado em [supabase.com](https://supabase.com) (ref: `cugzgfbbtugeleotqwuc`).
2. No Supabase, clique em **Connect** (topo) → **Connection pooling** → **Transaction** (porta **6543**).
3. Cole em **Streamlit Cloud → Secrets** (use **Opção B** se a senha tiver `@`, `#`, `!`, etc.):

**Opção A** — connection string:

```toml
admin_pin = "seu_pin_forte"
DATABASE_URL = "postgresql://postgres.cugzgfbbtugeleotqwuc:[SENHA]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
```

**Opção B** — campos separados (recomendado):

```toml
admin_pin = "seu_pin_forte"
DB_HOST = "cole_aqui_o_host_do_painel_Connect"
DB_PORT = 6543
DB_USER = "postgres.cugzgfbbtugeleotqwuc"
DB_PASSWORD = "sua_senha"
DB_NAME = "postgres"
```

> **Atenção:** `DB_HOST` deve ser o host **real** copiado do Supabase (ex.: `aws-0-sa-east-1.pooler.supabase.com`). **Não** use `XXXX` nem texto de exemplo — isso causa o erro *"could not translate host name"*.

> **Importante:** não use `db.cugzgfbbtugeleotqwuc.supabase.co:5432` no Streamlit Cloud. Esse host é IPv6 e costuma falhar no deploy. Use sempre o **pooler** (`*.pooler.supabase.com`, porta **6543** ou **5432**, usuário `postgres.cugzgfbbtugeleotqwuc`).

A região (`sa-east-1`) pode variar — use exatamente os valores que o painel **Connect** do Supabase gerar.

**O que NÃO precisa:**
- `npm install @supabase/supabase-js`
- `NEXT_PUBLIC_SUPABASE_URL` / publishable key (são para apps JavaScript com auth no browser)
- Arquivos `utils/supabase/*.ts` ou middleware Next.js

4. Faça redeploy do app. Na primeira execução, `init_db()` cria as tabelas e o seed de defesas/guias.

5. Cadastre membros pelo app ou importe via script (com `DATABASE_URL` no ambiente):

```bash
set DATABASE_URL=postgresql://...
python scripts/seed_production.py import-membros scripts/membros.exemplo.json
```

### Migrar SQLite → Supabase

Se você já tem dados em `data/guilda.db` local:

```bash
set DATABASE_URL=postgresql://...
python scripts/migrate_sqlite_to_postgres.py
```

## Deploy no Streamlit Cloud

1. Envie o repositório para GitHub (sem `secrets.toml` nem `guilda.db`).
2. Em [share.streamlit.io](https://share.streamlit.io): **New app** → repositório → **Main file:** `app.py`.
3. **Settings → Secrets** (inclua `DATABASE_URL` do Supabase — ver acima).
4. **Advanced settings → Python version:** 3.11 (ou use `runtime.txt`).

### Seed em produção (banco limpo)

Com `DATABASE_URL` configurada:

```bash
set DATABASE_URL=postgresql://...
python scripts/seed_production.py fresh --force --guild "24/7 Farming" --discord "https://discord.gg/SEU_LINK"
python scripts/seed_production.py import-membros scripts/membros.exemplo.json
```

Ou cadastre membros diretamente pelo app após o deploy.

### Comandos do script de seed

| Comando | Descrição |
|---------|-----------|
| `python scripts/seed_production.py status` | Resumo do banco |
| `python scripts/seed_production.py fresh --force` | Recria DB (sem membros demo) |
| `python scripts/seed_production.py fresh --force --keep-demo-members` | Recria com membros de exemplo |
| `python scripts/seed_production.py import-membros arquivo.json` | Importa lista de membros |
| `python scripts/seed_production.py backup` | Backup SQLite em `data/backups/` (não aplica ao Postgres) |
| `python scripts/migrate_sqlite_to_postgres.py` | Copia `guilda.db` → Supabase (`DATABASE_URL` obrigatória) |

Formato JSON de membros: ver `scripts/membros.exemplo.json`.

## Estrutura do projeto

```
app.py                 # UI Streamlit
auth.py                # Sessão e PIN
database.py            # SQLite ou PostgreSQL (Supabase) + CRUD
speed_calculator.py    # Tuning por simulação de ticks
swgt_meta.py           # Coleta e ranking meta SWGT.io
monsters.py            # API SWARFARM + cache
content.py / guides.py # Conteúdo dos guias
textos.md              # Fonte markdown dos textos
data/                  # DB, cache de monstros, crest
.streamlit/            # config.toml + secrets
scripts/               # seed_production.py
```

## Segurança

- PIN apenas para cargos Líder/Vice (máx. 3 tentativas por sessão)
- Gateway interno da guilda — não substitui autenticação corporativa
- Nunca commite `secrets.toml` ou PINs reais

## Licença

Uso interno da guilda 24/7 Farming.
