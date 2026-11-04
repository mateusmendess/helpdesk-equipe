import logging

import pytest
from django.test import Client
from django.urls import reverse

from conftest import SENHA_DE_TESTE
from fila.models import Troca

pytestmark = pytest.mark.django_db

PROIBIDAS = ["CSRF", "DEBUG", "Proibido", "403"]


def cliente_rigido():
    return Client(enforce_csrf_checks=True)


def test_anonimo_sem_token_ve_tela_amigavel(membro):
    client = cliente_rigido()

    resposta = client.post(
        reverse("login"), {"username": membro.email, "password": SENHA_DE_TESTE}
    )

    texto = resposta.content.decode()
    assert resposta.status_code == 403
    assert "Esta página ficou desatualizada" in texto
    assert "Voltar para a entrada" in texto
    assert f'href="{reverse("login")}"' in texto
    for palavra in PROIBIDAS:
        assert palavra not in texto
    assert "_auth_user_id" not in client.session


def test_logado_sem_token_ve_voltar_ao_inicio(membro):
    client = cliente_rigido()
    client.force_login(membro)
    antes = Troca.objects.count()

    resposta = client.post(reverse("registrar_troca"), {"titular": membro.pk})

    texto = resposta.content.decode()
    assert resposta.status_code == 403
    assert "Voltar ao início" in texto
    assert f'href="{reverse("home")}"' in texto
    assert "Voltar para a entrada" not in texto
    assert Troca.objects.count() == antes


def test_com_token_valido_o_login_continua_funcionando(membro):
    client = cliente_rigido()
    token = client.get(reverse("login")).cookies["csrftoken"].value

    resposta = client.post(
        reverse("login"),
        {
            "username": membro.email,
            "password": SENHA_DE_TESTE,
            "csrfmiddlewaretoken": token,
        },
    )

    assert resposta.status_code == 302
    assert client.session["_auth_user_id"] == str(membro.pk)


def test_falha_grava_uma_linha_de_log_sem_dado_pessoal(membro, caplog):
    client = cliente_rigido()

    with caplog.at_level(logging.WARNING, logger="core.csrf"):
        client.post(
            reverse("login"), {"username": membro.email, "password": SENHA_DE_TESTE}
        )

    linhas = [r for r in caplog.records if r.name == "core.csrf"]
    assert len(linhas) == 1
    assert linhas[0].levelno == logging.WARNING
    msg = linhas[0].getMessage()
    assert "motivo=" in msg and "CSRF" in msg
    assert "metodo=POST" in msg
    assert "caminho=/entrar/" in msg
    assert "cookie_csrf=False" in msg
    assert "cookie_sessao=False" in msg
    for segredo in (membro.email, SENHA_DE_TESTE, "pessoa1"):
        assert segredo not in msg


def test_resposta_403_nao_fica_no_cache(membro):
    resposta = cliente_rigido().post(reverse("login"), {"username": membro.email})

    assert resposta.status_code == 403
    assert "no-store" in resposta["Cache-Control"]
