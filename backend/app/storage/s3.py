import io
import uuid

import boto3
from botocore.config import Config

from ..config import settings


class Storage:
    """S3/MinIO-compatible object storage abstraction (private/public buckets)."""

    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name="us-east-1",
            config=Config(signature_version="s3v4"),
        )

    @staticmethod
    def _bucket(private: bool) -> str:
        return settings.s3_bucket_private if private else settings.s3_bucket_public

    def put_bytes(self, data: bytes, key: str, private: bool, content_type: str = "application/octet-stream") -> str:
        self.client.put_object(
            Bucket=self._bucket(private),
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return key

    def put_object(self, obj, key: str, private: bool, content_type: str = "application/octet-stream") -> str:
        data = obj.read() if hasattr(obj, "read") else obj
        return self.put_bytes(data, key, private, content_type)

    def get_bytes(self, key: str, private: bool) -> bytes:
        resp = self.client.get_object(Bucket=self._bucket(private), Key=key)
        return resp["Body"].read()

    def exists(self, key: str, private: bool) -> bool:
        try:
            self.client.head_object(Bucket=self._bucket(private), Key=key)
            return True
        except Exception:
            return False

    def object_exists_or_put(self, data: bytes, key: str, private: bool, content_type: str) -> bool:
        """Idempotent write; returns True if already existed."""
        if self.exists(key, private):
            return True
        self.put_bytes(data, key, private, content_type)
        return False


storage = Storage()