"""S3-compatible storage client (MinIO / AWS S3)."""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from dooservice_models import DOWNLOAD_CHUNK_SIZE

from .error import S3BucketError, S3DeleteError, S3DownloadError, S3InspectError, S3MultipartError, S3UploadError


class StorageClient:
    """Async S3 client backed by boto3. All I/O is offloaded via asyncio.to_thread."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str = "dooservice-backups",
        region: str = "us-east-1",
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    async def ensure_bucket(self) -> None:
        try:
            await asyncio.to_thread(self._client.head_bucket, Bucket=self._bucket)
        except ClientError:
            try:
                await asyncio.to_thread(self._client.create_bucket, Bucket=self._bucket)
            except ClientError as e:
                raise S3BucketError(self._bucket) from e

    async def upload(self, local_path: Path | str, object_key: str | None = None) -> str:
        path = Path(local_path)
        key = object_key or path.name
        try:
            await asyncio.to_thread(self._client.upload_file, str(path), self._bucket, key)
        except ClientError as e:
            raise S3UploadError(key) from e
        return key

    async def download(self, object_key: str, local_path: Path | str) -> None:
        """Stream object to disk via get_object — avoids HeadObject."""
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        def _stream() -> None:
            response = self._client.get_object(Bucket=self._bucket, Key=object_key)
            with open(dest, "wb") as fh:
                for chunk in response["Body"].iter_chunks(DOWNLOAD_CHUNK_SIZE):
                    fh.write(chunk)

        try:
            await asyncio.to_thread(_stream)
        except ClientError as e:
            raise S3DownloadError(object_key) from e

    async def delete(self, object_key: str) -> None:
        try:
            await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=object_key)
        except ClientError as e:
            raise S3DeleteError(object_key) from e

    async def presign_download(self, object_key: str, expires_in: int = 3600) -> str:
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )

    async def exists(self, object_key: str) -> bool:
        try:
            await asyncio.to_thread(self._client.head_object, Bucket=self._bucket, Key=object_key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "404":
                return False
            raise S3InspectError(object_key) from e

    async def size(self, object_key: str) -> int:
        try:
            head = await asyncio.to_thread(self._client.head_object, Bucket=self._bucket, Key=object_key)
        except ClientError as e:
            raise S3InspectError(object_key) from e
        return head["ContentLength"]

    async def create_multipart_upload(self, object_key: str) -> str:
        try:
            response = await asyncio.to_thread(
                self._client.create_multipart_upload,
                Bucket=self._bucket,
                Key=object_key,
                ContentType="application/zip",
            )
        except ClientError as e:
            raise S3MultipartError(object_key) from e
        return response["UploadId"]

    async def presign_upload_part(
        self, object_key: str, upload_id: str, part_number: int, expires_in: int = 3600
    ) -> str:
        try:
            return await asyncio.to_thread(
                self._client.generate_presigned_url,
                "upload_part",
                Params={
                    "Bucket":     self._bucket,
                    "Key":        object_key,
                    "UploadId":   upload_id,
                    "PartNumber": part_number,
                },
                ExpiresIn=expires_in,
            )
        except ClientError as e:
            raise S3MultipartError(object_key) from e

    async def complete_multipart_upload(self, object_key: str, upload_id: str, parts: list[dict]) -> None:
        try:
            await asyncio.to_thread(
                self._client.complete_multipart_upload,
                Bucket=self._bucket,
                Key=object_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except ClientError as e:
            raise S3MultipartError(object_key) from e

    async def abort_multipart_upload(self, object_key: str, upload_id: str) -> None:
        with contextlib.suppress(ClientError):
            await asyncio.to_thread(
                self._client.abort_multipart_upload,
                Bucket=self._bucket,
                Key=object_key,
                UploadId=upload_id,
            )
