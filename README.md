# 24/7 Farming — Guild Hub

Plataforma Streamlit para a guilda **24/7 Farming** (Summoners War): dashboard, guias, banco de defesas, calculadora de speed tuning e painel administrativo.

## Funcionalidades

- Login por nickname (auto-cadastro de novos membros)
- Líder/Vice: PIN em secrets + painel admin
- Banco de defesas com eficiência e imagens SWARFARM
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

O banco SQLite é criado em `data/guilda.db` na primeira execução.

## Secrets

Arquivo `.streamlit/secrets.toml` (não commitar):

```toml
admin_pin = "seu_pin_forte"
```

Sem `admin_pin`, Líder e Vice **não conseguem** entrar como administradores.

## Deploy no Streamlit Cloud

1. Envie o repositório para GitHub (sem `secrets.toml` nem `guilda.db`).
2. Em [share.streamlit.io](https://share.streamlit.io): **New app** → repositório → **Main file:** `app.py`.
3. **Settings → Secrets:**

```toml
admin_pin = "seu_pin_forte"
```

4. **Advanced settings → Python version:** 3.11 (ou use `runtime.txt`).

### Banco em produção

No Streamlit Cloud o filesystem é **efêmero** — `data/guilda.db` é recriado a cada redeploy, a menos que você use persistência externa.

**Primeiro deploy (banco limpo para produção):**

```bash
python scripts/seed_production.py fresh --force --guild "24/7 Farming" --discord "https://discord.gg/SEU_LINK"
python scripts/seed_production.py import-membros scripts/membros.exemplo.json
```

Depois copie `data/guilda.db` para o ambiente de produção **ou** cadastre membros pelo app após o deploy.

**Migrar banco local para produção:**

```bash
python scripts/seed_production.py backup
# Envie data/backups/guilda_backup_*.db para o servidor ou restaure manualmente
```

### Comandos do script de seed

| Comando | Descrição |
|---------|-----------|
| `python scripts/seed_production.py status` | Resumo do banco |
| `python scripts/seed_production.py fresh --force` | Recria DB (sem membros demo) |
| `python scripts/seed_production.py fresh --force --keep-demo-members` | Recria com membros de exemplo |
| `python scripts/seed_production.py import-membros arquivo.json` | Importa lista de membros |
| `python scripts/seed_production.py backup` | Backup em `data/backups/` |

Formato JSON de membros: ver `scripts/membros.exemplo.json`.

## Estrutura do projeto

```
app.py                 # UI Streamlit
auth.py                # Sessão e PIN
database.py            # SQLite + CRUD
speed_calculator.py    # Tuning por simulação de ticks
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
