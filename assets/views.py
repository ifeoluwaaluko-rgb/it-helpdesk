from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from .models import Asset, AssetCategory, AssetHistory, HardwareIncident
from directory.models import StaffMember
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
    total = assets.count()
    return render(request,'assets/asset_list.html',{
        'assets':assets,'categories':categories,'total':total,
        'status_choices':Asset.STATUS_CHOICES,'q':q,'sel_cat':cat,'sel_status':status,
    })

@login_required
def asset_detail(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    history = asset.history.all()[:20]
    incidents = asset.incidents.all()[:10]
    staff = StaffMember.objects.filter(is_active=True).order_by('first_name')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'assign':
            sid = request.POST.get('staff_id')
            old = asset.assigned_to.full_name if asset.assigned_to else 'Unassigned'
            asset.assigned_to = StaffMember.objects.get(pk=sid) if sid else None
            new = asset.assigned_to.full_name if asset.assigned_to else 'Unassigned'
            asset.save()
            AssetHistory.objects.create(asset=asset,changed_by=request.user,change_type='Reassigned',old_value=old,new_value=new)
            messages.success(request,'Assignment updated.')
        elif action == 'status':
            old = asset.get_status_display()
            asset.status = request.POST.get('status', asset.status)
            asset.save()
            AssetHistory.objects.create(asset=asset,changed_by=request.user,change_type='Status Change',old_value=old,new_value=asset.get_status_display())
            messages.success(request,'Status updated.')
        return redirect('asset_detail', pk=pk)
    return render(request,'assets/asset_detail.html',{
        'asset':asset,'history':history,'incidents':incidents,'staff':staff,
        'status_choices':Asset.STATUS_CHOICES,
    })

@login_required
def asset_create(request):
    categories = AssetCategory.objects.all()
    staff = StaffMember.objects.filter(is_active=True)
    if request.method == 'POST':
        cat_id = request.POST.get('category')
        sid = request.POST.get('assigned_to')
        asset = Asset.objects.create(
            asset_id=request.POST.get('asset_id','').strip(),
            name=request.POST.get('name','').strip(),
            category_id=cat_id or None,
            brand=request.POST.get('brand',''),
            model=request.POST.get('model',''),
            serial_number=request.POST.get('serial_number',''),
            location=request.POST.get('location',''),
            notes=request.POST.get('notes',''),
            status=request.POST.get('status','active'),
            assigned_to=StaffMember.objects.get(pk=sid) if sid else None,
            created_by=request.user,
        )
        AssetHistory.objects.create(asset=asset,changed_by=request.user,change_type='Registered',new_value='Asset created')
        messages.success(request,f'Asset {asset.asset_id} registered.')
        return redirect('asset_detail', pk=asset.pk)
    return render(request,'assets/asset_form.html',{
        'categories':categories,'staff':staff,'status_choices':Asset.STATUS_CHOICES
    })

@login_required
def log_incident(request, asset_pk):
    asset = get_object_or_404(Asset, pk=asset_pk)
    from tickets.models import Ticket
    tickets = Ticket.objects.filter(category='hardware').order_by('-created_at')[:30]
    if request.method == 'POST':
        HardwareIncident.objects.create(
            asset=asset,
            title=request.POST.get('title','').strip(),
            description=request.POST.get('description','').strip(),
            severity=request.POST.get('severity','medium'),
            reported_by=request.user,
            ticket_id=request.POST.get('ticket_id') or None,
        )
        AssetHistory.objects.create(asset=asset,changed_by=request.user,change_type='Incident Logged',new_value=request.POST.get('title',''))
        messages.success(request,'Incident logged.')
        return redirect('asset_detail', pk=asset_pk)
    return render(request,'assets/log_incident.html',{
        'asset':asset,'tickets':tickets,'severity_choices':HardwareIncident.SEVERITY_CHOICES
    })

@login_required
def bulk_import(request):
    if request.method == 'POST' and request.FILES.get('file'):
        f = request.FILES['file']
        decoded = f.read().decode('utf-8', errors='replace')
        reader = csv.DictReader(io.StringIO(decoded))
        created, skipped = 0, 0
        for row in reader:
            aid = row.get('asset_id','').strip()
            if not aid: continue
            cat_name = row.get('category','').strip()
            cat = None
            if cat_name: cat,_ = AssetCategory.objects.get_or_create(name=cat_name)
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
    return render(request,'assets/bulk_import.html')

@login_required
def asset_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="asset_import_template.csv"'
    w = csv.writer(response)
    w.writerow(['asset_id','name','category','brand','model','serial_number','location','status'])
    w.writerow(['LAPTOP-001','Dell XPS 15','Computers','Dell','XPS 15','SN123456','Floor 2','active'])
    return response
