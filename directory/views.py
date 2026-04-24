from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from .models import StaffMember, Department
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
    return render(request,'directory/staff_list.html',{'staff':staff,'departments':departments,'q':q,'selected_dept':dept})

@login_required
def staff_detail(request, pk):
    member = get_object_or_404(StaffMember, pk=pk)
    from tickets.models import Ticket
    tickets = Ticket.objects.filter(user_email=member.email).order_by('-created_at')[:10]
    return render(request,'directory/staff_detail.html',{'member':member,'tickets':tickets})

@login_required
def staff_create(request):
    departments = Department.objects.all()
    if request.method == 'POST':
        first = request.POST.get('first_name','').strip()
        last = request.POST.get('last_name','').strip()
        email = request.POST.get('email','').strip()
        dept_id = request.POST.get('department')
        if first and last and email:
            member = StaffMember.objects.create(
                first_name=first, last_name=last, email=email,
                phone=request.POST.get('phone',''),
                job_title=request.POST.get('job_title',''),
                department_id=dept_id if dept_id else None
            )
            messages.success(request, f'{member.full_name} added to directory.')
            return redirect('staff_detail', pk=member.pk)
    return render(request,'directory/staff_form.html',{'departments':departments,'action':'Add'})

@login_required
def staff_edit(request, pk):
    member = get_object_or_404(StaffMember, pk=pk)
    departments = Department.objects.all()
    if request.method == 'POST':
        member.first_name = request.POST.get('first_name', member.first_name)
        member.last_name = request.POST.get('last_name', member.last_name)
        member.email = request.POST.get('email', member.email)
        member.phone = request.POST.get('phone', member.phone)
        member.job_title = request.POST.get('job_title', member.job_title)
        dept_id = request.POST.get('department')
        member.department_id = dept_id if dept_id else None
        member.is_active = request.POST.get('is_active') == 'on'
        member.save()
        messages.success(request, 'Staff member updated.')
        return redirect('staff_detail', pk=member.pk)
    return render(request,'directory/staff_form.html',{'member':member,'departments':departments,'action':'Edit'})

@login_required
def import_staff(request):
    if request.method == 'POST' and request.FILES.get('file'):
        f = request.FILES['file']
        decoded = f.read().decode('utf-8', errors='replace')
        reader = csv.DictReader(io.StringIO(decoded))
        created, skipped = 0, 0
        for row in reader:
            email = row.get('email','').strip()
            if not email: continue
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
    return render(request,'directory/import_staff.html')

@login_required
def download_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="staff_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['first_name','last_name','email','phone','department','job_title'])
    writer.writerow(['John','Doe','john.doe@company.com','+2348012345678','Finance','Finance Manager'])
    return response

def staff_search_api(request):
    q = request.GET.get('q','').strip()
    if len(q) < 2: return JsonResponse({'results':[]})
    members = StaffMember.objects.filter(
        Q(first_name__icontains=q)|Q(last_name__icontains=q)|Q(email__icontains=q), is_active=True
    )[:10]
    return JsonResponse({'results':[
        {'id':m.id,'name':m.full_name,'email':m.email,'department':m.department.name if m.department else ''}
        for m in members
    ]})
