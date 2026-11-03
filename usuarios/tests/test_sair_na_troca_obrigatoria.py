import re

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

FORM_SAIR = re.compile(
    r'<form method="post" action="/sair/"[^>]*>\s*'
    r'<input type="hidden" name="csrfmiddlewaretoken" value="[^"]+">\s*'
    r"<button[^>]*>\s*Sair\s*</button>\s*</form>"
)


# Classes so do botao "Sair" do bloco da troca obrigatoria (o do menu e outro).
BOTAO_SAIR_DA_TROCA = "border-2 border-tinta bg-white px-4 font-semibold"


def tela_de_senha(client, usuario):
    client.force_login(usuario)
    resposta = client.get(reverse("password_change"))
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_troca_obrigatoria_tem_o_botao_sair_e_nao_tem_voltar(client, membro):
    membro.precisa_trocar_senha = True
    membro.save()

    conteudo = tela_de_senha(client, membro)

    assert FORM_SAIR.search(conteudo)
    assert BOTAO_SAIR_DA_TROCA in conteudo
    assert 'aria-label="Menu da conta"' not in conteudo
    assert "Voltar" not in conteudo


def test_troca_normal_tem_voltar_e_nao_tem_sair(client, membro):
    conteudo = tela_de_senha(client, membro)

    # O "Sair" do menu da conta existe; o botao da troca obrigatoria nao.
    assert 'aria-label="Menu da conta"' in conteudo
    assert BOTAO_SAIR_DA_TROCA not in conteudo
    assert "Voltar" in conteudo


def test_sair_na_troca_obrigatoria_encerra_a_sessao(client, membro):
    membro.precisa_trocar_senha = True
    membro.save()
    client.force_login(membro)

    resposta = client.post(reverse("logout"))

    assert resposta.status_code == 302
    assert resposta.url == reverse("login")
    # Sem sessao: "/" mostra a pagina publica e a de senha volta a pedir o login.
    inicio = client.get(reverse("home"))
    assert "publica/inicio.html" in [t.name for t in inicio.templates]
    depois = client.get(reverse("password_change"))
    assert depois.status_code == 302
    assert depois.url.startswith(reverse("login"))


# --- Pedido 43: cabecalho e cartao da tela "Trocar senha" ---


def test_tela_de_senha_sem_cartao_branco(client, membro):
    conteudo = tela_de_senha(client, membro)

    assert "<section" not in conteudo.split("</header>")[1]


def test_menu_da_conta_leva_a_tela_com_menu_e_voltar(client, membro):
    conteudo = tela_de_senha(client, membro)

    assert 'aria-label="Menu da conta"' in conteudo
    assert "Voltar" in conteudo
