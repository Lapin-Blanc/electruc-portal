"""Upload validators (size and extension)."""
from django.core.exceptions import ValidationError

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "doc", "docx"}


def validate_upload_size(file_obj):
    """Reject files larger than MAX_UPLOAD_SIZE."""
    if file_obj.size > MAX_UPLOAD_SIZE:
        raise ValidationError("Le fichier dépasse 5 Mo.")


def validate_upload_extension(file_obj):
    """Allow only known extensions."""
    name = getattr(file_obj, "name", "")
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("Type de fichier non autorisé.")
