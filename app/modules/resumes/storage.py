"""Resume storage backends and factory."""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4
from typing import Literal

import boto3
from app.config import settings
from app.observability.logging import get_logger

logger = get_logger(__name__)

# Allowed MIME types for resume uploads
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# Maximum file size: 10 MB
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


class StorageService(ABC):
    """Abstract base class for resume storage backends."""

    @abstractmethod
    async def store(self, file_bytes: bytes, filename: str, org_id: str) -> str:
        """
        Store a resume file and return the storage URI.

        Args:
            file_bytes: The file content as bytes
            filename: The original filename
            org_id: The organization ID for scoping storage

        Returns:
            A storage URI (e.g., 'local://path/to/file' or 's3://bucket/key')
        """
        pass

    @abstractmethod
    async def delete(self, storage_uri: str) -> None:
        """
        Delete a resume file from storage.

        Args:
            storage_uri: The storage URI returned by store()
        """
        pass


class LocalStorageBackend(StorageService):
    """Local filesystem storage backend for development."""

    def __init__(self, base_path: str | None = None):
        """
        Initialize the local storage backend.

        Args:
            base_path: Base directory for storing files. Defaults to settings.STORAGE_LOCAL_PATH
        """
        self.base_path = base_path or settings.STORAGE_LOCAL_PATH

    async def store(self, file_bytes: bytes, filename: str, org_id: str) -> str:
        """
        Store a resume file in the local filesystem.

        Args:
            file_bytes: The file content as bytes
            filename: The original filename
            org_id: The organization ID for scoping storage

        Returns:
            A local:// URI pointing to the stored file
        """
        # Create organization-scoped directory
        org_dir = Path(self.base_path) / str(org_id)
        org_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename with UUID prefix
        unique_filename = f"{uuid4()}_{filename}"
        file_path = org_dir / unique_filename

        # Write file to disk
        file_path.write_bytes(file_bytes)

        # Return local:// URI
        storage_uri = f"local://{file_path}"
        logger.info(
            "resume_stored_locally",
            org_id=str(org_id),
            filename=filename,
            storage_uri=storage_uri,
        )
        return storage_uri

    async def delete(self, storage_uri: str) -> None:
        """
        Delete a resume file from the local filesystem.

        Args:
            storage_uri: The local:// URI returned by store()
        """
        if not storage_uri.startswith("local://"):
            logger.warning("invalid_local_storage_uri", storage_uri=storage_uri)
            return

        # Extract path from URI
        file_path = Path(storage_uri.replace("local://", ""))

        try:
            if file_path.exists():
                file_path.unlink()
                logger.info("resume_deleted_locally", file_path=str(file_path))
        except Exception as exc:
            logger.error(
                "failed_to_delete_local_resume",
                file_path=str(file_path),
                error=str(exc),
            )


class S3StorageBackend(StorageService):
    """S3-compatible storage backend for cloud deployment."""

    def __init__(self):
        """Initialize the S3 storage backend."""
        self.s3_client = boto3.client("s3")
        self.bucket_name = settings.RESUME_BUCKET_NAME

    async def store(self, file_bytes: bytes, filename: str, org_id: str) -> str:
        """
        Store a resume file in S3.

        Args:
            file_bytes: The file content as bytes
            filename: The original filename
            org_id: The organization ID for scoping storage

        Returns:
            An s3:// URI pointing to the stored object
        """
        # Generate unique key with organization scope
        unique_filename = f"{uuid4()}_{filename}"
        s3_key = f"{org_id}/{unique_filename}"

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_bytes,
            )
            storage_uri = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(
                "resume_stored_s3",
                org_id=str(org_id),
                filename=filename,
                s3_key=s3_key,
                storage_uri=storage_uri,
            )
            return storage_uri
        except Exception as exc:
            logger.error(
                "failed_to_store_resume_s3",
                org_id=str(org_id),
                filename=filename,
                error=str(exc),
            )
            raise

    async def delete(self, storage_uri: str) -> None:
        """
        Delete a resume file from S3.

        Args:
            storage_uri: The s3:// URI returned by store()
        """
        if not storage_uri.startswith("s3://"):
            logger.warning("invalid_s3_storage_uri", storage_uri=storage_uri)
            return

        try:
            # Extract bucket and key from URI
            # Format: s3://bucket-name/key
            parts = storage_uri.replace("s3://", "").split("/", 1)
            if len(parts) != 2:
                logger.warning("malformed_s3_storage_uri", storage_uri=storage_uri)
                return

            bucket, key = parts
            self.s3_client.delete_object(Bucket=bucket, Key=key)
            logger.info("resume_deleted_s3", bucket=bucket, key=key)
        except Exception as exc:
            logger.error(
                "failed_to_delete_resume_s3",
                storage_uri=storage_uri,
                error=str(exc),
            )


def get_storage_service() -> StorageService:
    """
    Factory function to get the appropriate storage backend.

    Returns:
        A StorageService instance (LocalStorageBackend or S3StorageBackend)
        based on the STORAGE_BACKEND configuration.
    """
    if settings.STORAGE_BACKEND == "s3":
        return S3StorageBackend()
    else:
        return LocalStorageBackend()
