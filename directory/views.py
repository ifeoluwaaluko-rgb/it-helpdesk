from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from .models import StaffMember, Department
from .forms import StaffImportForm, StaffMemberForm
from tickets.permissions import can_manage_directory, is_helpdesk_staff
import csv, io

@login_required
def staff_list(request):
    staff = StaffMember.objects.select_related('department').all()
    q = request.GET.get('q','').strip()
    dept = request.GET.get('dept')
    if q:
        staff = staff.filter(Q(first_name__icontains=q)|Q(last_name__icontains=q)|Q(email__icontains=q))
    if dept:
        staff = staff.filter(department_id=dept)
    departments = Department.objects.all()
    return render(request,'directory/staff_list.html',{
        'staff':staff,
        'departments':departments,
        'q':q,
        'selected_dept':dept,
        'can_manage_directory': can_manage_directory(request.user),
    })

@login_required
def staff_detail(request, pk):
    member = get_object_or_404(StaffMember, pk=pk)
    from tickets.models import Ticket
    tickets = Ticket.objects.filter(user_email=member.email).order_by('-created_at')[:10]
    return render(request,'directory/staff_detail.html',{
        'member':member,
        'tickets':tickets,
        'can_manage_directory': can_manage_directory(request.user),
    })

@login_required
def staff_create(request):
    if not can_manage_directory(request.user):
        messages.error(request, 'Only helpdesk staff can manage the staff directory.')
        return redirect('staff_list')
    form = StaffMemberForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            member = form.save()
            messages.success(request, f'{member.full_name} added to directory.')
            return redirect('staff_detail', pk=member.pk)
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return render(request,'directory/staff_form.html',{'form': form, 'departments': Department.objects.all(),'action':'Add'})

@login_required
def staff_edit(request, pk):
    if not can_manage_directory(request.user):
        messages.error(request, 'Only helpdesk staff can manage the staff directory.')
        return redirect('staff_list')
    member = get_object_or_404(StaffMember, pk=pk)
    form = StaffMemberForm(request.POST or None, instance=member)
    if request.method == 'POST':
        if form.is_valid():
            member = form.save()
            messages.success(request, 'Staff member updated.')
            return redirect('staff_detail', pk=member.pk)
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return render(request,'directory/staff_form.html',{'member':member,'form': form,'departments':Department.objects.all(),'action':'Edit'})

@login_required
def import_staff(request):
    if not can_manage_directory(request.user):
        messages.error(request, 'Only helpdesk staff can manage the staff directory.')
        return redirect('staff_list')
    form = StaffImportForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            f = form.cleaned_data['file']
            decoded = f.read().decode('utf-8', errors='replace')
            f.seek(0)
            reader = csv.DictReader(io.StringIO(decoded))
            created, skipped = 0, 0
            for row in reader:
                email = row.get('email','').strip().lower()
                if not email:
                    continue
                dept_name = row.get('department','').strip()
                dept = None
                if dept_name:
                    dept, _ = Department.objects.get_or_create(name=dept_name)
                _, was_created = StaffMember.objects.get_or_create(
                    email=email,
                    defaults={
                        'first_name': row.get('first_name','').strip(),
                        'last_name': row.get('last_name','').strip(),
                        'phone': row.get('phone','').strip(),
                        'job_title': row.get('job_title','').strip(),
                        'department': dept,
                    }
                )
                if was_created: created += 1
                else: skipped += 1
            messages.success(request, f'Import complete: {created} added, {skipped} skipped (already exist).')
            return redirect('staff_list')
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return render(request,'directory/import_staff.html', {'form': form})

@login_required
def download_template(request):
    if not can_manage_directory(request.user):
        messages.error(request, 'Only helpdesk staff can manage the staff directory.')
        return redirect('staff_list')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="staff_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['first_name','last_name','email','phone','department','job_title'])
    writer.writerow(['John','Doe','john.doe@company.com','+2348012345678','Finance','Finance Manager'])
    return response

@login_required
def staff_search_api(request):
    if not is_helpdesk_staff(request.user):
        return JsonResponse({'results': []}, status=403)
    q = request.GET.get('q','').strip()
    if len(q) < 2: return JsonResponse({'results':[]})
    members = StaffMember.objects.filter(
        Q(first_name__icontains=q)|Q(last_name__icontains=q)|Q(email__icontains=q), is_active=True
    )[:10]
    return JsonResponse({'results':[
        {'id':m.id,'name':m.full_name,'email':m.email,'department':m.department.name if m.department else ''}
        for m in members
    ]})
