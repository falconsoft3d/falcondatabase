import re
from urllib.parse import urlsplit

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from uptime.forms import normalize_url

from .models import CronJob

HEADER_NAME = re.compile(r"[A-Za-z0-9-]+")


class CronJobForm(forms.ModelForm):
    url = forms.CharField(label=_("URL"), max_length=500)
    # Write-only: the saved value is never sent back to the browser.
    header_value = forms.CharField(required=False, max_length=1000)
    clear_header = forms.BooleanField(required=False)

    class Meta:
        model = CronJob
        fields = ["name", "url", "method", "interval", "header_name", "enabled"]

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = self.instance.project = project
        self.saved_host = self.instance.host if self.instance.pk else ""

    def clean_url(self):
        url = forms.URLField(assume_scheme="https").clean(normalize_url(self.cleaned_data["url"]))
        if not url.startswith(("http://", "https://")):
            raise forms.ValidationError(_("Use an http:// or https:// address."))
        return url

    def clean_header_name(self):
        name = self.cleaned_data["header_name"].strip()
        if name and not HEADER_NAME.fullmatch(name):
            raise forms.ValidationError(_("Use only letters, numbers and hyphens."))
        return name

    def clean_header_value(self):
        value = self.cleaned_data["header_value"]
        if any(ord(char) < 32 for char in value):
            raise forms.ValidationError(_("The value can't contain line breaks."))
        return value

    def clean(self):
        data = super().clean()
        limit = settings.FALCONDB_CRON_MAX_JOBS
        if self.instance.pk is None and CronJob.objects.filter(project=self.project).count() >= limit:
            raise forms.ValidationError(_("A project can have up to %(limit)s cron jobs.") % {"limit": limit})

        if data.get("clear_header") or not data.get("header_name"):
            data["header_name"] = data["header_value"] = ""
            return data
        keeps_value = not data.get("header_value")
        if keeps_value and not self.saved_value():
            self.add_error("header_value", _("Enter the value of the header."))
        elif keeps_value and "url" in data and self.host_changed(data["url"]):
            # The saved secret must not be sent to a new address without typing it again.
            self.add_error("header_value", _("The address changed: enter the value of the header again."))
        return data

    def saved_value(self):
        return CronJob.objects.filter(pk=self.instance.pk).values_list("header_value", flat=True).first()

    def host_changed(self, url):
        return urlsplit(url).netloc != self.saved_host

    def save(self, commit=True):
        job = super().save(commit=False)
        data = self.cleaned_data
        if data["header_value"] or not data["header_name"]:
            job.header_value = data["header_value"]
        if commit:
            job.save()
        return job
