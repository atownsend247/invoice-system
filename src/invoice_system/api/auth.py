from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sessionkit import AuthService, OtpInvalid, User


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth.service


def get_current_user(
    authorization: str | None = Header(default=None),
    auth: AuthService = Depends(get_auth_service),
) -> User:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    return auth.user_for_token(token)  # raises AuthenticationError -> mapped to 401


class LoginIn(BaseModel):
    email: str
    password: str
    otp: str | None = None


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    created_at: datetime
    totp_enabled: bool

    @classmethod
    def from_model(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            created_at=user.created_at,
            totp_enabled=user.totp_enabled,
        )


class LoginOut(BaseModel):
    token: str
    expires_at: datetime
    user: UserOut


public_router = APIRouter(prefix="/auth", tags=["auth"])
protected_router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(get_current_user)])


@public_router.post("/login", response_model=LoginOut)
def login(body: LoginIn, auth: AuthService = Depends(get_auth_service)) -> LoginOut:
    try:
        result = auth.login(body.email, body.password, otp=body.otp)
    except OtpInvalid as exc:
        # OtpInvalid isn't an AuthenticationError (see sessionkit/errors.py) so
        # the global handler would map it to 422; at login it means the same
        # thing as bad credentials to the caller.
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return LoginOut(token=result.token, expires_at=result.expires_at, user=UserOut.from_model(result.user))


@protected_router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.from_model(user)


@protected_router.post("/logout", status_code=204)
def logout(
    authorization: str | None = Header(default=None), auth: AuthService = Depends(get_auth_service)
) -> None:
    token = authorization.split(" ", 1)[1].strip() if authorization else None
    auth.logout(token)
