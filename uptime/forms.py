from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from .models import Monitor


def normalize_url(value):
    """example.com -> https://example.com/"""
    value = value.strip()
    if value and "://" not in value:
        value = f"https://{value}"
    if value.count("/") == 2:
        value += "/"
    return value


class MonitorForm(forms.ModelForm):
    url = forms.CharField(label=_("URL"), max_length=500,
                          widget=forms.TextInput(attrs={"placeholder": "https://example.com/", "inputmode": "url"}))

    class Meta:
        model = Monitor
        fields = ["url", "interval", "notify", "webhook_url", "enabled"]
        widgets = {"webhook_url": forms.URLInput(attrs={"placeholder": "https://hooks.slack.com/services/…"})}

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = self.instance.project = project

    def clean_url(self):
        url = normalize_url(self.cleaned_data["url"])
        url = forms.URLField(assume_scheme="https").clean(url)
        if not url.startswith(("http://", "https://")):
            raise forms.ValidationError(_("Use an http:// or https:// address."))
        duplicates = Monitor.objects.filter(project=self.project, url=url).exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError(_("This URL is already monitored in this project."))
        return url

    def clean(self):
        data = super().clean()
        limit = settings.FALCONDB_UPTIME_MAX_MONITORS
        if self.instance.pk is None and Monitor.objects.filter(project=self.project).count() >= limit:
            raise forms.ValidationError(_("A project can have up to %(limit)s monitors.") % {"limit": limit})
        return data
