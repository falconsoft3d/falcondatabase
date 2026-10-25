from django import template
from django.utils.translation import gettext_lazy as _

register = template.Library()

MEDIUMS = {
    "direct": _("Direct"), "organic": _("Organic search"), "social": _("Social"), "referral": _("Referral"),
    "cpc": _("Paid search"), "ppc": _("Paid search"), "paid": _("Paid"), "email": _("Email"),
}
DEVICES = {"desktop": _("Desktop"), "mobile": _("Mobile"), "tablet": _("Tablet")}


@register.filter
def flag(code):
    """ISO country code -> flag emoji (empty for unknown)."""
    if not code or len(code) != 2 or not code.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


@register.filter
def medium_label(value):
    return MEDIUMS.get(value, value)


@register.filter
def device_label(value):
    return DEVICES.get(value, value)


@register.filter
def compact(value):
    """1234 -> 1.2K, 1250000 -> 1.3M."""
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:g}"
    for size, suffix in ((1_000_000, "M"), (1_000, "K")):
        if abs(value) >= size:
            return f"{value / size:.1f}".rstrip("0").rstrip(".") + suffix
    return str(value)


@register.filter
def split(value):
    return value.split()


@register.filter(name="abs")
def absolute(value):
    return abs(value)
