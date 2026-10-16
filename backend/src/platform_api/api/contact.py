import re
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from platform_api.database import get_db
from platform_api.identity_models import ContactMessage

router = APIRouter(prefix="/contact", tags=["contact"])

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class ContactRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=3, max_length=320)
    subject: str = Field(..., min_length=1, max_length=300)
    message: str = Field(..., min_length=1, max_length=5000)
    category: str = Field("general", max_length=50)


class ContactResponse(BaseModel):
    success: bool
    ticket_id: str
    message: str


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def submit_contact(
    req: ContactRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ContactResponse:
    clean_email = req.email.lower().strip()
    if not EMAIL_REGEX.match(clean_email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Please provide a valid email address.",
        )

    ticket_id = f"TICK-{uuid4().hex[:8].upper()}"
    try:
        msg = ContactMessage(
            name=req.name.strip(),
            email=clean_email,
            subject=req.subject.strip(),
            message=req.message.strip(),
            category=req.category,
            status="received",
        )
        db.add(msg)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to submit contact request. Please try again later.",
        ) from exc

    return ContactResponse(
        success=True,
        ticket_id=ticket_id,
        message="Thank you! Your message has been received and our engineering support team will respond shortly.",
    )
