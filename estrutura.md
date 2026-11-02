# Help Desk Equipe — Estrutura do Projeto

**Nomes:** o repositório no GitHub é `helpdesk-equipe`; a pasta local e o nome técnico antigo seguem `galao-helpdesk`. **Produção:** https://helpdesk-equipe.up.railway.app

Sistema web simples para o time do Help Desk (cerca de 8 pessoas). Hoje tem **dois módulos**: o **galão** (de quem é a vez de trocar o galão de água) e a **escala de sábado** (quem trabalha em cada sábado). Os dois vieram de planilhas Excel; o sistema substitui as planilhas e guarda o histórico completo.

---

## 1. Stack (fechada)

| Camada | Escolha | Para que serve |
|---|---|---|
| Framework | Django 6.1 (Python 3.13) | Login, usuários, permissões e painel admin já vêm prontos |
| Banco | PostgreSQL (Railway; versão 18 no CI); SQLite no computador | Guarda pessoas, rodadas, trocas, ausências e a escala de sábado |
| Front | Templates Django (HTML) + Tailwind CSS 4 (CLI standalone) | O Django monta a página; o Tailwind é o CSS, gerado num arquivo `output.css` (versionado; o executável do Tailwind fica em `tools/`, fora do Git) |
| Login | `django.contrib.auth` com usuário próprio (custom user) | Um login por pessoa, por e-mail ou matrícula; cadastro só pelo admin |
| Servidor | Gunicorn + WhiteNoise | Gunicorn roda o Django em produção; WhiteNoise entrega o CSS |
| Qualidade | pytest-django + ruff | Testes e verificação de estilo do código |
| CI/CD | GitHub Actions (CI desde o módulo 1) + Railway | CI: lint + testes em cada push e PR. Deploy: sai da `main`, só com o CI verde |

**Visual:** as cores do sistema são tokens no bloco `@theme` de `static_src/input.css` (`tinta`, `agua`, `fundo`, `texto`, `ok`, `aviso`, `ausente`, `erro`...), viram classes como `bg-agua`/`text-tinta`, e o foco visível é uma regra global (contorno de 3 px na tinta).
A tela inicial usa o cabeçalho `templates/_cabecalho.html` (marca, rodada e menu da conta em `<details>`, sem JavaScript) e tem o cartão da vez como elemento principal, com a barra de progresso da rodada, o botão "Troquei o galão" e a última troca; a fila marca cada estado por forma e texto; no computador são duas colunas.
Os formulários (entrar, registrar troca, trocar senha e senha alterada) seguem o mesmo estilo: campos de 48 px com borda #7F8F97, botões de 48 a 52 px, avisos e erros com ícone.
O cabeçalho aceita parâmetros no include: `marca_p=True` (a marca vira `<p>` quando a página tem o próprio `<h1>`) e `sem_menu=True` (telas de senha, sem menu nem links); o entrar não tem cabeçalho.
O histórico agrupa as trocas por rodada (título "Rodada N" com o total de trocas da rodada inteira, contado numa consulta só), com data e hora empilhadas em cada cartão.
No /admin/, o mixin `MensagensNoFeminino` (em `fila/admin.py`) põe no feminino as mensagens de sucesso de Troca, Ausência e Rodada; os seletores de pessoa mostram "Escolha uma pessoa" como opção vazia.

**Página pública e identidade:** quem não entrou vê, em `/`, uma página pública (`templates/publica/inicio.html`), só HTML e CSS, sem JavaScript e sem ler o banco; quem entrou vê o galão no mesmo endereço. A logo "interseção" (dois quadrados que se cruzam, com o encontro vazado) está no partial `templates/_logo.html` e aparece no cabeçalho, na entrada e na página pública; o ícone da aba (`static/img/favicon.svg`, `favicon.ico` e `apple-touch-icon.png`) é a mesma marca, em branco sobre fundo azul. A tela de entrada (`/entrar/`) tem o cartão centralizado na tela.

---

## 2. Regras de negócio

### Galão

- Fila fixa pela `ordem` (1, 2, 3...; uma posição por pessoa, sem limite fixo no código). A troca acontece **por evento** (quando o galão acaba), não em dia fixo.
- **Rodada:** cada pessoa tem uma vez por rodada. A rodada fecha quando ninguém mais está esperando a vez: todos os **presentes** já trocaram ou foram **pulados** (ver abaixo). Só fecha se houver pelo menos uma pessoa presente.
- **Conferência da rodada:** além de quando uma troca é salva, a rodada também é conferida sempre que alguém consulta a rodada atual (ex.: ao abrir a tela inicial); se todos os presentes já trocaram, ela fecha ali e a próxima abre.
- **Sempre para a frente** (PR #25): a vez só anda para a frente na rodada. Cada pessoa da fila está num destes estados: *já trocou*; *ausente* (tem ausência cadastrada para hoje); *pulado* (presente, ainda sem troca, mas com `ordem` menor que a do último que trocou na rodada); *vez agora*; *aguardando*. Quem fica **pulado** não volta nesta rodada: "volta na próxima rodada", no lugar de sempre (`ordem`), sem prioridade e **sem dívida**. O estado "pulado" não é gravado: é recalculado a cada consulta, pelas trocas da rodada e pelas ausências de hoje.
- **Ausência:** quem está ausente não precisa ter trocado para a rodada fechar, e ninguém fica devendo por isso. O sistema só olha quem trocou e quem está ausente **hoje**; a data de volta nunca decide a vez. Se a data de volta é desconhecida (ausência em aberto, sem fim), a pessoa fica como "ausente" até o admin preencher o fim; quando há fim, a tela mostra "ausente até DD/MM".
- **Período da ausência:** cadastrado só pelo admin, com início e fim opcional (vazio = em aberto). Vale do início ao fim, inclusive, na data local; a pessoa volta no dia seguinte ao fim. A mesma pessoa não pode ter dois períodos que se sobreponham, e o fim não pode ser antes do início.
- **De quem é a vez:** a primeira pessoa presente, sem troca nesta rodada, que vem depois do último que trocou (ou a primeira da fila, se ninguém trocou ainda).
- **Cobertura:** se A troca no lugar de B, o histórico registra "A no lugar de B", a vez de B conta como cumprida e B passa a dever 1 troca.
- **Dívida ("devendo"):** não é digitada; é calculada a partir do histórico (ver seção 4).
- **Histórico completo:** cada troca vira um registro. Nada se perde quando a rodada vira.
- **Botão "Troquei o galão":** aparece na tela inicial quando há vez. No formulário "Registrar troca", o titular é sempre a pessoa da vez (calculada no servidor na hora de gravar); quem registra diz se foi a própria pessoa ou outra. Se a vez mudou enquanto a pessoa preenchia, nada é gravado.
- **Correções pelo admin:** o admin corrige só quem trocou (executor) e a observação; titular, rodada, data e quem registrou não mudam. Apagar só vale para a troca da rodada atual, ou para a da última rodada fechada quando a atual ainda está vazia; nesse caso a rodada vazia é apagada e a anterior é reaberta.
- **Última troca e histórico:** a tela inicial mostra a última troca e a marca "devendo N" ao lado do nome; a tela "Histórico de trocas" lista tudo, da mais recente para a mais antiga, 30 por página.
- **Sem notificação** por enquanto: o sistema não envia e-mail; os avisos à equipe (por exemplo, de uma troca de sábado) são feitos pelas pessoas.

### Escala de sábado (app `escala`)

- **Rodízio por posição:** a fila da escala é formada pelas pessoas ativas que têm `ordem_escala` (posição própria, separada da `ordem` do galão, vinda da planilha), da menor para a maior. A escala só anda para a frente: o sistema guarda a posição da última pessoa vista (escalada ou pulada), não um índice da lista, então a fila pode ganhar ou perder gente sem quebrar.
- **Início:** o admin liga a escala numa configuração única: o primeiro sábado da escala no sistema e a primeira pessoa da fila. Sem configuração, a página da escala avisa que ainda não foi ligada e que, por enquanto, vale a planilha.
- **Vagas:** cada sábado tem 1 pessoa (turno da manhã, das 8h às 12h). O admin pode cadastrar um sábado com 2 pessoas (manhã e tarde, das 13h às 17h).
- **Ausentes:** quem está ausente naquele sábado (as mesmas ausências do galão) é pulado: a posição anda e ninguém fica devendo. Se todos estiverem ausentes, ninguém é escalado.
- **Sábado sem escala** (feriado, imprevisto ou outro): cadastrado pelo admin. Com "passar para o próximo" marcado, quem estava na vez vai para o sábado seguinte (nada se gasta); desmarcado, a vez é gasta (ausentes são pulados) e ninguém trabalha. A mesma data não pode ser "sem escala" e "com 2 pessoas" ao mesmo tempo.
- **O sábado termina às 17h** (fuso America/Sao_Paulo). Só dá para cadastrar sábado que ainda não terminou.
- **Sábados passados são congelados:** ao abrir a escala (ou pelo comando `python manage.py congelar_escala`), cada sábado que terminou é gravado, com quem foi escalado e quem foi pulado, e nunca mais muda, mesmo que as ausências ou a fila mudem depois. Depois do primeiro sábado congelado, o início e o primeiro da fila ficam travados. Quem aparece em sábado gravado (escalado ou pulado) ou em troca de sábado **não pode ser apagado**: desative em vez de apagar.
- **Trocas de sábado:** duas pessoas trocam turnos de sábados diferentes (A fica com o turno de B e B com o de A); a fila **não** muda. O membro só registra troca em que participa, só do tipo "combinada" e só de sábados que ainda não chegaram; o admin registra qualquer par, inclusive "emergência" e os últimos sábados já gravados. O sistema recusa: sábado sem escala, turno sem ninguém, escala que mudou enquanto a pessoa preenchia, alguém duas vezes no mesmo sábado e alguém ausente na data.
- **Desfazer troca:** o admin sempre; o membro, se participa, até a véspera do primeiro sábado da troca. Antes é preciso desfazer a troca mais recente que mexe nos mesmos turnos. A troca nunca é apagada: fica no histórico como desfeita, com quem desfez e quando. Situação: ativa, feita (as duas datas já terminaram) ou desfeita.
- **Telas:** `/escala/` (o próximo sábado em destaque e mais 6), `/escala/proximos/` (previsão dos próximos 26 sábados), `/escala/trocar/`, `/escala/trocas/` (trocas ativas e histórico, 30 por página) e `/escala/regras/` (as regras da planilha: o sistema aplica as de fila, data e troca; as demais valem como combinado da equipe).

### Login e acesso

- **Entrar:** `/entrar/` tem um campo só, "E-mail ou matrícula", e a senha. Se o texto (sem espaços nas pontas) tem só dígitos, é buscado como matrícula (texto exato: "0123" e "123" são diferentes); senão, como e-mail (sem diferença entre maiúsculas e minúsculas). O `/admin/login/` usa o mesmo campo e a mesma mensagem.
- **Matrícula:** opcional, só dígitos, guardada como texto, única por pessoa. Quem ainda não tem matrícula entra pelo e-mail.
- **Mensagem única:** "E-mail, matrícula ou senha incorretos." Ela não diz se a matrícula ou o e-mail existe. Usuário inativo não entra.
- **Bloqueio:** 5 senhas erradas em 15 minutos bloqueiam a pessoa (valores em `config/settings.py`: `LOGIN_MAX_TENTATIVAS` e `LOGIN_JANELA_MINUTOS`). A matrícula e o e-mail da mesma pessoa contam juntos: a falha é guardada com o e-mail dela; se o texto digitado não é de ninguém, guarda o texto em minúsculas. No bloqueio nem a senha certa entra; o sucesso zera a contagem e o bloqueio acaba sozinho.
- **Troca de senha obrigatória:** a conta criada pelo admin vem com senha provisória e, no primeiro acesso, só abre "Trocar senha" (e Sair). Quando o admin redefine a senha de outra pessoa, vale de novo. Não existe "esqueci a senha": quem esquece fala com um admin.
- **Sem cache:** as telas de quem está logado saem com cabeçalhos de "não guardar" (`core/middleware.py`), para o botão "voltar" não mostrar a tela antiga depois de sair. A página pública, o `/saude/` e os arquivos estáticos não mudam.
- **Acesso:** login individual. Admins: o Mateus e quem ele indicar. Só admins cadastram pessoas, registram ausências, corrigem registros do galão e configuram a escala. Os demais consultam e registram trocas do galão pelo botão, inclusive cobertura, e trocam sábados seus.

---

## 3. Modelos (tabelas)

### Usuario (usuário próprio do Django)
- Login por **e-mail** (único, sempre em minúsculas) ou **matrícula** (`matricula`: opcional, só dígitos, texto, única; vazia fica sem valor). O `USERNAME_FIELD` continua sendo o e-mail; não existe nome de usuário
- Campos do Django (nome, senha, `is_active`, `is_staff`, `is_superuser`)
- `ordem`: posição na fila do galão (começa em 1), única; pode ficar vazia para quem não está na fila
- `ordem_escala`: posição no rodízio de sábado (começa em 1), única; vazia = a pessoa não entra na escala (independe da `ordem`)
- `precisa_trocar_senha`: liga a troca de senha obrigatória no próximo acesso (só a tela "Trocar senha" desliga)
- Admin do sistema = `is_staff` e `is_superuser` ligados; membro = os dois desligados; `is_active` = ainda faz parte do time

### FalhaLogin
- `email` (texto: o e-mail da pessoa ou, se o texto digitado não é de ninguém, o texto em minúsculas; sem chave estrangeira) e `criada_em`
- Uma linha por senha errada; as que passam da janela de 15 minutos são apagadas na próxima falha registrada, e o login com sucesso apaga as da pessoa

### Rodada
- `numero` (1, 2, 3...; único), `aberta_em`, `fechada_em` (vazio = rodada atual)
- Só pode existir uma rodada aberta por vez

### Troca
- `rodada`: em qual rodada aconteceu
- `titular`: de quem era a vez
- `executor`: quem realmente trocou (igual ao titular quando não há cobertura)
- `data_hora`, `observacao`
- `registrada_por`: quem lançou no sistema
- Regra: um titular só pode ter **uma** troca por rodada

### Ausencia
- `usuario`, `inicio`, `fim` (vazio = em aberto)
- O banco recusa fim antes do início; a sobreposição da mesma pessoa é recusada na validação

### Escala de sábado (app `escala`)
- `ConfiguracaoEscala`: linha única, que não se apaga; `inicio` (um sábado) e `primeiro` (primeira pessoa da fila). Trava depois do primeiro sábado congelado
- `SabadoSemEscala`: `data` (única), `motivo` (feriado, imprevisto ou outro) e `passa_para_proximo`
- `SabadoDuasPessoas`: `data` (única)
- `SabadoFechado`: o sábado congelado, só para consulta no admin. `data` (única), `manha`, `tarde`, `sem_escala`, `motivo`, `passa_para_proximo`, `vagas` (1 ou 2), `cursor_depois` (posição da última pessoa vista) e `fechado_em`
- `PuladoNoSabado`: quem foi pulado por ausência num sábado congelado (uma linha por pessoa e sábado)
- `TrocaSabado`: `pessoa_a`, `data_a`, `turno_a` e `pessoa_b`, `data_b`, `turno_b` (manhã ou tarde); `tipo` (combinada ou emergência); `registrada_por`, `registrada_em`; `desfeita_em`, `desfeita_por` (vazio = ativa). O banco recusa pessoas iguais e datas iguais
- As ligações com `Usuario` impedem apagar a pessoa (PROTECT); nenhuma troca de sábado é apagada

---

## 4. Como o "devendo" é calculado

Para cada pessoa X, olhando todo o histórico:

```
saldo(X) = (vezes em que X foi coberto por outro)
         − (vezes em que X cobriu outro)
```

- Saldo positivo: X deve trocas.
- Saldo negativo: X tem trocas a receber.
- Quando X cobre a vez de quem o cobriu antes, as duas pontas se anulam.
- Conta o histórico inteiro, não só a rodada. A tela mostra só "devendo N" (N > 0); crédito não aparece.

Vantagem: se um registro for corrigido, o saldo se acerta sozinho. Não existe número digitado à mão para ficar errado.

---

## 5. Lógica da vez (resumo)

1. Pega a rodada aberta e confere: se já está completa, fecha e abre a próxima; se não houver rodada, abre a primeira.
2. Candidatos = usuários ativos, com ordem, em ordem crescente.
3. Cada um recebe um estado: **já trocou** (tem troca nesta rodada); **ausente** (ausência cadastrada para hoje); **pulado** (presente, sem troca, com ordem menor que a do último que trocou na rodada); o primeiro que sobrar é a **vez**; os demais ficam **aguardando**. A lista de ausentes vem das ausências cadastradas (`ausentes_hoje`).
4. Se não sobrar ninguém, não há vez.
5. Quando ninguém está na vez nem aguardando, e há pelo menos um presente, a rodada fecha e outra abre.
6. Ausentes e pulados ficam fora do fechamento e voltam no lugar de sempre na rodada seguinte, sem prioridade e sem dívida. A data de volta não entra na conta.

---

## 6. Módulos (uma branch + um Pull Request por módulo)

**Plano original** (todos entregues; está aqui como histórico):

| # | Módulo | O que entregava | Situação |
|---|---|---|---|
| 1 | Base, CI e deploy | Projeto Django, `Usuario` próprio criado vazio (evita uma migração difícil depois; hoje tem `ordem`, `ordem_escala`, matrícula etc.), SQLite local, Gunicorn + WhiteNoise, Tailwind CLI, `CLAUDE.md`, ruff + testes e **CI no GitHub Actions (lint + testes)**, e o deploy no Railway | Entregue; no ar, com deploy da `main` depois do CI |
| 2 | Usuários e login | Login por e-mail (sem nome de usuário), campo `ordem`, login/logout, cadastro só pelo admin, permissão admin × membro, tela inicial protegida, comando que cria a equipe de teste | Entregue; o login hoje também aceita matrícula (módulo 9) |
| 3 | Fila e "de quem é a vez" | Rodada, regra da vez, tela com "Vez de: fulano". Testes pesados aqui | Entregue; a regra de ausência mudou para "sempre para a frente" (seções 2 e 5) |
| 4 | Registrar troca e histórico | Botão "troquei o galão", cobertura, lista de histórico, saldo de dívida | Entregue |
| 5 | Ausências | Cadastro de férias/faltas (só admin) e integração com a fila | Entregue |
| 6 | Acabamento | Telas finais e revisão geral | Feito aos poucos, em pedidos numerados (reforma das telas, celular, mensagens); segue por pedido |

**O que veio depois:**

| # | Módulo | O que entrega | Situação |
|---|---|---|---|
| 7 | Escala de sábado | Rodízio por posição, sábados sem escala e com 2 pessoas, sábados congelados (comando `congelar_escala`), trocas de sábado (registrar, desfazer, histórico, admin) e as telas "Escala", "Próximos sábados", "Trocar de sábado", "Trocas" e "Regras da escala" | Entregue |
| 8 | Página pública e identidade | Página em `/` para quem não entrou, logo "interseção", ícone da aba azul e tela de entrada com o cartão centralizado | Entregue |
| 9 | Login por matrícula | Campo único "E-mail ou matrícula", bloqueio de tentativas por pessoa (matrícula e e-mail contam juntos) e mensagem única; o e-mail continua cadastrado | Entregue |
| 10 | Segurança das telas logadas | Telas de quem está logado sem cache do navegador | Entregue |

Antes de cada tela nova, mostro uma prévia visual para você aprovar.

---

## 7. Quem faz o quê

- **Mateus (dono do projeto):** decide, aprova as prévias visuais e conduz o fluxo com quatro frases: "leia o task.md e execute" (ao Claude Code), "feito" (ao analista), "faz o merge do PR #N" (ao Claude Code) e "mesclou" (ao analista).
- **Claude (analista, conversa separada):** investiga, escreve os pedidos numerados em `pedidos/` (arquivos `.txt`, com a lista "LEIA ANTES DE EDITAR") e atualiza o `task.md`, que aponta para o pedido atual. Lê o `RELATORIO.md`, confere o diff do PR e o CI no GitHub e diz se pode mesclar. Não programa o projeto.
- **Claude Code (programador):** lê o `task.md` e o pedido, programa, testa, abre o Pull Request e escreve o `RELATORIO.md`. **O merge é sempre dele**, e só depois do "faz o merge". Segue o `CLAUDE.md` na raiz do repositório, que tem as regras de trabalho.

**Fluxo de cada pedido:** analista escreve o pedido e atualiza o `task.md` → Mateus diz "leia o task.md e execute" ao Claude Code → Claude Code programa, abre o PR e escreve o `RELATORIO.md` → Mateus diz "feito" ao analista → analista confere o relatório, o diff e o CI e libera → Mateus diz "faz o merge do PR #N" ao Claude Code → Claude Code mescla (merge commit, sem squash), apaga a branch e passa o link do CI da `main` → Mateus diz "mesclou" ao analista, que confere a `main`.

`pedidos/`, `task.md` e `RELATORIO.md` ficam só no computador do Mateus, fora do Git.

**Combinados:** passo a passo com confirmação ("1,1"), conceito explicado junto com o código, prévia visual antes de cada tela nova e documentação completa só quando você pedir.

---

## 8. Pontos a confirmar

- **Dívida ("devendo"):** a leitura da planilha atual (um colega com 1 troca devida e uma troca fora da ordem) foi entendida como cobertura. Vale confirmar com o time.
- **Ausência:** a regra "sempre para a frente" (PR #25) substituiu a de 25/10/2026 ("o ausente volta na posição fixa"): hoje quem fica para trás é pulado, volta na próxima rodada e não deve nada (ver seções 2 e 5).
- **Privacidade:** como o repositório é público, nomes reais do time não entram no repositório (código, testes, docs). Os dados reais ficam só no banco de produção.

---

## 9. Estrutura de pastas

```
galao-helpdesk/
├── CLAUDE.md                  regras permanentes de trabalho do Claude Code
├── README.md                  como rodar, variáveis de ambiente e deploy
├── estrutura.md               este documento
├── .env.example               variáveis de ambiente (só valores falsos de exemplo)
├── .github/workflows/ci.yml   CI: ruff, check, migrações pendentes, pytest (PostgreSQL) e gunicorn
├── manage.py                  comandos do Django
├── pyproject.toml             configuração do pytest e do ruff
├── conftest.py                fixtures e senha falsa dos testes
├── requirements.txt           dependências de produção (requirements-dev.txt: + pytest e ruff)
├── .python-version            Python 3.13
├── config/                    settings.py, urls.py (todas as rotas), wsgi.py e asgi.py
├── core/                      página inicial "/" (pública ou galão), /saude/ e o middleware sem cache
├── fila/                      GALÃO: models.py, regras.py (vez, rodada, dívida), views, forms e admin
├── escala/                    ESCALA DE SÁBADO: models.py, calculo.py, trocas.py, datas.py, views, forms, admin e o comando congelar_escala
├── usuarios/                  LOGIN: models.py (Usuario, FalhaLogin), backends.py, limite.py, middleware.py (troca de senha), forms, admin e o comando criar_equipe_de_teste
├── templates/                 HTML: base.html, partials (_cabecalho, _logo...), e as pastas core, fila, escala, publica e registration
├── static_src/input.css       entrada do Tailwind (tokens de cor no @theme)
└── static/                    css/output.css (gerado pelo Tailwind) e img/ (favicon e ícone)
```

- **Regras de negócio:** `fila/regras.py` (galão), `escala/calculo.py`, `escala/trocas.py` e `escala/datas.py` (escala) e `usuarios/limite.py` (bloqueio de tentativas).
- **Testes:** pasta `tests/` dentro de cada app (`core`, `fila`, `escala` e `usuarios`). As migrações ficam em `migrations/`, também dentro de cada app.
- **CSS gerado:** `static/css/output.css` vai para o Git e é regerado com `./tools/tailwindcss.exe -i static_src/input.css -o static/css/output.css --minify`.
- **Fora do Git:** `.env`, `db.sqlite3`, `.venv/`, `tools/` (executável do Tailwind), `staticfiles/`, os caches, `pedidos/`, `task.md` e `RELATORIO.md`.

---

## 10. Porte e risco

Staging: não (uso interno, cerca de 8 pessoas). Monitoramento de erros: não por enquanto. Testes de navegador (Playwright): não. LGPD: não se aplica (só dados da equipe, sem público externo). Backup do banco: a conferir. Reavaliar quando houver público externo, e-mail para a equipe ou mais pessoas usando.
