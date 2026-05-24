import logging

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from config import settings

logger = logging.getLogger(__name__)


def _get_client() -> Client:
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def buy_phone_number(area_code: str = "604") -> dict:
    """Buy a Twilio phone number. Returns {phone_number, sid}."""
    client = _get_client()

    numbers = client.available_phone_numbers("US").local.list(
        area_code=area_code, limit=1
    )
    if not numbers:
        numbers = client.available_phone_numbers("CA").local.list(
            area_code=area_code, limit=1
        )

    if not numbers:
        raise Exception(f"No available numbers in area code {area_code}")

    purchased = client.incoming_phone_numbers.create(
        phone_number=numbers[0].phone_number
    )

    logger.info(
        "Purchased number %s (SID: %s)", purchased.phone_number, purchased.sid
    )
    return {"phone_number": purchased.phone_number, "sid": purchased.sid}


def configure_voice_url(phone_number_sid: str, voice_url: str) -> None:
    """Set the voice webhook URL for a Twilio phone number."""
    client = _get_client()
    number = client.incoming_phone_numbers(phone_number_sid).update(
        voice_url=voice_url,
        voice_method="POST",
    )
    logger.info("Configured voice URL for %s: %s", number.phone_number, voice_url)


def release_phone_number(phone_number_sid: str) -> None:
    """Release a Twilio phone number."""
    client = _get_client()
    try:
        client.incoming_phone_numbers(phone_number_sid).delete()
        logger.info("Released phone number SID: %s", phone_number_sid)
    except TwilioRestException as e:
        logger.error("Failed to release number %s: %s", phone_number_sid, e)


def send_sms(to: str, body: str) -> str | None:
    """Send an SMS via Twilio. Returns message SID or None on failure."""
    client = _get_client()
    try:
        message = client.messages.create(
            body=body,
            from_=settings.twilio_phone_number_sid,
            to=to,
        )
        logger.info("Sent SMS to %s: %s", to, message.sid)
        return message.sid
    except TwilioRestException as e:
        logger.error("Failed to send SMS to %s: %s", to, e)
        return None
