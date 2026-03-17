from django import forms
from .models import User


class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model  = User
        fields = [
            'email', 'full_name', 'role',
            'skills', 'hourly_wage', 'hours_per_day', 'working_days',
            'password',
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user
