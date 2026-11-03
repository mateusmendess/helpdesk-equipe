from django.contrib import admin

# Ordem dos blocos (apps) e dos itens (pelo object_name do modelo) no /admin/.
# O que nao estiver aqui vai depois: apps em ordem alfabetica, e modelos no
# fim do bloco, na ordem em que o Django os entregou (alfabetica).
ORDEM_DOS_APPS = ("fila", "escala", "usuarios")
ORDEM_DOS_MODELOS = {
    "fila": ("Troca", "Ausencia", "Rodada"),
    "escala": (
        "TrocaSabado",
        "SabadoSemEscala",
        "SabadoDuasPessoas",
        "SabadoFechado",
        "ConfiguracaoEscala",
    ),
    "usuarios": ("Usuario",),
}
# Blocos que ficam fora da tela inicial e do menu lateral. Os modelos seguem
# registrados: as URLs (ex.: /admin/auth/group/) continuam abrindo.
APPS_ESCONDIDOS = ("auth",)


def _posicao(valor, ordem):
    """Posicao na lista de ordem; o que nao esta nela vai para o fim."""
    return ordem.index(valor) if valor in ordem else len(ordem)


class PainelAdminSite(admin.AdminSite):
    """Admin do projeto: so muda a lista da tela inicial e do menu lateral
    (quais blocos aparecem e em que ordem)."""

    def get_app_list(self, request, app_label=None):
        apps = super().get_app_list(request, app_label)
        if app_label is None:
            apps = [a for a in apps if a["app_label"] not in APPS_ESCONDIDOS]
        # sorted() e estavel: empates mantem a ordem alfabetica do Django.
        apps = sorted(
            apps, key=lambda a: (_posicao(a["app_label"], ORDEM_DOS_APPS), a["name"])
        )
        for app in apps:
            ordem = ORDEM_DOS_MODELOS.get(app["app_label"], ())
            app["models"] = sorted(
                app["models"], key=lambda m: _posicao(m["object_name"], ordem)
            )
        return apps
