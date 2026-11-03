import re

import pytest
from django.urls import reverse

from conftest import SENHA_DE_TESTE

pytestmark = pytest.mark.django_db

SENHA_ERRADA = SENHA_DE_TESTE + "-errada"
NOVA_SENHA = SENHA_DE_TESTE + "-nova"


def campo(html, nome):
    """A tag <input> do campo com esse name."""
    return re.search(rf'<input[^>]*name="{nome}"[^>]*>', html, flags=re.S)[0]


def descritos_por(html, nome):
    """Ids em aria-describedby do campo (vazio se não tiver)."""
    achado = re.search(r'aria-describedby="([^"]*)"', campo(html, nome))
    return achado[1].split() if achado else []


def test_trocar_senha_liga_cada_erro_ao_seu_campo(client, membro):
    client.force_login(membro)

    # Senha atual errada, nova fraca e confirmação diferente: erro nos três.
    html = client.post(
        reverse("password_change"),
        {
            "old_password": SENHA_ERRADA,
            "new_password1": "ab1",
            "new_password2": NOVA_SENHA,
        },
    ).content.decode()

    for nome in ("old_password", "new_password1", "new_password2"):
        erro = f"erro-{nome}"
        assert erro in descritos_por(html, nome)
        assert html.count(f'id="{erro}"') == 1
    # A ajuda da nova senha continua ligada junto com o erro.
    assert "ajuda-nova-senha" in descritos_por(html, "new_password1")
    assert html.count('id="ajuda-nova-senha"') == 1


def test_trocar_senha_sem_erro_so_liga_a_ajuda(client, membro):
    client.force_login(membro)

    html = client.get(reverse("password_change")).content.decode()

    assert descritos_por(html, "new_password1") == ["ajuda-nova-senha"]
    assert descritos_por(html, "old_password") == []
    assert 'id="erro-' not in html


def test_entrar_liga_o_erro_do_campo(client):
    # Texto vazio: erro de "campo obrigatório" no próprio campo.
    html = client.post(
        reverse("login"), {"username": "", "password": SENHA_ERRADA}
    ).content.decode()

    assert descritos_por(html, "username") == ["erro-username"]
    assert html.count('id="erro-username"') == 1
    assert descritos_por(html, "password") == []
