from nats.aio.client import Client
from nats.js import JetStreamContext
from nats.js.errors import NotFoundError

from core.settings import settings

nc: Client = Client()


async def connect_nats() -> None:
    await nc.connect(
        settings.nats_url,
        connect_timeout=2,
        max_reconnect_attempts=-1,
        reconnect_time_wait=1,
        name="uttg-api",
    )


async def close_nats() -> None:
    if not nc.is_closed:
        await nc.close()


async def ensure_event_stream() -> JetStreamContext:
    jetstream = nc.jetstream()
    try:
        await jetstream.stream_info("EVENTS")
    except NotFoundError:
        try:
            await jetstream.add_stream(name="EVENTS", subjects=["events.>"])
        except Exception:
            # Another scheduler/worker may have created it between the two calls.
            await jetstream.stream_info("EVENTS")
    return jetstream
