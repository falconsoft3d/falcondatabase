import re

from django import forms
from django.utils.translation import gettext_lazy as _

from . import schema
from .models import Project, ProjectTable

TYPE_CHOICES = [
    ("text", _("text — text")),
    ("integer", _("integer — whole number")),
    ("bigint", _("bigint — large whole number")),
    ("decimal", _("decimal — exact number")),
    ("float", _("float — number with decimals")),
    ("boolean", _("boolean — true/false")),
    ("date", _("date — date")),
    ("datetime", _("datetime — date and time")),
    ("json", _("json — object or list")),
    ("uuid", _("uuid — unique identifier")),
]
COLUMN_FIELD_RE = re.compile(r"^columns-(\d+)-(name|type|default|required|unique)$")


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description"]
        widgets = {"description": forms.TextInput(attrs={"placeholder": _("Optional")})}


class TableForm(forms.Form):
    name = forms.CharField(label=_("Table name"), max_length=63)
    description = forms.CharField(label=_("Description"), max_length=300, required=False)
    access = forms.ChoiceField(label=_("API access"), choices=ProjectTable.ACCESS_CHOICES,
                               initial=ProjectTable.PUBLIC_READ)

    def clean_name(self):
        try:
            name = schema.validate_identifier(self.cleaned_data["name"].lower(), _("Table name"))
        except schema.SchemaError as exc:
            raise forms.ValidationError(str(exc))
        if name == "new":
            raise forms.ValidationError(_("“new” is reserved, choose another name."))
        return name


def columns_from_post(data):
    """Read the dynamic ``columns-<n>-<field>`` inputs of the new-table form."""
    rows = {}
    for key in data:
        match = COLUMN_FIELD_RE.match(key)
        if match:
            rows.setdefault(int(match.group(1)), {})[match.group(2)] = data.get(key)
    columns = []
    for _index, row in sorted(rows.items()):
        name = (row.get("name") or "").strip().lower()
        if not name:
            continue
        columns.append({
            "name": name,
            "type_": row.get("type") or "text",
            "required": bool(row.get("required")),
            "unique": bool(row.get("unique")),
            "default": row.get("default") or None,
        })
    return columns


class ColumnForm(forms.Form):
    name = forms.CharField(label=_("Name"), max_length=63)
    type = forms.ChoiceField(label=_("Type"), choices=TYPE_CHOICES)
    default = forms.CharField(label=_("Default value"), required=False,
                              help_text=_("Optional. Use now() for dates or uuid() for uuid."))
    required = forms.BooleanField(label=_("Required (NOT NULL)"), required=False)
    unique = forms.BooleanField(label=_("Unique"), required=False)

    def as_column(self):
        data = self.cleaned_data
        return {
            "name": data["name"].strip().lower(),
            "type_": data["type"],
            "required": data["required"],
            "unique": data["unique"],
            "default": data["default"] or None,
        }


class ProjectUserForm(forms.Form):
    email = forms.EmailField(label=_("Email"))
    password = forms.CharField(label=_("Password"), min_length=6, widget=forms.PasswordInput)
