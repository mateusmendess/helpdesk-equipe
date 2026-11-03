"""Limite de tentativas de login, guardado no banco.

Por conta: a partir de LOGIN_MAX_TENTATIVAS erros na ultima hora, a pessoa espera
um tempo que dobra a cada erro novo (1, 2, 4, 8 min...), ate o teto, contado do
ultimo erro. Por IP: muitos erros do mesmo IP, em qualquer conta, bloqueiam o IP.
"""

import ipaddress
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Max
from django.utils import timezone

from .models import FalhaLogin, Usuario


def normalizar_email(email):
    return (email or "").strip().lower()


def chave_de_bloqueio(identificador):
    """E-mail do dono da matricula ou do e-mail digitado; senao, o texto digitado.

    Assim os erros pela matricula e pelo e-mail da mesma pessoa contam juntos.
    """
    try:
        return Usuario.objects.por_identificador(identificador).email
    except Usuario.DoesNotExist:
        return normalizar_email(identificador)


def _ip_valido(texto):
    try:
        return str(ipaddress.ip_address((texto or "").strip()))
    except ValueError:
        return None


def ip_do_pedido(request):
    """IP de quem tenta entrar; None sem request (a regra por IP nao se aplica).

    Em producao o Railway manda o IP real em X-Real-IP; fora dela o cabecalho
    e ignorado, porque qualquer um pode envia-lo.
    """
    if request is None:
        return None
    if settings.LOGIN_IP_DO_CABECALHO:
        ip = _ip_valido(request.META.get("HTTP_X_REAL_IP"))
        if ip:
            return ip
    return _ip_valido(request.META.get("REMOTE_ADDR"))


def _ha_minutos(minutos):
    return timezone.now() - timedelta(minutes=minutos)


def _espera(erros):
    """Espera depois de `erros` erros: 1 min x 2^(erros - max), ate o teto."""
    expoente = min(erros - settings.LOGIN_MAX_TENTATIVAS, 20)
    minutos = settings.LOGIN_ESPERA_INICIAL_MINUTOS * 2**expoente
    return timedelta(minutes=min(minutos, settings.LOGIN_ESPERA_MAXIMA_MINUTOS))


def _conta_em_espera(email):
    falhas = FalhaLogin.objects.filter(
        email=email, criada_em__gte=_ha_minutos(settings.LOGIN_JANELA_CONTA_MINUTOS)
    ).aggregate(erros=Count("id"), ultimo=Max("criada_em"))
    if falhas["erros"] < settings.LOGIN_MAX_TENTATIVAS:
        return False
    return timezone.now() < falhas["ultimo"] + _espera(falhas["erros"])


def _ip_bloqueado(ip):
    erros = FalhaLogin.objects.filter(
        ip=ip, criada_em__gte=_ha_minutos(settings.LOGIN_JANELA_IP_MINUTOS)
    ).count()
    return erros >= settings.LOGIN_MAX_POR_IP


def esta_bloqueado(identificador, ip=None):
    email = chave_de_bloqueio(identificador)
    if email and _conta_em_espera(email):
        return True
    return bool(ip) and _ip_bloqueado(ip)


def registrar_falha(identificador, ip=None):
    email = chave_de_bloqueio(identificador)
    if not email:
        return
    # Apaga de passagem o que ja saiu da maior janela, para a tabela nao crescer.
    maior_janela = max(
        settings.LOGIN_JANELA_CONTA_MINUTOS, settings.LOGIN_JANELA_IP_MINUTOS
    )
    FalhaLogin.objects.filter(criada_em__lt=_ha_minutos(maior_janela)).delete()
    FalhaLogin.objects.create(email=email, ip=ip)


def limpar_falhas(email):
    FalhaLogin.objects.filter(email=normalizar_email(email)).delete()
