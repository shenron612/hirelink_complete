import base64, json
from datetime import datetime

import requests
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

from skillsync.forms import RegisterForm
from skillsync.models import HireRequest, JobRequest, Message, Notification, User


# ── helpers ──────────────────────────────────────────────────────────────────

def _notif(recipient, sender, notif_type, title, body='', link='', related_id=None):
    Notification.objects.create(
        recipient=recipient, sender=sender,
        notif_type=notif_type, title=title,
        body=body, link=link, related_id=related_id,
    )


# ── CORE ─────────────────────────────────────────────────────────────────────

def dashboard(request):
    profiles = User.objects.all().order_by('-date_joined')
    return render(request, 'dashboard.html', {'profiles': profiles})


def register(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'errors': {'detail': ['Invalid request.']}}, status=400)
        form = RegisterForm(data)
        if form.is_valid():
            user = form.save()
            # set default status
            user.status = 'available' if user.role == 'worker' else 'hiring'
            user.save()
            login(request, user)
            return JsonResponse({'success': True, 'message': f'Welcome, {user.full_name}!'})
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    return redirect('dashboard')


def user_login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'errors': {'detail': ['Invalid request.']}}, status=400)
        user = authenticate(request, username=data.get('email',''), password=data.get('password',''))
        if user:
            login(request, user)
            return JsonResponse({'success': True, 'message': f'Welcome back, {user.full_name}!', 'role': user.role})
        return JsonResponse({'success': False, 'errors': {'detail': ['Invalid email or password.']}}, status=400)
    return redirect('dashboard')


def user_logout(request):
    logout(request)
    return redirect('dashboard')


@login_required
def delete_account(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user = authenticate(request, username=request.user.email, password=data.get('password',''))
            if user:
                logout(request)
                user.delete()
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'Incorrect password.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return redirect('dashboard')


# ── PROFILE ──────────────────────────────────────────────────────────────────

def user_profile(request, user_id):
    profile = get_object_or_404(User, id=user_id)
    hire_status = None
    job_status = None
    if request.user.is_authenticated:
        if request.user.role == 'employer' and profile.role == 'worker':
            hr = HireRequest.objects.filter(employer=request.user, worker=profile).order_by('-created_at').first()
            hire_status = hr.status if hr else None
        if request.user.role == 'worker' and profile.role == 'employer':
            jr = JobRequest.objects.filter(worker=request.user, employer=profile).order_by('-created_at').first()
            job_status = jr.status if jr else None
    return render(request, 'profile_view.html', {
        'profile': profile,
        'hire_status': hire_status,
        'job_status': job_status,
    })


@login_required
def update_profile(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({'success': False, 'error': 'Invalid data'})
        u = request.user
        u.full_name    = data.get('full_name', u.full_name)
        u.skills       = data.get('skills', u.skills)
        u.hourly_wage  = data.get('hourly_wage') or u.hourly_wage
        u.hours_per_day = data.get('hours_per_day') or u.hours_per_day
        u.working_days = data.get('working_days', u.working_days)
        u.bio          = data.get('bio', u.bio)
        u.job_ad       = data.get('job_ad', u.job_ad)
        u.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})


# ── SEARCH ───────────────────────────────────────────────────────────────────

def search_workers(request):
    query = request.GET.get('q', '').strip()
    users = []
    if query:
        users = User.objects.filter(
            Q(full_name__icontains=query) |
            Q(skills__icontains=query) |
            Q(role__icontains=query)
        )
    viewer_role = request.user.role if request.user.is_authenticated else None
    return JsonResponse({'workers': [
        {
            'id':            u.id,
            'full_name':     u.full_name,
            'role':          u.role,
            'skills':        u.skills,
            'hourly_wage':   str(u.hourly_wage) if u.hourly_wage else 'N/A',
            'hours_per_day': u.hours_per_day or 'N/A',
            'working_days':  u.working_days,
            'status':        u.status,
            'viewer_role':   viewer_role,
            'is_self':       u.id == request.user.id if request.user.is_authenticated else False,
        }
        for u in users
    ]})


# ── HIRE FLOW ─────────────────────────────────────────────────────────────────

@login_required
def send_hire_request(request):
    if request.method == 'POST':
        try:
            data      = json.loads(request.body)
            worker    = get_object_or_404(User, id=data.get('worker_id'), role='worker')
            if request.user.role != 'employer':
                return JsonResponse({'success': False, 'error': 'Only employers can send hire requests.'})
            # check no pending
            existing = HireRequest.objects.filter(employer=request.user, worker=worker, status='pending').first()
            if existing:
                return JsonResponse({'success': False, 'error': 'You already have a pending request to this worker.'})
            hr = HireRequest.objects.create(employer=request.user, worker=worker, message=data.get('message',''))
            _notif(
                recipient=worker, sender=request.user,
                notif_type='hire_request',
                title=f'{request.user.full_name} wants to hire you!',
                body=data.get('message',''),
                link=f'/notifications/',
                related_id=hr.id,
            )
            return JsonResponse({'success': True, 'message': 'Hire request sent! Waiting for worker to respond.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return redirect('dashboard')


@login_required
def respond_hire_request(request, req_id):
    if request.method == 'POST':
        try:
            data   = json.loads(request.body)
            action = data.get('action')  # 'accept' or 'reject'
            hr     = get_object_or_404(HireRequest, id=req_id, worker=request.user)
            if action == 'accept':
                hr.status = 'accepted'
                hr.save()
                _notif(
                    recipient=hr.employer, sender=request.user,
                    notif_type='hire_accepted',
                    title=f'{request.user.full_name} accepted your hire request!',
                    body='You can now proceed to make payment.',
                    link=f'/make-payment/?worker_id={request.user.id}&hire_id={hr.id}',
                    related_id=hr.id,
                )
                return JsonResponse({'success': True, 'message': 'You accepted the hire request.'})
            elif action == 'reject':
                hr.status = 'rejected'
                hr.save()
                _notif(
                    recipient=hr.employer, sender=request.user,
                    notif_type='hire_rejected',
                    title=f'{request.user.full_name} declined your hire request.',
                    body='You may try contacting them or find another worker.',
                    link='/notifications/',
                    related_id=hr.id,
                )
                return JsonResponse({'success': True, 'message': 'You declined the hire request.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return redirect('notifications')


# ── JOB REQUEST (worker → employer) ──────────────────────────────────────────

@login_required
def send_job_request(request):
    if request.method == 'POST':
        try:
            data     = json.loads(request.body)
            employer = get_object_or_404(User, id=data.get('employer_id'), role='employer')
            if request.user.role != 'worker':
                return JsonResponse({'success': False, 'error': 'Only workers can request jobs.'})
            existing = JobRequest.objects.filter(worker=request.user, employer=employer, status='pending').first()
            if existing:
                return JsonResponse({'success': False, 'error': 'You already have a pending request to this employer.'})
            jr = JobRequest.objects.create(worker=request.user, employer=employer, message=data.get('message',''))
            _notif(
                recipient=employer, sender=request.user,
                notif_type='job_request',
                title=f'{request.user.full_name} is requesting a job from you!',
                body=data.get('message',''),
                link='/notifications/',
                related_id=jr.id,
            )
            return JsonResponse({'success': True, 'message': 'Job request sent! Waiting for employer to respond.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return redirect('dashboard')


@login_required
def respond_job_request(request, req_id):
    if request.method == 'POST':
        try:
            data   = json.loads(request.body)
            action = data.get('action')
            jr     = get_object_or_404(JobRequest, id=req_id, employer=request.user)
            if action == 'accept':
                jr.status = 'accepted'
                jr.save()
                _notif(
                    recipient=jr.worker, sender=request.user,
                    notif_type='job_accepted',
                    title=f'{request.user.full_name} accepted your job request!',
                    body='Great news! You have been offered a job.',
                    link='/notifications/',
                    related_id=jr.id,
                )
                return JsonResponse({'success': True})
            elif action == 'reject':
                jr.status = 'rejected'
                jr.save()
                _notif(
                    recipient=jr.worker, sender=request.user,
                    notif_type='job_rejected',
                    title=f'{request.user.full_name} declined your job request.',
                    body='Keep applying — other employers may be interested.',
                    link='/notifications/',
                    related_id=jr.id,
                )
                return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return redirect('notifications')


# ── NOTIFICATIONS ─────────────────────────────────────────────────────────────

@login_required
def notifications_page(request):
    notifs = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    # attach related request objects
    hire_requests_pending = HireRequest.objects.filter(worker=request.user, status='pending')
    job_requests_pending  = JobRequest.objects.filter(employer=request.user, status='pending')
    return render(request, 'notifications.html', {
        'notifications':        notifs,
        'hire_requests_pending': hire_requests_pending,
        'job_requests_pending':  job_requests_pending,
    })


@login_required
def unread_notifications(request):
    count  = request.user.unread_notifications()
    recent = list(Notification.objects.filter(recipient=request.user, is_read=False).values(
        'id','title','body','notif_type','created_at','link','related_id'
    )[:5])
    for n in recent:
        n['created_at'] = n['created_at'].strftime('%b %d, %H:%M')
    return JsonResponse({'count': count, 'notifications': recent})


@login_required
def mark_notification_read(request, notif_id):
    Notification.objects.filter(id=notif_id, recipient=request.user).update(is_read=True)
    return JsonResponse({'success': True})


@login_required
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


# ── MESSAGING ─────────────────────────────────────────────────────────────────

@login_required
def messages_page(request):
    # get all unique conversations
    sent     = Message.objects.filter(sender=request.user).values_list('recipient_id', flat=True)
    received = Message.objects.filter(recipient=request.user).values_list('sender_id', flat=True)
    user_ids = set(list(sent) + list(received))
    contacts = User.objects.filter(id__in=user_ids).exclude(id=request.user.id)
    return render(request, 'messages.html', {'contacts': contacts})


@login_required
def conversation(request, user_id):
    other = get_object_or_404(User, id=user_id)
    msgs  = Message.objects.filter(
        Q(sender=request.user, recipient=other) |
        Q(sender=other, recipient=request.user)
    ).order_by('created_at')
    # mark received as read
    msgs.filter(recipient=request.user, is_read=False).update(is_read=True)
    contacts_sent     = Message.objects.filter(sender=request.user).values_list('recipient_id', flat=True)
    contacts_received = Message.objects.filter(recipient=request.user).values_list('sender_id', flat=True)
    user_ids = set(list(contacts_sent) + list(contacts_received))
    if other.id not in user_ids:
        user_ids.add(other.id)
    contacts = User.objects.filter(id__in=user_ids).exclude(id=request.user.id)
    return render(request, 'messages.html', {'contacts': contacts, 'active_user': other, 'messages': msgs})


@login_required
def send_message(request):
    if request.method == 'POST':
        try:
            data      = json.loads(request.body)
            recipient = get_object_or_404(User, id=data.get('recipient_id'))
            body      = data.get('body','').strip()
            if not body:
                return JsonResponse({'success': False, 'error': 'Message cannot be empty.'})
            msg = Message.objects.create(sender=request.user, recipient=recipient, body=body)
            _notif(
                recipient=recipient, sender=request.user,
                notif_type='message',
                title=f'New message from {request.user.full_name}',
                body=body[:80],
                link=f'/messages/{request.user.id}/',
            )
            return JsonResponse({'success': True, 'message': {'id': msg.id, 'body': msg.body, 'time': msg.created_at.strftime('%H:%M')}})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return redirect('messages')


@login_required
def fetch_messages(request, user_id):
    other = get_object_or_404(User, id=user_id)
    msgs  = Message.objects.filter(
        Q(sender=request.user, recipient=other) |
        Q(sender=other, recipient=request.user)
    ).order_by('created_at')
    msgs.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'messages': [
        {'id': m.id, 'body': m.body, 'time': m.created_at.strftime('%H:%M'),
         'is_mine': m.sender_id == request.user.id}
        for m in msgs
    ]})


# ── STATUS TOGGLE ─────────────────────────────────────────────────────────────

@login_required
def toggle_status(request):
    if request.method == 'POST':
        try:
            data   = json.loads(request.body)
            status = data.get('status')
            valid  = ['available','unavailable'] if request.user.role == 'worker' else ['hiring','not_hiring']
            if status not in valid:
                return JsonResponse({'success': False, 'error': 'Invalid status.'})
            request.user.status = status
            request.user.save()
            return JsonResponse({'success': True, 'status': status})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False})


# ── PAYMENT ───────────────────────────────────────────────────────────────────

def get_mpesa_token():
    credentials = base64.b64encode(f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}".encode()).decode()
    r = requests.get('https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials',
                     headers={'Authorization': f'Basic {credentials}'})
    return r.json().get('access_token')


def get_password_and_timestamp():
    ts  = datetime.now().strftime('%Y%m%d%H%M%S')
    raw = f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{ts}"
    return base64.b64encode(raw.encode()).decode(), ts


@login_required
def make_payment(request):
    worker_id = request.GET.get('worker_id')
    hire_id   = request.GET.get('hire_id')
    worker    = None
    if worker_id:
        try:
            worker = User.objects.get(id=worker_id)
        except User.DoesNotExist:
            pass
    return render(request, 'make_payment.html', {'worker': worker, 'hire_id': hire_id})


@login_required
def stk_push(request):
    if request.method != 'POST':
        return JsonResponse({'success': False}, status=405)
    try:
        data     = json.loads(request.body)
        phone    = data.get('phone','').strip()
        amount   = data.get('amount','').strip()
        hire_id  = data.get('hire_id','')
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('+'):
            phone = phone[1:]
        token, (password, ts) = get_mpesa_token(), get_password_and_timestamp()
        payload = {
            'BusinessShortCode': settings.MPESA_SHORTCODE, 'Password': password,
            'Timestamp': ts, 'TransactionType': 'CustomerPayBillOnline',
            'Amount': int(amount), 'PartyA': phone, 'PartyB': settings.MPESA_SHORTCODE,
            'PhoneNumber': phone, 'CallBackURL': settings.MPESA_CALLBACK_URL,
            'AccountReference': f'HireLink-{hire_id or "payment"}',
            'TransactionDesc': 'HireLink Worker Payment',
        }
        r = requests.post('https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
                          json=payload, headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
        result = r.json()
        if result.get('ResponseCode') == '0':
            # mark hire as paid
            if hire_id:
                HireRequest.objects.filter(id=hire_id).update(status='paid')
            return JsonResponse({'success': True, 'message': 'STK Push sent! Check your phone.'})
        return JsonResponse({'success': False, 'error': result.get('errorMessage','STK Push failed.')})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
def mpesa_callback(request):
    if request.method == 'POST':
        try:
            data     = json.loads(request.body)
            callback = data['Body']['stkCallback']
            if callback.get('ResultCode') == 0:
                items   = {i['Name']: i.get('Value') for i in callback['CallbackMetadata']['Item']}
                print(f"✅ Payment: KES {items.get('Amount')} from {items.get('PhoneNumber')} | {items.get('MpesaReceiptNumber')}")
        except Exception as e:
            print(f"Callback error: {e}")
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})


# ── STATIC PAGES ─────────────────────────────────────────────────────────────

def report_dispute(request):
    return render(request, 'report_dispute.html', {'user': request.user})


def hirelink_care(request):
    return render(request, 'hirelink_care.html', {'user': request.user})

def terms(request):
    return render(request, 'terms.html')

def about(request):
    return render(request, 'about.html')

def careers(request):
    return render(request, 'careers.html')

def privacy(request):
    return render(request, 'privacy.html')

def contact(request):
    return render(request, 'contact.html')
