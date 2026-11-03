from datetime import timedelta

import pytest
from django.contrib.messages import get_messages
from django.db.models import F
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from conftest import SENHA_DE_TESTE
from usuarios.limite import esta_bloqueado, ip_do_pedido
from usuarios.models import FalhaLogin

pytestmark = pytest.mark.django_db

SENHA_ERRADA = SENHA_DE_TESTE + "-errada"

MENSAGEM_BLOQUEIO = "Muitas tentativas de entrada. Tente de novo em alguns minutos."
MENSAGEM_ERRO = "E-mail, matrícula ou senha incorretos."

# IPs de documentacao (RFC 5737), nunca de alguem de verdade.
IP_A = "203.0.113.7"
IP_B = "198.51.100.4"


def entrar(client, email, senha, ip=IP_A):
    return client.post(
        reverse("login"), {"username": email, "password": senha}, REMOTE_ADDR=ip
    )


def entrar_no_painel(client, email, senha, ip=IP_A):
    return client.post(
        reverse("admin:login"),
        {"username": email, "password": senha},
        REMOTE_ADDR=ip,
    )


def errar(client, email, vezes, ip=IP_A):
    for _ in range(vezes):
        entrar(client, email, SENHA_ERRADA, ip)


def esta_logado(client):
    return "_auth_user_id" in client.session


def passar(segundos):
    """Simula o tempo passando: todas as falhas ficam mais antigas."""
    FalhaLogin.objects.update(criada_em=F("criada_em") - timedelta(seconds=segundos))


# 1. Cinco erros: espera de 1 minuto


def test_cinco_erros_esperam_um_minuto_e_depois_entra(client, membro):
    errar(client, "pessoa1@exemplo.test", 5)

    passar(55)
    resposta = entrar(client, "pessoa1@exemplo.test", SENHA_DE_TESTE)
    assert MENSAGEM_BLOQUEIO in resposta.content.decode()
    assert not esta_logado(client)

    passar(10)
    assert entrar(client, "pessoa1@exemplo.test", SENHA_DE_TESTE).status_code == 302
    assert esta_logado(client)


# 2. Escada: cada erro novo dobra a espera, ate o teto de 15 minutos


@pytest.mark.parametrize(
    "erros, minutos",
    [(5, 1), (6, 2), (7, 4), (8, 8), (9, 15), (12, 15), (40, 15)],
)
def test_escada_de_espera(erros, minutos):
    agora = timezone.now()
    FalhaLogin.objects.bulk_create(
        FalhaLogin(email="pessoa1@exemplo.test", criada_em=agora) for _ in range(erros)
    )

    passar(minutos * 60 - 5)
    assert esta_bloqueado("pessoa1@exemplo.test")

    passar(10)
    assert not esta_bloqueado("pessoa1@exemplo.test")


def test_quatro_erros_nao_esperam():
    FalhaLogin.objects.bulk_create(
        FalhaLogin(email="pessoa1@exemplo.test") for _ in range(4)
    )

    assert not esta_bloqueado("pessoa1@exemplo.test")


def test_errar_depois_da_espera_soma_um_e_dobra(client, membro):
    errar(client, "pessoa1@exemplo.test", 5)
    passar(65)

    errar(client, "pessoa1@exemplo.test", 1)

    assert FalhaLogin.objects.count() == 6
    passar(115)
    assert MENSAGEM_BLOQUEIO in (
        entrar(client, "pessoa1@exemplo.test", SENHA_DE_TESTE).content.decode()
    )
    passar(10)
    errar(client, "pessoa1@exemplo.test", 1)
    assert FalhaLogin.objects.count() == 7
    passar(4 * 60 - 5)
    assert esta_bloqueado("pessoa1@exemplo.test")
    passar(10)
    assert entrar(client, "pessoa1@exemplo.test", SENHA_DE_TESTE).status_code == 302


# 3. Uma hora sem erros zera; sucesso zera


def test_uma_hora_sem_erros_zera(client, membro):
    errar(client, "pessoa1@exemplo.test", 8)
    passar(61 * 60)

    # Os 8 erros antigos nao contam: um erro novo e so o primeiro.
    errar(client, "pessoa1@exemplo.test", 1)

    assert not esta_bloqueado("pessoa1@exemplo.test")
    assert FalhaLogin.objects.count() == 1


def test_sucesso_depois_da_espera_zera(client, membro):
    errar(client, "pessoa1@exemplo.test", 5)
    passar(65)
    assert entrar(client, "pessoa1@exemplo.test", SENHA_DE_TESTE).status_code == 302

    assert FalhaLogin.objects.count() == 0
    client.post(reverse("logout"))
    errar(client, "pessoa1@exemplo.test", 4)
    assert entrar(client, "pessoa1@exemplo.test", SENHA_DE_TESTE).status_code == 302


# 4. Tentativas durante a espera nao sao registradas


def test_tentativas_durante_a_espera_nao_registram(client, admin_usuario):
    errar(client, "admin@exemplo.test", 5)

    errar(client, "admin@exemplo.test", 2)
    entrar_no_painel(client, "admin@exemplo.test", SENHA_ERRADA)
    entrar_no_painel(client, "admin@exemplo.test", SENHA_DE_TESTE)

    assert FalhaLogin.objects.count() == 5
    assert not esta_logado(client)
    # A espera continua sendo de 1 minuto, contada do 5o erro.
    passar(65)
    assert (
        entrar_no_painel(client, "admin@exemplo.test", SENHA_DE_TESTE).status_code
        == 302
    )


# 5. Limite por IP


def errar_em_contas_diferentes(client, quantas, ip=IP_A):
    for numero in range(quantas):
        entrar(client, f"outra{numero}@exemplo.test", SENHA_ERRADA, ip)


def test_vinte_erros_do_mesmo_ip_bloqueiam_outra_conta(client, membro):
    errar_em_contas_diferentes(client, 20)

    resposta = entrar(client, "pessoa1@exemplo.test", SENHA_DE_TESTE)

    assert MENSAGEM_BLOQUEIO in resposta.content.decode()
    assert not esta_logado(client)
    # A tentativa durante o bloqueio do IP nao e registrada.
    errar(client, "pessoa1@exemplo.test", 1)
    assert FalhaLogin.objects.count() == 20


def test_ip_bloqueado_vale_no_painel(client, admin_usuario):
    errar_em_contas_diferentes(client, 20)

    resposta = entrar_no_painel(client, "admin@exemplo.test", SENHA_DE_TESTE)

    assert resposta.status_code == 200
    assert not esta_logado(client)
    assert FalhaLogin.objects.count() == 20


def test_outro_ip_nao_e_afetado(client, membro):
    errar_em_contas_diferentes(client, 20)

    resposta = entrar(client, "pessoa1@exemplo.test", SENHA_DE_TESTE, ip=IP_B)

    assert resposta.status_code == 302


def test_dezenove_erros_do_ip_nao_bloqueiam(client, membro):
    errar_em_contas_diferentes(client, 19)

    assert entrar(client, "pessoa1@exemplo.test", SENHA_DE_TESTE).status_code == 302


def test_bloqueio_do_ip_acaba_quando_os_erros_saem_da_janela(client, membro):
    errar_em_contas_diferentes(client, 20)
    passar(14 * 60)
    assert MENSAGEM_BLOQUEIO in (
        entrar(client, "pessoa1@exemplo.test", SENHA_DE_TESTE).content.decode()
    )

    passar(61)

    assert entrar(client, "pessoa1@exemplo.test", SENHA_DE_TESTE).status_code == 302


# 6. De onde vem o IP


def pedido(**meta):
    return RequestFactory().get("/", **meta)


def test_producao_usa_x_real_ip_valido(settings):
    settings.LOGIN_IP_DO_CABECALHO = True

    assert ip_do_pedido(pedido(HTTP_X_REAL_IP=IP_B, REMOTE_ADDR=IP_A)) == IP_B


def test_producao_com_x_real_ip_invalido_usa_remote_addr(settings):
    settings.LOGIN_IP_DO_CABECALHO = True

    for invalido in ("nao-e-ip", "", "1.2.3.4, 5.6.7.8"):
        resultado = ip_do_pedido(pedido(HTTP_X_REAL_IP=invalido, REMOTE_ADDR=IP_A))
        assert resultado == IP_A, invalido


def test_fora_de_producao_x_real_ip_e_ignorado(settings):
    settings.LOGIN_IP_DO_CABECALHO = False

    assert ip_do_pedido(pedido(HTTP_X_REAL_IP=IP_B, REMOTE_ADDR=IP_A)) == IP_A


def test_sem_pedido_nao_ha_ip():
    assert ip_do_pedido(None) is None


def test_falha_guarda_o_ip_do_cabecalho_em_producao(client, settings):
    settings.LOGIN_IP_DO_CABECALHO = True

    client.post(
        reverse("login"),
        {"username": "pessoa1@exemplo.test", "password": SENHA_ERRADA},
        REMOTE_ADDR=IP_A,
        HTTP_X_REAL_IP=IP_B,
    )

    assert list(FalhaLogin.objects.values_list("ip", flat=True)) == [IP_B]


# 7. Liberar entrada pelo admin


def liberar(client, *usuarios):
    return client.post(
        reverse("admin:usuarios_usuario_changelist"),
        {
            "action": "liberar_entrada",
            "_selected_action": [usuario.pk for usuario in usuarios],
        },
    )


def test_admin_libera_a_entrada_da_pessoa(client, membro, admin_usuario):
    outra = Client()
    errar(outra, "pessoa1@exemplo.test", 9)
    errar(outra, "pessoa2@exemplo.test", 3)
    client.force_login(admin_usuario)

    resposta = liberar(client, membro)

    assert resposta.status_code == 302
    mensagens = [str(m) for m in get_messages(resposta.wsgi_request)]
    assert "Entrada liberada para 1 pessoa(s)." in mensagens
    assert set(FalhaLogin.objects.values_list("email", flat=True)) == {
        "pessoa2@exemplo.test"
    }
    assert FalhaLogin.objects.count() == 3
    assert entrar(outra, "pessoa1@exemplo.test", SENHA_DE_TESTE).status_code == 302


def test_liberar_apaga_falhas_de_todas_as_origens(client, membro, admin_usuario):
    membro.matricula = "1001"
    membro.save()
    errar(client, "1001", 2, ip=IP_A)
    errar(client, "pessoa1@exemplo.test", 3, ip=IP_B)
    FalhaLogin.objects.create(email="pessoa1@exemplo.test")  # sem IP
    client.force_login(admin_usuario)

    liberar(client, membro)

    assert FalhaLogin.objects.count() == 0


def test_membro_nao_usa_a_acao_liberar(client, membro, django_user_model):
    outra = django_user_model.objects.create_user(
        email="pessoa2@exemplo.test", password=SENHA_DE_TESTE
    )
    errar(client, "pessoa2@exemplo.test", 5)
    # O login do membro so apaga as falhas dele; as da pessoa 2 ficam.
    client.force_login(membro)

    resposta = liberar(client, outra)

    assert resposta.status_code == 302
    assert reverse("admin:login") in resposta.url
    assert FalhaLogin.objects.count() == 5


# 8. Mensagens iguais as de antes


def test_mensagens_iguais_para_conta_existente_e_inexistente(client, membro):
    for email in ("pessoa1@exemplo.test", "ninguem@exemplo.test"):
        for _ in range(5):
            conteudo = entrar(client, email, SENHA_ERRADA, ip=IP_B).content.decode()
            assert MENSAGEM_ERRO in conteudo, email
            assert MENSAGEM_BLOQUEIO not in conteudo, email

        conteudo = entrar(client, email, SENHA_ERRADA, ip=IP_B).content.decode()
        assert MENSAGEM_BLOQUEIO in conteudo, email
        assert MENSAGEM_ERRO not in conteudo, email


def test_painel_em_espera_da_conta_mostra_a_mensagem_de_espera(client, admin_usuario):
    # Igual ao /entrar/, para conta que existe e que nao existe.
    for email in ("admin@exemplo.test", "ninguem@exemplo.test"):
        for _ in range(5):
            conteudo = entrar_no_painel(client, email, SENHA_ERRADA).content.decode()
            assert MENSAGEM_ERRO in conteudo, email
            assert MENSAGEM_BLOQUEIO not in conteudo, email

        conteudo = entrar_no_painel(client, email, SENHA_DE_TESTE).content.decode()
        assert MENSAGEM_BLOQUEIO in conteudo, email
        assert MENSAGEM_ERRO not in conteudo, email

    assert not esta_logado(client)
    # As tentativas durante a espera nao foram registradas.
    assert FalhaLogin.objects.count() == 10


def test_painel_em_espera_do_ip_mostra_a_mensagem_de_espera(client, admin_usuario):
    errar_em_contas_diferentes(client, 20)

    conteudo = entrar_no_painel(
        client, "admin@exemplo.test", SENHA_DE_TESTE
    ).content.decode()

    assert MENSAGEM_BLOQUEIO in conteudo
    assert MENSAGEM_ERRO not in conteudo
    assert not esta_logado(client)
    assert FalhaLogin.objects.count() == 20
