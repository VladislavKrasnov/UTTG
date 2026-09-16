import valkey.asyncio as valkey

from core.settings import settings

valkey_client = valkey.from_url(settings.valkey_url)  # type: ignore[no-untyped-call]
