import os
import uuid
from pathlib import Path
from typing import Union

from fastapi import HTTPException, UploadFile, status

from app.common.utils import sanitize_filename

ALLOWED_REPORT_EXTENSIONS = {".pdf", ".xlsx", ".csv"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".csv", ".png", ".jpg", ".jpeg", ".txt", ".zip"}


def validate_file_extension(filename: str, allowed_extensions: set[str]) -> bool:
    """Checks if the file extension is allowed."""
    ext = Path(filename).suffix.lower()
    return ext in allowed_extensions


def validate_file_size(file_size: int, max_size_mb: float = 10.0) -> bool:
    """Validates that file size does not exceed max limit in MB."""
    max_bytes = max_size_mb * 1024 * 1024
    return file_size <= max_bytes


def generate_unique_filename(original_filename: str) -> str:
    """Generates a UUID-prefixed unique filename."""
    sanitized = sanitize_filename(original_filename)
    unique_prefix = uuid.uuid4().hex[:10]
    return f"{unique_prefix}_{sanitized}"


async def save_upload_file(
    upload_file: UploadFile,
    destination_directory: Union[str, Path],
    allowed_extensions: set[str] = ALLOWED_REPORT_EXTENSIONS,
    max_size_mb: float = 10.0,
) -> Path:
    """
    Validates and saves an uploaded file to the specified destination directory.
    Returns the absolute path to the saved file.
    """
    if not upload_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty",
        )

    if not validate_file_extension(upload_file.filename, allowed_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}",
        )

    # Read content to verify size
    content = await upload_file.read()
    if not validate_file_size(len(content), max_size_mb=max_size_mb):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum limit of {max_size_mb} MB",
        )

    dest_dir = Path(destination_directory)
    dest_dir.mkdir(parents=True, exist_ok=True)

    unique_name = generate_unique_filename(upload_file.filename)
    file_path = dest_dir / unique_name

    with open(file_path, "wb") as f:
        f.write(content)

    # Reset file cursor position
    await upload_file.seek(0)
    return file_path


def delete_file(file_path: Union[str, Path]) -> bool:
    """Deletes a file from local storage if it exists."""
    path = Path(file_path)
    if path.exists() and path.is_file():
        os.remove(path)
        return True
    return False
