from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """
    Sent as a JSON body, never as query parameters. Credentials in a query string
    end up in access logs, browser history, and Referer headers.
    """

    email: EmailStr
    password: str = Field(min_length=8, max_length=256)
    full_name: str | None = Field(default=None, max_length=255)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    email: str
    full_name: str | None
    is_demo: bool
