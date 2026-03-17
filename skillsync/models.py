from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


class UserManager(BaseUserManager):
    def create_user(self, email, full_name, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, full_name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (('employer', 'Employer'), ('worker', 'Worker'))
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('unavailable', 'Unavailable'),
        ('hiring', 'Hiring'),
        ('not_hiring', 'Not Hiring'),
    )

    email         = models.EmailField(unique=True)
    full_name     = models.CharField(max_length=150)
    role          = models.CharField(max_length=10, choices=ROLE_CHOICES)
    is_active     = models.BooleanField(default=True)
    is_staff      = models.BooleanField(default=False)
    date_joined   = models.DateTimeField(auto_now_add=True)

    # Professional details
    skills        = models.CharField(max_length=300, blank=True)
    hourly_wage   = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    hours_per_day = models.PositiveIntegerField(null=True, blank=True)
    working_days  = models.CharField(max_length=100, blank=True)
    bio           = models.TextField(blank=True)

    # Status
    status        = models.CharField(max_length=15, choices=STATUS_CHOICES, default='available')

    # Employer: job ad / skills wanted
    job_ad        = models.TextField(blank=True, help_text='Skills/roles employer is looking to hire')

    groups = models.ManyToManyField('auth.Group', blank=True, related_name='skillsync_users')
    user_permissions = models.ManyToManyField('auth.Permission', blank=True, related_name='skillsync_users')

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['full_name']
    objects = UserManager()

    def get_skills_list(self):
        return [s.strip() for s in self.skills.split(',') if s.strip()]

    def get_working_days_list(self):
        return [d.strip() for d in self.working_days.split(',') if d.strip()]

    def hired_count(self):
        return HireRequest.objects.filter(employer=self, status='accepted').count()

    def jobs_count(self):
        return HireRequest.objects.filter(worker=self, status='accepted').count()

    def unread_notifications(self):
        return self.notifications_received.filter(is_read=False).count()

    def __str__(self):
        return f"{self.full_name} ({self.role})"


class HireRequest(models.Model):
    STATUS = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
    )
    employer   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hire_requests_sent')
    worker     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hire_requests_received')
    message    = models.TextField(blank=True)
    status     = models.CharField(max_length=10, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employer} → {self.worker} [{self.status}]"


class JobRequest(models.Model):
    """Worker requests a job from an employer"""
    STATUS = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    )
    worker     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_requests_sent')
    employer   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_requests_received')
    message    = models.TextField(blank=True)
    status     = models.CharField(max_length=10, choices=STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.worker} → {self.employer} [{self.status}]"


class Notification(models.Model):
    TYPE = (
        ('hire_request', 'Hire Request'),
        ('hire_accepted', 'Hire Accepted'),
        ('hire_rejected', 'Hire Rejected'),
        ('job_request', 'Job Request'),
        ('job_accepted', 'Job Accepted'),
        ('job_rejected', 'Job Rejected'),
        ('message', 'Message'),
        ('general', 'General'),
    )
    recipient  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_received')
    sender     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications_sent', null=True, blank=True)
    notif_type = models.CharField(max_length=20, choices=TYPE, default='general')
    title      = models.CharField(max_length=200)
    body       = models.TextField(blank=True)
    is_read    = models.BooleanField(default=False)
    link       = models.CharField(max_length=200, blank=True)
    related_id = models.IntegerField(null=True, blank=True)  # HireRequest or JobRequest id
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"To {self.recipient}: {self.title}"


class Message(models.Model):
    sender    = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages_sent')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages_received')
    body      = models.TextField()
    is_read   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender} → {self.recipient}: {self.body[:40]}"
