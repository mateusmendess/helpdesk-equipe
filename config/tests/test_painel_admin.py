import re

import pytest
from django.contrib import admin
from django.urls import reverse

from config.admin import PainelAdminSite
from fila.models import Troca

pytestmark = pytest.mark.django_db


def blocos(resposta):
    """(nome do bloco, [nomes dos itens]) na ordem da tela inicial."""
    return [
        (app["name"], [m["name"] for m in app["models"]])
        for app in resposta.context["app_list"]
    ]


def test_tela_inicial_tem_tres_blocos_na_ordem_certa(client, admin_usuario):
    client.force_login(admin_usuario)

    resposta = client.get(reverse("admin:index"))

    assert resposta.status_code == 200
    assert [nome for nome, _ in blocos(resposta)] == [
        "Galão de água",
        "Escala de sábado",
        "Usuarios",
    ]


def test_itens_de_cada_bloco_na_ordem_do_pedido(client, admin_usuario):
    client.force_login(admin_usuario)

    resposta = client.get(reverse("admin:index"))

    assert dict(blocos(resposta)) == {
        "Galão de água": ["Trocas do galão", "Ausências", "Rodadas"],
        "Escala de sábado": [
            "Trocas de sábado",
            "Sábados sem escala",
            "Sábados com 2 pessoas",
            "Sábados fechados",
            "Configuração da escala",
        ],
        "Usuarios": ["Usuários"],
    }


def test_html_da_tela_inicial_mostra_blocos_na_ordem_e_sem_grupos(
    client, admin_usuario
):
    client.force_login(admin_usuario)

    html = client.get(reverse("admin:index")).content.decode()

    # O menu lateral e a tela inicial repetem os nomes; a ordem vale para o 1o de cada.
    posicoes = [html.index(n) for n in ("Galão de água", "Escala de sábado")]
    assert posicoes == sorted(posicoes)
    assert html.index("Escala de sábado") < html.index("Usuarios")
    assert "Autenticação e autorização" not in html
    assert "Authentication and Authorization" not in html
    assert "Grupos" not in html and "/admin/auth/" not in html


def test_menu_lateral_de_outra_tela_tambem_sem_grupos(client, admin_usuario):
    client.force_login(admin_usuario)

    html = client.get(reverse("admin:fila_troca_changelist")).content.decode()

    assert "/admin/auth/group/" not in html
    assert re.search(r"Galão de água.*Escala de sábado.*Usuarios", html, re.S)


def test_grupos_seguem_abrindo_pela_url(client, admin_usuario):
    client.force_login(admin_usuario)

    assert client.get("/admin/auth/group/").status_code == 200
    assert client.get("/admin/auth/group/add/").status_code == 200
    # O campo de grupos na edicao do usuario nao muda.
    resposta = client.get(
        reverse("admin:usuarios_usuario_change", args=[admin_usuario.pk])
    )
    assert resposta.status_code == 200
    assert "groups" in resposta.context["adminform"].form.fields


def test_lista_de_trocas_chama_se_trocas_do_galao(client, admin_usuario):
    client.force_login(admin_usuario)

    html = client.get(reverse("admin:fila_troca_changelist")).content.decode()

    assert "Trocas do galão" in html
    assert Troca._meta.verbose_name == "troca"
    assert Troca._meta.verbose_name_plural == "trocas do galão"


def test_url_do_galao_nao_mudou():
    assert reverse("admin:fila_troca_changelist") == "/admin/fila/troca/"
    assert reverse("admin:fila_ausencia_changelist") == "/admin/fila/ausencia/"
    assert reverse("admin:fila_rodada_changelist") == "/admin/fila/rodada/"


def test_usuario_comum_vai_para_o_login_do_painel(client, membro):
    client.force_login(membro)

    resposta = client.get(reverse("admin:index"))

    assert resposta.status_code == 302
    assert resposta.url.startswith(reverse("admin:login"))


def _app(label, nome, *modelos):
    return {
        "app_label": label,
        "name": nome,
        "models": [{"object_name": m, "name": m} for m in modelos],
    }


def _lista(monkeypatch, apps, app_label=None):
    """Roda o get_app_list do painel sobre uma lista falsa entregue pelo Django."""
    monkeypatch.setattr(
        admin.AdminSite, "get_app_list", lambda self, request, app_label=None: apps
    )
    return PainelAdminSite().get_app_list(None, app_label)


def test_outro_app_futuro_vai_depois_em_ordem_alfabetica(monkeypatch):
    entregue = [  # alfabetica, como o Django entrega
        _app("auth", "Autenticação e autorização", "Group"),
        _app("zeta", "Zeta", "Coisa"),
        _app("escala", "Escala de sábado", "TrocaSabado"),
        _app("beta", "Beta", "Coisa"),
        _app("usuarios", "Usuarios", "Usuario"),
        _app("fila", "Galão de água", "Troca"),
    ]

    apps = _lista(monkeypatch, entregue)

    # "auth" some; os desconhecidos vao depois, por nome.
    assert [a["app_label"] for a in apps] == [
        "fila",
        "escala",
        "usuarios",
        "beta",
        "zeta",
    ]


def test_modelo_fora_da_lista_vai_ao_fim_do_bloco(monkeypatch):
    entregue = [
        _app("fila", "Galão de água", "Ausencia", "Novo", "Rodada", "Troca"),
        _app("escala", "Escala de sábado", "Outro", "SabadoFechado", "TrocaSabado"),
    ]

    apps = _lista(monkeypatch, entregue)

    assert [m["object_name"] for m in apps[0]["models"]] == [
        "Troca",
        "Ausencia",
        "Rodada",
        "Novo",
    ]
    assert [m["object_name"] for m in apps[1]["models"]] == [
        "TrocaSabado",
        "SabadoFechado",
        "Outro",
    ]


def test_pagina_de_um_app_especifico_nao_esconde_o_app(monkeypatch):
    # Com app_label (ex.: /admin/auth/) nada e escondido: so a lista geral.
    entregue = [_app("auth", "Autenticação e autorização", "Group")]

    apps = _lista(monkeypatch, entregue, app_label="auth")

    assert [a["app_label"] for a in apps] == ["auth"]
