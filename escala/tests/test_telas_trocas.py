import re
from datetime import time, timedelta

import pytest
from django.urls import reverse

from escala.models import ConfiguracaoEscala, TrocaSabado
from escala.trocas import registrar_troca

from .conftest import SABADO

pytestmark = pytest.mark.django_db
M = "manha"


def s(k):
    return SABADO + timedelta(weeks=k)


@pytest.fixture
def equipe(django_user_model, hoje):
    pessoas = [
        django_user_model.objects.create_user(
            email=f"pessoa{n}@exemplo.test", first_name=f"Pessoa {n}", ordem_escala=n
        )
        for n in range(1, 8)
    ]
    ConfiguracaoEscala.objects.create(inicio=SABADO, primeiro=pessoas[0])
    hoje(SABADO - timedelta(days=10))
    return pessoas


def html_de(client, usuario, nome, *args):
    client.force_login(usuario)
    resposta = client.get(reverse(nome, args=args))
    assert resposta.status_code == 200
    return resposta.content.decode()


def texto(html):
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def opcoes(html, campo):
    select = re.search(rf'<select name="{campo}".*?</select>', html, flags=re.S)
    assert select, campo
    return [
        t.strip()
        for t in re.findall(
            r'<option value="[^"]+"[^>]*>(.*?)</option>', select.group(0)
        )
    ]


def trocar(p1, p3, por):
    return registrar_troca(p1, s(0), M, p3, s(2), M, por=por)


@pytest.mark.parametrize("nome", ["escala_trocar", "escala_trocas"])
def test_login_obrigatorio(client, nome):
    resposta = client.get(reverse(nome))

    assert resposta.status_code == 302 and resposta.url.startswith("/entrar/")


def test_aba_tem_botao_e_link(client, equipe):
    html = html_de(client, equipe[0], "escala")

    assert f'href="{reverse("escala_trocar")}"' in html
    assert re.search(r'href="/escala/trocas/"[^>]*>Trocas registradas</a>', html)


def test_aba_mostra_no_lugar_de_com_etiqueta(client, equipe):
    p1, p3 = equipe[0], equipe[2]
    trocar(p1, p3, por=p1)

    html = texto(html_de(client, equipe[1], "escala"))

    assert "Manhã 08h às 12h Pessoa 3 no lugar de Pessoa 1 troca" in html
    # No destaque, o "no lugar de" aparece uma vez so (na linha do turno).
    assert html.split("Próximos sábados")[0].count("no lugar de") == 1
    assert f"{s(2):%d/%m} Pessoa 1 no lugar de Pessoa 3 troca" in html


def test_membro_ve_os_proprios_turnos_e_os_dos_outros(client, equipe):
    html = html_de(client, equipe[0], "escala_trocar")

    assert opcoes(html, "meu") == [
        f"{s(0):%d/%m} · manhã · Pessoa 1",
        f"{s(7):%d/%m} · manhã · Pessoa 1",
    ]
    outros = opcoes(html, "outro")
    assert f"{s(1):%d/%m} · manhã · Pessoa 2" in outros
    assert not any("Pessoa 1" in o for o in outros)
    assert 'name="tipo"' not in html
    assert "Sábado que vou assumir" in html
    assert "regras 7.1 e 8" in html


def test_membro_nao_ve_o_sabado_de_hoje(client, equipe, hoje):
    hoje(s(0), time(8))

    html = html_de(client, equipe[0], "escala_trocar")

    assert opcoes(html, "meu") == [f"{s(7):%d/%m} · manhã · Pessoa 1"]


def test_admin_ve_todos_e_o_tipo(client, equipe, admin_usuario):
    html = html_de(client, admin_usuario, "escala_trocar")

    assert len(opcoes(html, "meu")) == 12 == len(opcoes(html, "outro"))
    assert "Primeiro sábado" in html
    assert "Segundo sábado" in html
    assert "Sábado da outra pessoa" not in html
    assert opcoes(html, "tipo") == ["Combinada", "Emergência"]


def test_sem_opcoes(client, equipe, django_user_model):
    fora = django_user_model.objects.create_user(email="pessoa9@exemplo.test")

    html = html_de(client, fora, "escala_trocar")

    assert (
        "Não há sábados para trocar agora." in html
        and "<form" not in html.split("</header>")[1]
    )


def test_registrar_ok_vai_para_as_trocas(client, equipe):
    p1, p3 = equipe[0], equipe[2]
    client.force_login(p1)

    resposta = client.post(
        reverse("escala_trocar"),
        {
            "meu": f"{s(0).isoformat()}|manha|{p1.pk}",
            "outro": f"{s(2).isoformat()}|manha|{p3.pk}",
        },
        follow=True,
    )

    assert resposta.redirect_chain[-1][0] == reverse("escala_trocas")
    assert "Troca registrada: Pessoa 1 ⇄ Pessoa 3" in resposta.content.decode()
    assert TrocaSabado.objects.count() == 1


def test_registrar_com_erro_fica_na_tela(client, equipe):
    p1, p2, p3 = equipe[:3]
    trocar(p1, p3, por=p1)  # outra aba ja trocou o 05/12
    client.force_login(p1)

    resposta = client.post(
        reverse("escala_trocar"),
        {
            "meu": f"{s(0).isoformat()}|manha|{p1.pk}",
            "outro": f"{s(1).isoformat()}|manha|{p2.pk}",
        },
    )

    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "A escala mudou enquanto você preenchia." in html
    assert TrocaSabado.objects.count() == 1


def test_historico_com_os_tres_estados_e_desfazer_so_para_quem_pode(
    client, equipe, hoje, admin_usuario
):
    p1, p2, p3, p4, p5 = equipe[:5]
    feita = registrar_troca(
        p1, s(0), M, p2, s(1), M, por=admin_usuario, tipo="emergencia"
    )
    desfeita = registrar_troca(p3, s(2), M, p4, s(3), M, por=p3)
    ativa = registrar_troca(p5, s(4), M, p1, s(7), M, por=p5)
    hoje(s(1), time(18))
    client.force_login(p4)
    client.post(reverse("escala_desfazer", args=[desfeita.pk]))

    html = html_de(client, p5, "escala_trocas")
    ativas = html[html.index("Troca ativa") : html.index("Histórico")]
    historico = html[html.index("Histórico") :]

    assert texto(ativas).count("⇄") == 2 and "Pessoa 5 ⇄ Pessoa 1" in texto(ativas)
    assert "Desfazer troca" in ativas
    assert (
        "Você pode desfazer até 01/01 (véspera do primeiro sábado). "
        "Depois, só um admin." in texto(ativas)
    )
    linhas = texto(historico)
    assert "Pessoa 5 ⇄ Pessoa 1 02/01 ⇄ 23/01" in linhas
    assert re.search(
        r"Pessoa 3 ⇄ Pessoa 4 .*desfeita por Pessoa 4, 12/12 desfeita", linhas
    )
    assert re.search(
        r"Pessoa 1 ⇄ Pessoa 2 .*emergência · "
        r"registrada por Pessoa Admin, 25/11 às 12:00 feita",
        linhas,
    )
    etiquetas = re.findall(r">(ativa|feita|desfeita)</span>", historico)
    assert sorted(etiquetas) == ["ativa", "desfeita", "feita"]
    assert feita.pk and ativa.pk

    # Quem nao participa nao ve o botao; o admin ve e sem o texto de prazo.
    assert "Desfazer troca" not in html_de(client, p3, "escala_trocas")
    admin = html_de(client, admin_usuario, "escala_trocas")
    assert "Desfazer troca" in admin and "Você pode desfazer" not in admin


def test_desfazer_so_por_post_e_com_mensagem(client, equipe):
    p1, p3 = equipe[0], equipe[2]
    troca = trocar(p1, p3, por=p1)
    url = reverse("escala_desfazer", args=[troca.pk])
    client.force_login(equipe[4])

    assert client.get(url).status_code == 405
    recusado = client.post(url, follow=True)
    assert "Só quem participa da troca" in recusado.content.decode()
    client.force_login(p3)
    aceito = client.post(url, follow=True)
    assert "Troca desfeita." in aceito.content.decode()
    troca.refresh_from_db()
    assert not troca.ativa


def test_desfazer_sem_login_vai_para_entrar_e_a_troca_continua_ativa(client, equipe):
    troca = trocar(equipe[0], equipe[2], por=equipe[0])

    resposta = client.post(reverse("escala_desfazer", args=[troca.pk]))

    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")
    troca.refresh_from_db()
    assert troca.ativa and troca.desfeita_em is None


def test_desfazer_troca_inexistente_da_404_para_membro_e_admin(
    client, equipe, admin_usuario
):
    url = reverse("escala_desfazer", args=[99999])
    for usuario in (equipe[0], admin_usuario):
        client.force_login(usuario)
        assert client.post(url).status_code == 404


def test_desfazer_por_terceiro_e_recusado_e_a_troca_continua_ativa(client, equipe):
    troca = trocar(equipe[0], equipe[2], por=equipe[0])
    client.force_login(equipe[4])

    resposta = client.post(reverse("escala_desfazer", args=[troca.pk]), follow=True)

    assert "Só quem participa da troca" in resposta.content.decode()
    troca.refresh_from_db()
    assert troca.ativa and troca.desfeita_em is None and troca.desfeita_por is None


def test_historico_pagina_de_30_em_30(client, equipe, admin_usuario):
    for n in range(31):
        TrocaSabado.objects.create(
            pessoa_a=equipe[0],
            data_a=s(n),
            turno_a=M,
            pessoa_b=equipe[1],
            data_b=s(n + 40),
            turno_b=M,
            registrada_por=admin_usuario,
        )

    primeira = html_de(client, admin_usuario, "escala_trocas")
    client.force_login(admin_usuario)
    segunda = client.get(reverse("escala_trocas") + "?pagina=2").content.decode()

    historico = primeira[primeira.index("Histórico") :]
    assert historico.count("<li") == 30 and "Mais antigas" in primeira
    assert segunda[segunda.index("Histórico") :].count("<li") == 1
    assert "Mais recentes" in segunda


def descritos_por(html, nome):
    """Ids em aria-describedby do <select> com esse name."""
    tag = re.search(rf'<select[^>]*name="{nome}"[^>]*>', html)[0]
    achado = re.search(r'aria-describedby="([^"]*)"', tag)
    return achado[1].split() if achado else []


def test_trocar_sem_escolher_liga_o_erro_a_cada_campo(client, equipe):
    client.force_login(equipe[0])

    html = client.post(
        reverse("escala_trocar"), {"meu": "", "outro": ""}
    ).content.decode()

    for nome in ("meu", "outro"):
        tag = re.search(rf'<select[^>]*name="{nome}"[^>]*>', html)[0]
        assert descritos_por(html, nome) == [f"erro-{nome}"]
        assert 'aria-invalid="true"' in tag
        assert html.count(f'id="erro-{nome}"') == 1


def test_trocar_sem_erro_nao_liga_nada(client, equipe):
    html = html_de(client, equipe[0], "escala_trocar")

    assert descritos_por(html, "meu") == [] == descritos_por(html, "outro")
    assert 'id="erro-' not in html


def test_link_das_regras_fica_fora_do_paragrafo_com_alvo_de_toque(client, equipe):
    html = html_de(client, equipe[0], "escala_trocar")

    link = re.search(
        rf'<a href="{reverse("escala_regras")}" class="([^"]*)">Regras da escala</a>',
        html,
    )
    assert link and "min-h-11" in link[1].split()
    # Não está dentro de nenhum <p>.
    antes = html[: link.start()]
    assert antes.rfind("<p") <= antes.rfind("</p>")
    # Vem logo antes do botão de registrar.
    assert html.index("Regras da escala") < html.index("Registrar troca</button>")


# --- Pedido 43: grupos (optgroup) para o admin em "Trocar de sabado" ---

AJUDA_ADMIN = (
    "A troca é entre os dois sábados: pode ser o seu com o de outra pessoa, "
    "ou o de duas outras pessoas."
)


def grupos(html, campo):
    select = re.search(rf'<select name="{campo}".*?</select>', html, flags=re.S)
    assert select, campo
    return re.findall(r'<optgroup label="([^"]+)"', select.group(0))


def admin_da_escala(equipe):
    # A Pessoa 1 vira admin: tem turnos proprios (grupo "Meus sábados").
    equipe[0].is_staff = equipe[0].is_superuser = True
    equipe[0].save()
    return equipe[0]


def test_admin_ve_grupos_na_ordem_certa_de_cada_campo(client, equipe):
    admin = admin_da_escala(equipe)

    html = html_de(client, admin, "escala_trocar")

    assert grupos(html, "meu") == ["Meus sábados", "Outras pessoas"]
    assert grupos(html, "outro") == ["Outras pessoas", "Meus sábados"]
    assert len(opcoes(html, "meu")) == 12 == len(opcoes(html, "outro"))
    meu = re.search(r'<select name="meu".*?</select>', html, flags=re.S).group(0)
    assert "Escolha um sábado" in meu.split("<optgroup")[0]  # continua o primeiro
    meus_sabados = meu.split("</optgroup>")[0]
    assert "Pessoa 1" in meus_sabados and "Pessoa 2" not in meus_sabados
    assert AJUDA_ADMIN in html


def test_admin_sem_turno_proprio_nao_ve_grupo_vazio(client, equipe, admin_usuario):
    html = html_de(client, admin_usuario, "escala_trocar")

    assert grupos(html, "meu") == ["Outras pessoas"]
    assert grupos(html, "outro") == ["Outras pessoas"]


def test_valor_das_opcoes_do_admin_nao_muda_e_cada_grupo_segue_a_data(client, equipe):
    admin = admin_da_escala(equipe)

    html = html_de(client, admin, "escala_trocar")

    valores = re.findall(r'<option value="([^"]+)"', html.split('name="outro"')[0])
    assert f"{s(0).isoformat()}|manha|{admin.pk}" in valores
    meus = [v for v in valores if v.endswith(f"|{admin.pk}")]
    assert meus == sorted(meus)
    assert all(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}\|(manha|tarde)\|\d+", v) for v in valores
    )


def test_admin_troca_o_proprio_sabado_com_o_de_outra_pessoa(client, equipe):
    admin, p3 = admin_da_escala(equipe), equipe[2]
    client.force_login(admin)

    resposta = client.post(
        reverse("escala_trocar"),
        {
            "meu": f"{s(0).isoformat()}|manha|{admin.pk}",
            "outro": f"{s(2).isoformat()}|manha|{p3.pk}",
            "tipo": "combinada",
        },
    )

    assert resposta.status_code == 302
    assert TrocaSabado.objects.count() == 1


def test_membro_continua_com_lista_plana_e_sem_ajuda_de_admin(client, equipe):
    html = html_de(client, equipe[0], "escala_trocar")

    assert "<optgroup" not in html
    assert AJUDA_ADMIN not in html
    assert not any("Pessoa 1" in o for o in opcoes(html, "outro"))


def test_rotulos_do_admin_e_do_membro(client, equipe):
    admin = admin_da_escala(equipe)

    html_admin = html_de(client, admin, "escala_trocar")
    html_membro = html_de(client, equipe[1], "escala_trocar")

    assert ">Primeiro sábado</label>" in html_admin
    assert ">Segundo sábado</label>" in html_admin
    assert ">Meu sábado</label>" not in html_admin
    assert ">Meu sábado</label>" in html_membro
    assert ">Sábado que vou assumir</label>" in html_membro
    assert "Primeiro sábado" not in html_membro
