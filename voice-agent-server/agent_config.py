from config import settings

DG_AGENT_API = "https://api.deepgram.com/v1/projects"

SYSTEM_PROMPT = """You are an AI receptionist for {business_name}. Your job is to:
1. Answer calls professionally and warmly
2. Answer FAQs about hours, pricing, services
3. Schedule appointments (use the schedule_appointment function)
4. Take messages if the owner isn't available
5. Transfer complex calls to the owner (use transfer_to_owner function)

Business name: {business_name}
Hours: {business_hours}
FAQs: {faqs}

Rules:
- Keep responses brief and natural, under 30 seconds of speaking
- If you don't know the answer, say "Let me transfer you to the owner"
- Never make up prices or availability
- Confirm appointment details before booking
- After booking, summarize the appointment for the caller
- If the caller is angry or abusive, stay polite and offer to transfer
- If this is after business hours, inform the caller and offer to take a message

Call flow:
1. Greet and identify the business
2. Ask how you can help
3. Handle the request (answer, schedule, or transfer)
4. End the call warmly"""

GREETING_TEMPLATE = "Hello, thank you for calling {business_name}. How can I help you today?"


def build_settings(
    business_name: str = "AI Receptionist",
    greeting: str | None = None,
    business_hours: str = "Monday-Friday 9am-5pm",
    faqs: str = "No FAQs configured yet.",
) -> dict:
    """Build the Deepgram Voice Agent Settings message."""
    prompt = SYSTEM_PROMPT.format(
        business_name=business_name,
        business_hours=business_hours,
        faqs=faqs,
    )

    return {
        "type": "Settings",
        "audio": {
            "input": {
                "encoding": "linear16",
                "sample_rate": 24000,
            },
            "output": {
                "encoding": "linear16",
                "sample_rate": 24000,
                "container": "none",
            },
        },
        "agent": {
            "language": "en",
            "listen": {
                "provider": {
                    "type": "deepgram",
                    "model": "nova-3-general",
                    "language": "en",
                    "smart_format": True,
                    "interim_results": True,
                }
            },
            "think": {
                "provider": {
                    "type": "custom",
                },
                "endpoint": {
                    "url": f"{settings.ollama_cloud_endpoint}/chat/completions",
                    "headers": {
                        "Authorization": f"Bearer {settings.ollama_cloud_api_key}",
                        "Content-Type": "application/json",
                    },
                },
                "model": "deepseek-v4-flash",
                "prompt": prompt,
                "functions": build_functions(),
                "context_length": 15000,
                "temperature": 0.5,
            },
            "speak": {
                "provider": {
                    "type": "deepgram",
                    "model": "aura-2-thalia-en",
                    "speed": 1.0,
                }
            },
            "greeting": greeting or GREETING_TEMPLATE.format(business_name=business_name),
        },
    }


def build_functions() -> list[dict]:
    """Build the function definitions for scheduling and messaging."""
    base_url = f"http://localhost:{settings.port}"
    auth_header = f"Bearer {settings.internal_api_key}"

    return [
        {
            "name": "check_availability",
            "description": "Check available appointment slots for a given date",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format",
                    }
                },
                "required": ["date"],
            },
            "endpoint": {
                "url": f"{base_url}/api/scheduling/availability",
                "method": "post",
                "headers": {"Authorization": auth_header},
            },
        },
        {
            "name": "book_appointment",
            "description": "Book an appointment for a caller",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "time": {"type": "string"},
                    "name": {"type": "string", "description": "Caller's name"},
                    "phone": {"type": "string", "description": "Caller's phone number"},
                    "service": {
                        "type": "string",
                        "description": "Type of appointment",
                    },
                },
                "required": ["date", "time", "name", "phone"],
            },
            "endpoint": {
                "url": f"{base_url}/api/scheduling/book",
                "method": "post",
                "headers": {"Authorization": auth_header},
            },
        },
        {
            "name": "transfer_to_owner",
            "description": "Transfer the call to the business owner",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why the call needs the owner",
                    }
                },
                "required": ["reason"],
            },
        },
        {
            "name": "take_message",
            "description": "Take a message for the owner when they can't take the call",
            "parameters": {
                "type": "object",
                "properties": {
                    "caller_name": {"type": "string"},
                    "callback_number": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["caller_name", "callback_number", "message"],
            },
        },
    ]

