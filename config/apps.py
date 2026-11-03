from django.contrib.admin.apps import AdminConfig


class PainelAdminConfig(AdminConfig):
    # Faz o admin.site do projeto ser o PainelAdminSite (config/admin.py).
    default_site = "config.admin.PainelAdminSite"
