# Help Desk Equipe

[![CI](https://github.com/mateusmendess/helpdesk-equipe/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/mateusmendess/helpdesk-equipe/actions/workflows/ci.yml) ![Python 3.13](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white) ![Django 6.1](https://img.shields.io/badge/Django-6.1-092E20?logo=django&logoColor=white)

Sistema web que o time de Help Desk de uma universidade usa no dia a dia para controlar a **troca do galão de água** e a **escala de sábado**. Substituiu duas planilhas Excel, guarda o histórico de tudo e está em produção, com uso real pela equipe (cerca de 8 pessoas).

**No ar:** https://helpdesk-equipe.up.railway.app (acesso só para quem foi cadastrado)

<!-- PRINT 1: docs/img/pagina-publica.png - página pública, com o desenho animado da equipe -->
<!-- PRINT 2: docs/img/galao-inicio.png - tela inicial do galão: vez, fila e botão "Troquei o galão" -->
<!-- PRINT 3: docs/img/escala-sabado.png - escala de sábado: próximo sábado e próximos sábados -->

## Telas

O sistema é de uso interno e exige login, por isso não há demo pública.
Os prints das telas serão adicionados aqui em breve.

## O problema

Na planilha, ninguém sabia ao certo de quem era a vez, as trocas feitas por um colega se perdiam e a escala dos sábados dependia de alguém lembrar a ordem. O sistema responde "de quem é a vez?" em uma tela, no computador ou no celular.

## O que faz

- **Galão:** fila fixa, vez calculada pelo servidor, registro da troca em um clique, cobertura (quem troca no lugar de outro) com dívida calculada a partir do histórico e ausências (quem está ausente é pulado e volta na próxima rodada).
- **Escala de sábado:** rodízio por posição, trocas de sábado entre pessoas, sábados com 2 pessoas ou sem escala, e sábados passados congelados (não mudam depois, mesmo que a fila mude).
- **Login por e-mail ou matrícula**, cadastro só pelo admin e troca de senha obrigatória no primeiro acesso.
- **Painel de administração** organizado em Galão, Escala e Usuários.

## Decisões técnicas que valem destaque

- **Regras no servidor, não na tela:** a vez, a dívida e a permissão de desfazer uma troca são calculadas e conferidas no backend.
- **Segurança de login:** limite progressivo de tentativas (por conta e por IP), sem bloqueio permanente que permita travar a conta de outra pessoa; páginas logadas sem cache; erro de formulário vencido com tela amigável e log do motivo.
- **Histórico que não se perde:** sábados passados são congelados e cada troca guarda quem registrou, quem trocou e a observação.
- **Testes:** mais de 740 testes (pytest), com regras de negócio, acesso por item e provas de que o teste falha quando o código é quebrado. O hash de senha é rápido só nos testes e forte em produção (com um teste que garante isso).
- **CI/CD:** GitHub Actions (ruff, testes e GitGuardian) em cada pull request; deploy automático no Railway só com o CI verde.
- **Sem dado pessoal no repositório:** nomes, matrículas, e-mails e senhas da equipe nunca entram no código, nos testes nem nos documentos.

## Stack

Python 3.13 · Django 6.1 · PostgreSQL · templates Django · Tailwind CSS 4 (CLI, sem Node) · Gunicorn + WhiteNoise · pytest · ruff · GitHub Actions · Railway

O nome técnico da pasta do projeto é `galao-helpdesk`.

## Como este projeto foi feito

Projeto solo de [Mateus Mendes](https://github.com/mateusmendess), estudante de Sistemas de Informação, com IA como apoio: eu defini as regras e conferi cada mudança; o código saiu em pull requests pequenos, com testes e CI verde antes de cada merge (mais de 50 pull requests). A descrição completa do sistema está em [`estrutura.md`](estrutura.md).

## Como rodar localmente (Windows, PowerShell)

```powershell
# 1. Ambiente virtual e dependências
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# 2. Variáveis de ambiente: copie o exemplo e troque a SECRET_KEY
Copy-Item .env.example .env

# 3. Banco local (SQLite)
python manage.py migrate
```

### Tailwind (CSS)

Baixe o executável standalone do Tailwind (sem Node) para a pasta `tools/`
(ela fica fora do git):

```powershell
New-Item -ItemType Directory -Force tools
Invoke-WebRequest https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.3/tailwindcss-windows-x64.exe -OutFile tools\tailwindcss.exe
```

Gerar o CSS uma vez:

```powershell
.\tools\tailwindcss.exe -i static_src\input.css -o static\css\output.css --minify
```

### Dois terminais no dia a dia

```powershell
# Terminal 1: servidor em http://127.0.0.1:8000
python manage.py runserver

# Terminal 2: regera o CSS a cada mudança nos templates
.\tools\tailwindcss.exe -i static_src\input.css -o static\css\output.css --minify --watch
```

O `static/css/output.css` vai para o git: depois de mudar o visual, faça commit dele.

### Primeiro uso do login

```powershell
python manage.py migrate
python manage.py createsuperuser          # seu admin: e-mail e senha digitados por você
python manage.py criar_equipe_de_teste    # Pessoa 1 a 7, sem senha (só com DEBUG=True)
python manage.py changepassword pessoa1@exemplo.test   # define a senha de uma conta de teste
python manage.py runserver
```

Abra http://127.0.0.1:8000 e entre com o e-mail (ou a matrícula) e a senha. Contas novas de verdade
são cadastradas só pelo admin, em http://127.0.0.1:8000/admin/.

Limite de tentativas (em /entrar/ e no /admin/): com 5 senhas erradas para a mesma pessoa
na última hora, somando as feitas pelo e-mail e pela matrícula, ela espera 1 minuto; cada erro
novo dobra a espera (2, 4, 8 min), até no máximo 15 minutos. Uma hora sem erros ou a senha
certa zeram a contagem. Além disso, 20 erros do mesmo IP em 15 minutos bloqueiam esse IP.
O admin pode liberar alguém na hora: ação "Liberar entrada" na lista de usuários.
Os valores ficam em `config/settings.py` (os `LOGIN_...`).

Senhas: cada pessoa troca a própria senha em "Trocar senha", na tela inicial.
O admin cria a senha provisória no /admin/; usuário novo vem marcado para trocar no primeiro acesso.
Ao redefinir a senha de outra pessoa no /admin/, a marca "precisa trocar a senha no próximo acesso" liga sozinha (a pessoa troca no próximo acesso).

Fila: a tela inicial mostra a rodada, de quem é a vez e a fila de 1 a 7.
A `ordem` de cada usuário (no /admin/) define a posição na fila; quem não tem ordem fica fora.
Qualquer pessoa logada registra a troca pelo botão "Troquei o galão" na tela inicial (inclusive cobertura).
O histórico completo fica em "Ver histórico" (/trocas/); a marca "devendo N" vem desse histórico.
O admin ainda pode lançar trocas em /admin/ (Galão de água › Trocas do galão).
No /admin/, o admin corrige o executor e a observação de uma troca; o "devendo" se acerta sozinho.
Apagar só vale para uma troca da rodada atual, ou da última rodada fechada enquanto a atual estiver vazia (essa rodada é reaberta).
Ausências: no /admin/ (Galão de água › Ausências), o admin cadastra a pessoa, o início e o fim (fim em branco = sem data de volta).
Quem está ausente hoje é pulado na fila e aparece como "ausente até DD/MM" na tela inicial.

### Testes e ruff

```powershell
pytest
ruff check .
ruff format --check .
```

## Produção (Railway)

Build, pré-deploy, start e healthcheck ficam configurados no painel do Railway
(não há `railway.json` nem `Procfile`):

| Etapa | Valor |
|---|---|
| Build | `python manage.py collectstatic --noinput` |
| Pré-deploy | `python manage.py migrate --noinput` |
| Start | `gunicorn config.wsgi --bind 0.0.0.0:$PORT` |
| Healthcheck | `/saude/` (timeout de 300 s) |

O Python vem do `.python-version` (3.13). Variáveis de ambiente (sem valores aqui):

- `SECRET_KEY`: chave longa e aleatória, só de produção
- `DEBUG=False`
- `HTTPS_SEGURO=True` (redireciona para https, cookies seguros e HSTS)
- `ALLOWED_HOSTS`: domínio do site **e** `healthcheck.railway.app`, separados por vírgula
  (ex.: `meu-app.up.railway.app,healthcheck.railway.app`)
- `CSRF_TRUSTED_ORIGINS`: endereço com https (ex.: `https://meu-app.up.railway.app`)
- `DATABASE_URL`: URL do PostgreSQL do Railway

O `criar_equipe_de_teste` não roda em produção (recusa com `DEBUG=False`).

## Licença

Todos os direitos reservados. O código está público para consulta e portfólio.
