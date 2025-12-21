from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"
# accounts/apps.py
def ready(self):
    import accounts.signals
