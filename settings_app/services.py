from .models import IntegrationConfig


def get_configs():
    configs = {}
    for key in ["email_imap", "email_smtp"]:
        obj, _ = IntegrationConfig.objects.get_or_create(
            integration=key,
            defaults={"use_ssl": True},
        )
        configs[key] = obj
    return configs


def get_smtp_runtime_config():
    config, _ = IntegrationConfig.objects.get_or_create(
        integration="email_smtp",
        defaults={"use_ssl": True},
    )
    return {
        "host": getattr(config, "host", ""),
        "port": getattr(config, "port", None),
        "username": getattr(config, "username", ""),
        "password": getattr(config, "password", ""),
        "use_tls": getattr(config, "use_tls", False),
        "use_ssl": getattr(config, "use_ssl", True),
    }
