import uuid
from datetime import datetime, timezone

from sqlalchemy import Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    business_name: Mapped[str] = mapped_column(Text, nullable=False)
    owner_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(Text, default="America/Vancouver")
    twilio_phone_number: Mapped[str | None] = mapped_column(Text, nullable=True)
    deepgram_agent_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    faqs: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    greeting: Mapped[str | None] = mapped_column(Text, nullable=True)
    calendar_integration: Mapped[str | None] = mapped_column(Text, nullable=True)
    calendar_credentials: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
