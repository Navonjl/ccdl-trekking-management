"""CSV exports in Azure Blob Storage.

Used only when Config.EXPORT_BLOB_ACCOUNT_URL is set, which it is in the AKS
cluster. There a worker pod writes the CSV and an API pod hands it out, and
the two do not share a disk, so the file has to live somewhere both can reach.

Both sides authenticate with DefaultAzureCredential, which in the cluster picks
up the pod's Microsoft Entra workload identity. No storage key exists in the
app or its configuration.
"""

from datetime import datetime, timedelta, timezone

from azure.identity import DefaultAzureCredential
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    ContentSettings,
    generate_blob_sas,
)

from .config import Config

# How long a download link works for.
LINK_LIFETIME = timedelta(minutes=15)

_client = None


def enabled():
    return bool(Config.EXPORT_BLOB_ACCOUNT_URL)


def _service():
    global _client
    if _client is None:
        _client = BlobServiceClient(Config.EXPORT_BLOB_ACCOUNT_URL, credential=DefaultAzureCredential())
    return _client


def upload_csv(blob_name, data):
    """Store the CSV text. Overwrites, so a retried task leaves one file."""
    blob = _service().get_blob_client(Config.EXPORT_BLOB_CONTAINER, blob_name)
    blob.upload_blob(
        data.encode("utf-8"),
        overwrite=True,
        content_settings=ContentSettings(content_type="text/csv"),
    )


def exists(blob_name):
    return _service().get_blob_client(Config.EXPORT_BLOB_CONTAINER, blob_name).exists()


def download_url(blob_name):
    """A read-only link to one blob that expires after LINK_LIFETIME.

    Signed with a user delegation key, which is itself issued to the pod's
    identity, so revoking the identity's role also kills every link.
    """
    service = _service()
    now = datetime.now(timezone.utc)
    key = service.get_user_delegation_key(now - timedelta(minutes=5), now + LINK_LIFETIME)
    sas = generate_blob_sas(
        account_name=service.account_name,
        container_name=Config.EXPORT_BLOB_CONTAINER,
        blob_name=blob_name,
        user_delegation_key=key,
        permission=BlobSasPermissions(read=True),
        expiry=now + LINK_LIFETIME,
        content_disposition=f'attachment; filename="{blob_name}"',
    )
    return f"{service.url}{Config.EXPORT_BLOB_CONTAINER}/{blob_name}?{sas}"
