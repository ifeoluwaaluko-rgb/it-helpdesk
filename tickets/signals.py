from django.db.models.signals import post_save, post_migrate
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import Profile


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Create a Profile whenever a new User is created."""
    if created:
        Profile.objects.get_or_create(user=instance)


@receiver(post_migrate)
def ensure_profiles_exist(sender, **kwargs):
    """
    After every migration, make sure every existing User has a Profile.
    Runs once on deploy — safe to call repeatedly (get_or_create is idempotent).
    """
    if sender.name == 'tickets':
        try:
            for user in User.objects.all():
                Profile.objects.get_or_create(user=user)
        except RuntimeError:
            pass  # DB tables may not exist yet on first migrate
