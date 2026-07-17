from django.apps import AppConfig


class LeasesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'leases'

    def ready(self):
        # Connect unit-status sync signals.
        from . import signals  # noqa: F401
