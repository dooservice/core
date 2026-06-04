from __future__ import annotations


class S3Error(Exception):
    pass


class S3BucketError(S3Error):
    def __init__(self, bucket: str) -> None:
        super().__init__(f"Failed to access or create bucket '{bucket}'")


class S3UploadError(S3Error):
    def __init__(self, key: str) -> None:
        super().__init__(f"Failed to upload '{key}'")


class S3DownloadError(S3Error):
    def __init__(self, key: str) -> None:
        super().__init__(f"Failed to download '{key}'")


class S3DeleteError(S3Error):
    def __init__(self, key: str) -> None:
        super().__init__(f"Failed to delete '{key}'")


class S3InspectError(S3Error):
    def __init__(self, key: str) -> None:
        super().__init__(f"Failed to inspect '{key}'")


class S3MultipartError(S3Error):
    def __init__(self, key: str) -> None:
        super().__init__(f"Failed multipart operation for '{key}'")
