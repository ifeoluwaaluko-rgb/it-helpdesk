from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

# existing imports in your file may already include more; this patch is only the setup view

def first_time_setup(request):
    if User.objects.exists():
        return redirect('login')

    if request.method == 'POST':
        full_name = (request.POST.get('full_name') or '').strip()
        email = (request.POST.get('email') or '').strip()
        username = (request.POST.get('username') or '').strip()
        password = request.POST.get('password') or ''
        confirm_password = request.POST.get('confirm_password') or ''

        if not full_name or not email or not username or not password or not confirm_password:
            messages.error(request, 'All fields are required.')
            return render(request, 'setup_first_admin.html')

        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'setup_first_admin.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'That username is already in use.')
            return render(request, 'setup_first_admin.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'That email address is already in use.')
            return render(request, 'setup_first_admin.html')

        first_name = full_name
        last_name = ''
        if ' ' in full_name:
            parts = full_name.split()
            first_name = parts[0]
            last_name = ' '.join(parts[1:])

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_staff=True,
            is_superuser=True,
        )

        auth_user = authenticate(request, username=username, password=password)
        if auth_user is not None:
            login(request, auth_user)

        messages.success(request, 'Administrator account created successfully.')
        return redirect('dashboard')

    return render(request, 'setup_first_admin.html')
