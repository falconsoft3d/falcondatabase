from django.contrib import admin

from .models import Avatar, SiteSettings, TwoFactor


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("__str__", "allow_signup")


@admin.register(TwoFactor)
class TwoFactorAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    exclude = ("secret", "recovery_codes", "last_counter")
