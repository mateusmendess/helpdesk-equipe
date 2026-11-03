"""Guardas do hash de senha: rapido nos testes, forte em producao.

O conftest.py liga um hasher rapido (MD5) em todos os testes para nao pagar
~0,5 s por senha. Estes testes garantem que (a) o padrao de producao continua
forte, (b) a troca para o hasher rapido esta mesmo ativa e (c) o login funciona
ponta a ponta com o hash real.
"""

import pytest
from django.contrib.auth.hashers import get_hasher
from django.urls import reverse

from conftest import SENHA_DE_TESTE

pytestmark = pytest.mark.django_db


@pytest.mark.hash_real
def test_hasher_de_producao_e_pbkdf2_forte():
    hasher = get_hasher()

    assert hasher.algorithm == "pbkdf2_sha256"
    assert hasher.iterations >= 1_000_000


def test_nos_testes_a_senha_usa_o_hasher_rapido(membro):
    assert get_hasher().algorithm == "md5"
    assert membro.password.startswith("md5$")


@pytest.mark.hash_real
def test_login_ponta_a_ponta_com_o_hash_real(client, membro):
    assert membro.password.startswith("pbkdf2_sha256$")

    resposta = client.post(
        reverse("login"), {"username": membro.email, "password": SENHA_DE_TESTE}
    )

    assert resposta.status_code == 302
    assert resposta.url == reverse("home")
    assert "_auth_user_id" in client.session
