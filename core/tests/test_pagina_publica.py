import re

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

TITULO = "Quem faz o quê, sem precisar perguntar."


def publica(client):
    resposta = client.get(reverse("home"))
    assert resposta.status_code == 200
    return resposta.content.decode()


def test_anonimo_ve_o_titulo_e_os_botoes_entrar(client):
    html = publica(client)

    assert re.findall(r"<h1[^>]*>(.*?)</h1>", html) == [TITULO]
    entrar = re.findall(r'<a href="([^"]+)"[^>]*>Entrar</a>', html)
    assert entrar == [reverse("login")] * 3
    assert "<title>Help Desk Equipe</title>" in html
    assert '<meta name="description" content="O sistema da equipe' in html


def test_logado_continua_vendo_o_galao(client, membro):
    client.force_login(membro)

    resposta = client.get(reverse("home"))

    nomes = [t.name for t in resposta.templates]
    assert resposta.status_code == 200
    assert "core/home.html" in nomes and "publica/inicio.html" not in nomes


def test_sem_dado_do_banco_e_sem_consulta(client, membro, django_assert_num_queries):
    with django_assert_num_queries(0):
        html = publica(client)

    assert "Rodada" not in html
    assert membro.first_name not in html and membro.email not in html


@pytest.mark.parametrize(
    "nome",
    [
        "historico",
        "registrar_troca",
        "escala",
        "escala_trocar",
        "escala_regras",
        "escala_proximos",
        "escala_trocas",
    ],
)
def test_telas_logadas_continuam_pedindo_login(client, nome):
    resposta = client.get(reverse(nome))

    assert resposta.status_code == 302
    assert resposta.url.startswith(reverse("login"))


def test_pular_para_o_conteudo_e_um_so_h1(client):
    html = publica(client)

    assert html.count("<h1") == 1
    assert '<a href="#modulos"' in html and ">Pular para o conteúdo</a>" in html
    assert 'id="modulos"' in html


def test_sem_o_bloco_do_proximo_modulo_e_com_os_dois_modulos(client):
    html = publica(client)

    assert "O próximo módulo cabe aqui" not in html and "cabe aqui" not in html
    assert re.findall(r"<h1[^>]*>(.*?)</h1>", html) == [TITULO]
    modulos = re.findall(r"<h3[^>]*>(.*?)</h3>", html)
    assert modulos == ["Galão", "Escala de sábado"]


def test_titulo_novo_e_sem_os_textos_antigos(client):
    html = publica(client)

    assert TITULO in html
    assert "grupo" not in html and "Cada um na sua vez" not in html
    assert "ver a sua vez e a escala." in html


def test_desenho_da_equipe_em_tres_camadas_sem_a_legenda_antiga(client):
    html = publica(client)
    # A pagina inteira nao fala de divida; o desenho vai do aria-hidden a legenda unica.
    desenho = html[
        html.index('<div aria-hidden="true">') : html.index("tudo no mesmo lugar")
    ]

    for pilula in (">Galão<", ">Sábado<", ">Ausências<"):
        assert pilula in desenho
    assert "tudo no mesmo lugar" in html
    assert "Carla estava ausente" not in html
    assert not re.search(r"d[ií]vida|devendo", html, re.IGNORECASE)
