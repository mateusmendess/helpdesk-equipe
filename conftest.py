import pytest

# Senha ficticia, usada so no banco temporario dos testes.
SENHA_DE_TESTE = "galao-teste-2026"


@pytest.fixture(autouse=True)
def _hasher_rapido(request, settings):
    """Hash de senha rapido so nos testes (producao continua com o padrao forte
    do Django, PBKDF2). O PBKDF2 custa ~0,5 s por senha e os testes de login
    pagam isso dezenas de vezes. O marcador `hash_real` desliga isto num teste.
    O Django limpa o cache de hashers sozinho quando PASSWORD_HASHERS muda."""
    if request.node.get_closest_marker("hash_real"):
        return
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def membro(django_user_model):
    return django_user_model.objects.create_user(
        email="pessoa1@exemplo.test",
        password=SENHA_DE_TESTE,
        first_name="Pessoa 1",
        ordem=1,
    )


@pytest.fixture
def admin_usuario(django_user_model):
    return django_user_model.objects.create_superuser(
        email="admin@exemplo.test",
        password=SENHA_DE_TESTE,
        first_name="Pessoa Admin",
    )
