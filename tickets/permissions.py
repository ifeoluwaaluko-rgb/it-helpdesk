from django.contrib.auth.models import AnonymousUser


HELPDESK_ADMIN_ROLES = {"manager", "consultant", "senior", "superadmin"}
SETTINGS_ADMIN_ROLES = {"manager", "superadmin"}


def get_role(user):
    if not user or isinstance(user, AnonymousUser):
        return ""
    try:
        return user.profile.role
    except Exception:
        return "associate"


def is_helpdesk_staff(user):
    return bool(getattr(user, "is_authenticated", False) and getattr(user, "is_staff", False))


def can_assign(user):
    return get_role(user) in HELPDESK_ADMIN_ROLES


def can_delete_edit(user):
    return get_role(user) in HELPDESK_ADMIN_ROLES


def can_manage_knowledge(user):
    return is_helpdesk_staff(user)


def can_manage_assets(user):
    return is_helpdesk_staff(user)


def can_manage_directory(user):
    return is_helpdesk_staff(user)


def can_manage_settings(user):
    return get_role(user) in SETTINGS_ADMIN_ROLES
