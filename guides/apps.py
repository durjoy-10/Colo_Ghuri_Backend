from django.apps import AppConfig

class GuidesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'guides'
    
    def ready(self):
        # Import signals only when app is ready
        import guides.signals