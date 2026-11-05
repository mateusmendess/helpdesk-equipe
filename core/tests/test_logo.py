import re
import struct

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse

pytestmark = pytest.mark.django_db

LOGO = "M45.27 16.45A22 22 0 0 1 53.83 31.28"
ANTIGAS = ("M17 7H31", "M17 6H31")
GALAO = "M12 3h8v3l2 2v3"


def html_de(client, nome, usuario=None):
    if usuario is not None:
        client.force_login(usuario)
    resposta = client.get(reverse(nome))
    assert resposta.status_code == 200
    return resposta.content.decode()


def marca(html):
    """O trecho com a marca: o comeco do <header>, ou da tela de entrada."""
    inicio = html.find("<header")
    if inicio < 0:
        inicio = html.index("<main")
    return html[inicio : html.index("Help Desk Equipe", inicio)]


def test_aba_aponta_para_o_favicon_que_existe(client):
    cabeca = html_de(client, "login").split("</head>")[0]

    href = static("img/favicon.svg")
    assert f'<link rel="icon" href="{href}" type="image/svg+xml">' in cabeca
    assert finders.find("img/favicon.svg")


@pytest.mark.parametrize(
    "nome, logado, cor",
    [
        ("home", True, "text-white"),
        ("escala", True, "text-white"),
        ("registrar_troca", True, "text-white"),
        ("login", False, "text-tinta"),
        ("home", False, "text-white"),
    ],
)
def test_marca_e_a_logo_nova(client, membro, nome, logado, cor):
    html = html_de(client, nome, membro if logado else None)
    trecho = marca(html)

    svg = re.search(r'<svg class="([^"]*)" viewBox="0 -3 64 64"[^>]*>', trecho)
    assert svg and cor in svg.group(1).split()
    assert 'aria-hidden="true" focusable="false"' in svg.group(0)
    assert LOGO in trecho and GALAO not in trecho


def test_galao_nao_aparece_na_entrada_nem_no_inicio_logado(client, membro):
    publica = html_de(client, "home")
    entrada = html_de(client, "login")
    galao = html_de(client, "home", membro)

    # O desenho do topo da pagina publica agora e o painel da equipe (sem o jarro).
    assert GALAO not in publica and GALAO not in entrada and GALAO not in galao


@pytest.mark.parametrize(
    "nome, logado",
    [("home", True), ("login", False), ("home", False)],
)
def test_marca_tem_tres_arcos_e_tres_pontos(client, membro, nome, logado):
    trecho = marca(html_de(client, nome, membro if logado else None))

    assert trecho.count("A22 22") == 3
    assert trecho.count('r="9.5"') == 3
    assert not any(antiga in trecho for antiga in ANTIGAS)


def test_favicon_svg_e_o_desenho_novo():
    texto = open(finders.find("img/favicon.svg"), encoding="utf-8").read()

    assert LOGO in texto and texto.count("A22 22") == 3
    assert not any(antiga in texto for antiga in ANTIGAS)


def test_favicon_ico_tem_duas_imagens():
    with open(finders.find("img/favicon.ico"), "rb") as f:
        dados = f.read(6)

    assert dados[:4] == bytes([0, 0, 1, 0])
    assert int.from_bytes(dados[4:6], "little") == 2


def test_apple_touch_icon_e_png_180():
    with open(finders.find("img/apple-touch-icon.png"), "rb") as f:
        dados = f.read(24)

    assert dados[:8] == bytes([137, 80, 78, 71, 13, 10, 26, 10])
    assert struct.unpack(">II", dados[16:24]) == (180, 180)
