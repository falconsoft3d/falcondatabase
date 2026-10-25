"""Profile picture processing: square crop, resize and WebP encoding."""

from io import BytesIO

from django.utils.translation import gettext as _
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Avatar

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}


class AvatarError(Exception):
    pass


def process(upload):
    """Return WebP bytes for an uploaded image, or raise AvatarError."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise AvatarError(_("The image is too large (maximum 5 MB)."))
    try:
        image = Image.open(upload)
        if image.format not in ALLOWED_FORMATS:
            raise AvatarError(_("Use a PNG, JPG, WebP or GIF image."))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise AvatarError(_("The file is not a valid image."))
    image = ImageOps.exif_transpose(image)
    image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    image = ImageOps.fit(image, (Avatar.SIZE, Avatar.SIZE), Image.Resampling.LANCZOS)
    output = BytesIO()
    image.save(output, "WEBP", quality=85, method=6)
    return output.getvalue()


def save(user, upload):
    data = process(upload)
    Avatar.objects.update_or_create(user=user, defaults={"image": data})
