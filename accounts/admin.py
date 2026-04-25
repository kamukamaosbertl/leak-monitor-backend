from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    fields = ("role", "phone_number", "department", "is_available")


class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ("username", "email", "is_staff", "is_superuser")
    search_fields = ("username", "email")


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)