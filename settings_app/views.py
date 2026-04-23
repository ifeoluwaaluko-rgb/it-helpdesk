from django.shortcuts import render
from .models import IntegrationConfig

def _get_configs():
    configs = {}
    for key in ["imap", "smtp"]:
        obj, _ = IntegrationConfig.objects.get_or_create(
            integration=key,
            defaults={"use_ssl": True}
        )
        configs[key] = obj
    return configs

def settings_home(request):
    configs = _get_configs()
    return render(request, "settings/home.html", {"configs": configs})