from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from .models import Asset, AssetCategory, AssetHistory, HardwareIncident
from .forms import AssetAssignmentForm, AssetCreateForm, AssetImportForm, AssetStatusForm, HardwareIncidentForm
from directory.models import StaffMember
from tickets.permissions import can_manage_assets
import csv, io

@login_required
def asset_list(request):
    assets = Asset.objects.select_related('category','assigned_to').all()
    q = request.GET.get('q','').strip()
    cat = request.GET.get('category')
    status = request.GET.get('status')
    if q:
        assets = assets.filter(Q(name__icontains=q)|Q(asset_id__icontains=q)|Q(serial_number__icontains=q))
    if cat: assets = assets.filter(category_id=cat)
    if status: assets = assets.filter(status=status)
    categories = AssetCategory.objects.all()
    all_assets_qs = Asset.objects.all()
    total_all = all_assets_qs.count()
    total_filtered = assets.count()
    status_summary = [(val, label, all_assets_qs.filter(status=val).count()) for val, label in Asset.STATUS_CHOICES]
    return render(request,'assets/asset_list.html',{
        'assets':assets,'categories':categories,
        'total': total_all, 'total_filtered': total_filtered,
        'status_choices':Asset.STATUS_CHOICES,'q':q,'sel_cat':cat,'sel_status':status,
        'status_summary': status_summary,
        'is_filtered': bool(q or cat or status),
        'can_manage_assets': can_manage_assets(request.user),
    })

@login_required
def asset_detail(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    history = asset.history.all()[:20]
    incidents = asset.incidents.all()[:10]
    staff = StaffMember.objects.filter(is_active=True).order_by('first_name')
    assignment_form = AssetAssignmentForm(initial={'staff_id': asset.assigned_to_id or ''})
    status_form = AssetStatusForm(initial={'status': asset.status})
    if request.method == 'POST':
        if not can_manage_assets(request.user):
            messages.error(request,'Only helpdesk staff can update assets.')
            return redirect('asset_detail', pk=pk)
        action = request.POST.get('action')
        if action == 'assign':
            assignment_form = AssetAssignmentForm(request.POST)
            if assignment_form.is_valid():
                sid = assignment_form.cleaned_data.get('staff_id')
                try:
                    old = asset.assigned_to.full_name if asset.assigned_to else 'Unassigned'
                    asset.assigned_to = StaffMember.objects.get(pk=sid) if sid else None
                    new = asset.assigned_to.full_name if asset.assigned_to else 'Unassigned'
                    asset.save()
                    AssetHistory.objects.create(asset=asset,changed_by=request.user,change_type='Reassigned',old_value=old,new_value=new)
                    messages.success(request,'Assignment updated.')
                except StaffMember.DoesNotExist:
                    messages.error(request, 'Invalid staff selection.')
            else:
                for errors in assignment_form.errors.values():
                    for error in errors:
                        messages.error(request, error)
        elif action == 'status':
            status_form = AssetStatusForm(request.POST)
            if status_form.is_valid():
                old = asset.get_status_display()
                asset.status = status_form.cleaned_data['status']
                asset.save()
                AssetHistory.objects.create(asset=asset,changed_by=request.user,change_type='Status Change',old_value=old,new_value=asset.get_status_display())
                messages.success(request,'Status updated.')
            else:
                for errors in status_form.errors.values():
                    for error in errors:
                        messages.error(request, error)
        return redirect('asset_detail', pk=pk)
    return render(request,'assets/asset_detail.html',{
        'asset':asset,'history':history,'incidents':incidents,'staff':staff,
        'status_choices':Asset.STATUS_CHOICES,
        'can_manage_assets': can_manage_assets(request.user),
        'assignment_form': assignment_form,
        'status_form': status_form,
    })

@login_required
def asset_create(request):
    if not can_manage_assets(request.user):
        messages.error(request,'Only helpdesk staff can register assets.')
        return redirect('asset_list')
    categories = AssetCategory.objects.all()
    staff = StaffMember.objects.filter(is_active=True)
    form = AssetCreateForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            asset = form.save(commit=False)
            asset.created_by = request.user
            asset.save()
            AssetHistory.objects.create(asset=asset,changed_by=request.user,change_type='Registered',new_value='Asset created')
            messages.success(request,f'Asset {asset.asset_id} registered.')
            return redirect('asset_detail', pk=asset.pk)
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return render(request,'assets/asset_form.html',{
        'form': form, 'categories':categories,'staff':staff,'status_choices':Asset.STATUS_CHOICES
    })

@login_required
def log_incident(request, asset_pk):
    if not can_manage_assets(request.user):
        messages.error(request,'Only helpdesk staff can log hardware incidents.')
        return redirect('asset_detail', pk=asset_pk)
    asset = get_object_or_404(Asset, pk=asset_pk)
    from tickets.models import Ticket
    tickets = Ticket.objects.filter(category='hardware').order_by('-created_at')[:30]
    valid_ticket_ids = list(tickets.values_list('id', flat=True))
    form = HardwareIncidentForm(request.POST or None, valid_ticket_ids=valid_ticket_ids, initial={'severity': 'medium'})
    if request.method == 'POST':
        if form.is_valid():
            HardwareIncident.objects.create(
                asset=asset,
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                severity=form.cleaned_data['severity'],
                reported_by=request.user,
                ticket_id=form.cleaned_data.get('ticket_id') or None,
            )
            AssetHistory.objects.create(asset=asset,changed_by=request.user,change_type='Incident Logged',new_value=form.cleaned_data['title'])
            messages.success(request,'Incident logged.')
            return redirect('asset_detail', pk=asset_pk)
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return render(request,'assets/log_incident.html',{
        'asset':asset,'tickets':tickets,'severity_choices':HardwareIncident.SEVERITY_CHOICES,'form': form
    })

@login_required
def bulk_import(request):
    if not can_manage_assets(request.user):
        messages.error(request,'Only helpdesk staff can import assets.')
        return redirect('asset_list')
    form = AssetImportForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if form.is_valid():
            f = form.cleaned_data['file']
            decoded = f.read().decode('utf-8', errors='replace')
            f.seek(0)
            reader = csv.DictReader(io.StringIO(decoded))
            created, skipped = 0, 0
            for row in reader:
                aid = row.get('asset_id','').strip().upper()
                if not aid:
                    continue
                cat_name = row.get('category','').strip()
                cat = None
                if cat_name:
                    cat,_ = AssetCategory.objects.get_or_create(name=cat_name)
                _, was_created = Asset.objects.get_or_create(asset_id=aid, defaults={
                    'name':row.get('name','').strip(),'category':cat,
                    'brand':row.get('brand',''),'model':row.get('model',''),
                    'serial_number':row.get('serial_number',''),
                    'location':row.get('location',''),'status':row.get('status','active'),
                    'created_by':request.user,
                })
                if was_created: created += 1
                else: skipped += 1
            messages.success(request,f'Import complete: {created} added, {skipped} skipped.')
            return redirect('asset_list')
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    return render(request,'assets/bulk_import.html', {'form': form})

@login_required
def asset_template(request):
    if not can_manage_assets(request.user):
        messages.error(request,'Only helpdesk staff can download asset templates.')
        return redirect('asset_list')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="asset_import_template.csv"'
    w = csv.writer(response)
    w.writerow(['asset_id','name','category','brand','model','serial_number','location','status'])
    w.writerow(['LAPTOP-001','Dell XPS 15','Computers','Dell','XPS 15','SN123456','Floor 2','active'])
    return response
