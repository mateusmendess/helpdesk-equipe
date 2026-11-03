"""Pedido 44: a lista "Fila" do inicio fica dentro de um cartao."""

import re

import pytest

pytestmark = pytest.mark.django_db


def test_fila_dentro_do_cartao_com_todas_as_pessoas(client, equipe):
    client.force_login(equipe[0])

    html = client.get("/").content.decode()

    cartao = re.search(r'<section data-cartao="fila".*?</section>', html, flags=re.S)
    assert cartao
    dentro = cartao.group(0)
    assert 'id="titulo-fila"' in dentro
    assert dentro.count("<li ") == len(equipe)
    assert "data-estado" in dentro
    assert "(você)" in dentro
