from django.contrib import admin
from django.urls import path
from skillsync import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('delete-account/', views.delete_account, name='delete_account'),

    # Search
    path('search-workers/', views.search_workers, name='search_workers'),

    # Profiles
    path('profile/<int:user_id>/', views.user_profile, name='user_profile'),
    path('profile/update/', views.update_profile, name='update_profile'),

    # Hire flow
    path('hire-request/', views.send_hire_request, name='send_hire_request'),
    path('hire-request/<int:req_id>/respond/', views.respond_hire_request, name='respond_hire_request'),

    # Job request flow (worker → employer)
    path('job-request/', views.send_job_request, name='send_job_request'),
    path('job-request/<int:req_id>/respond/', views.respond_job_request, name='respond_job_request'),

    # Notifications
    path('notifications/', views.notifications_page, name='notifications'),
    path('notifications/unread/', views.unread_notifications, name='unread_notifications'),
    path('notifications/<int:notif_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_read, name='mark_all_read'),

    # Messaging
    path('messages/', views.messages_page, name='messages'),
    path('messages/<int:user_id>/', views.conversation, name='conversation'),
    path('messages/send/', views.send_message, name='send_message'),
    path('messages/<int:user_id>/fetch/', views.fetch_messages, name='fetch_messages'),

    # Status toggle
    path('toggle-status/', views.toggle_status, name='toggle_status'),

    # Payment
    path('make-payment/', views.make_payment, name='make_payment'),
    path('stk-push/', views.stk_push, name='stk_push'),
    path('mpesa-callback/', views.mpesa_callback, name='mpesa_callback'),

    # Care pages
    path('report-dispute/', views.report_dispute, name='report_dispute'),
    path('hirelink-care/', views.hirelink_care, name='hirelink_care'),
]
