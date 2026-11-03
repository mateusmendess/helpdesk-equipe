"""Pedido 44: so quem esta na fila e executor; o chefe registra a dos outros."""

import pytest

from fila.models import Troca
from fila.regras import de_quem_e_a_vez, registrar_troca, rodada_atual

pytestmark = pytest.mark.django_db

URL = "/trocas/nova/"
SO_DA_FILA = "Só quem está na fila do galão pode ser quem trocou."


@pytest.fixture
def chefe(django_user_model):
    return django_user_model.objects.create_user(
        email="chefe@exemplo.test", first_name="Chefe"
    )


def postar(client, logado, vez, **dados):
    client.force_login(logado)
    return client.post(URL, {"titular": vez.pk, "observacao": "", **dados})


def test_chefe_nao_ve_fui_eu_e_ve_outra_pessoa_marcada(client, equipe, chefe):
    client.force_login(chefe)

    html = client.get(URL).content.decode()

    assert "Fui eu" not in html
    assert 'value="eu"' not in html
    assert 'value="outra" checked' in html
    assert "Foi outra pessoa" in html
    assert "passa a dever 1 troca" in html
    assert "Pessoa 1" in html


def test_pessoa_da_fila_ve_as_duas_opcoes(client, equipe):
    client.force_login(equipe[2])

    html = client.get(URL).content.decode()

    assert "Fui eu" in html
    assert "Foi outra pessoa" in html


def test_chefe_registra_a_troca_de_outra_pessoa(client, equipe, chefe):
    resposta = postar(client, chefe, equipe[0], quem="outra", executor=equipe[1].pk)

    assert resposta.status_code == 302
    troca = Troca.objects.get()
    assert (troca.titular, troca.executor, troca.registrada_por) == (
        equipe[0],
        equipe[1],
        chefe,
    )


def test_chefe_com_fui_eu_nao_grava(client, equipe, chefe):
    resposta = postar(client, chefe, equipe[0], quem="eu")

    assert resposta.status_code == 200
    assert not Troca.objects.exists()
    assert resposta.context["form"].errors["quem"] == [SO_DA_FILA]
    assert SO_DA_FILA in resposta.content.decode()


def test_chefe_como_executor_na_lista_nao_grava(client, equipe, chefe):
    resposta = postar(client, chefe, equipe[0], quem="outra", executor=chefe.pk)

    assert resposta.status_code == 200
    assert not Troca.objects.exists()
    assert resposta.context["form"].errors["executor"] == [SO_DA_FILA]


@pytest.mark.parametrize("quem", ["eu", "outra"])
def test_pessoa_da_fila_registra_as_duas_opcoes(client, equipe, quem):
    dados = {"quem": quem}
    if quem == "outra":
        dados["executor"] = equipe[3].pk

    resposta = postar(client, equipe[2], equipe[0], **dados)

    assert resposta.status_code == 302
    troca = Troca.objects.get()
    assert troca.executor == (equipe[2] if quem == "eu" else equipe[3])


def test_regra_do_servidor_recusa_executor_sem_ordem(equipe, chefe):
    with pytest.raises(Exception) as erro:
        registrar_troca(equipe[0], chefe, chefe)

    assert SO_DA_FILA in str(erro.value)
    assert not Troca.objects.exists()
    assert de_quem_e_a_vez() == equipe[0]


def test_admin_do_django_aceita_qualquer_pessoa_ativa(
    client, equipe, chefe, admin_usuario
):
    troca = Troca(
        rodada=rodada_atual(),
        titular=equipe[0],
        executor=chefe,
        registrada_por=admin_usuario,
    )

    troca.full_clean()
    troca.save()

    assert Troca.objects.get().executor == chefe
