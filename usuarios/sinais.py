from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .limite import esta_bloqueado, ip_do_pedido, limpar_falhas, registrar_falha


def _email_das_credenciais(credentials):
    # USERNAME_FIELD = "email": o e-mail chega como "username" ou "email".
    return credentials.get("username") or credentials.get("email")


@receiver(user_login_failed, dispatch_uid="usuarios_registrar_falha_de_login")
def registrar_falha_de_login(sender, credentials, request=None, **kwargs):
    email = _email_das_credenciais(credentials)
    ip = ip_do_pedido(request)
    # Tentativa durante a espera (da conta ou do IP) nao conta: nao a prolonga.
    if not email or esta_bloqueado(email, ip):
        return
    registrar_falha(email, ip)


@receiver(user_logged_in, dispatch_uid="usuarios_limpar_falhas_no_sucesso")
def limpar_falhas_no_sucesso(sender, request, user, **kwargs):
    limpar_falhas(user.email)
