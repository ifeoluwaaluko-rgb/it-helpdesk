from .models import IntegrationConfig

def get_configs():
    configs = {}
    for key in ["email_imap", "email_smtp"]:
        obj, _ = IntegrationConfig.objects.get_or_create(
            integration=key,
            defaults={"use_ssl": True}
        )
        configs[key] = obj
    return configs