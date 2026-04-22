def user_role(request):
    """Inject the current user's role into every template context."""
    role = 'associate'
    if request.user.is_authenticated:
        try:
            role = request.user.profile.role
        except Exception:
            role = 'associate'
    return {'role': role, 'role_display': role.title()}
