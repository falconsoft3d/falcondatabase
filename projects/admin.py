from django.contrib import admin

from .models import Project, ProjectTable, ProjectUser


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "ref", "auth_enabled", "created_at")
    search_fields = ("name", "ref", "owner__username")
    readonly_fields = ("ref",)


@admin.register(ProjectTable)
class ProjectTableAdmin(admin.ModelAdmin):
    list_display = ("name", "project", "access", "created_at")
    list_filter = ("access",)


@admin.register(ProjectUser)
class ProjectUserAdmin(admin.ModelAdmin):
    list_display = ("email", "project", "is_active", "created_at", "last_login")
    exclude = ("password",)
