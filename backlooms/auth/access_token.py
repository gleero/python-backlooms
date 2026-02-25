from datetime import UTC, datetime, timedelta

from jose import jwt

from .schema import JWTUserPayload


def create_access_token(
    subject: JWTUserPayload,
    *,
    secret_key: str,
    algorithm: str = "HS256",
    expires_delta: timedelta | None = None,
) -> tuple[str, datetime | None]:
    expiration_datetime: datetime | None = None
    payload = subject.model_dump(exclude_none=True, mode="json")

    # Add expire information
    if expires_delta:
        expire = datetime.now(tz=UTC) + expires_delta
        expiration_datetime = expire
        payload["exp"] = int(expire.timestamp())

    else:
        if "exp" in payload:
            del payload["exp"]

    encoded_jwt = jwt.encode(
        payload,
        secret_key,
        algorithm=algorithm,
    )
    return encoded_jwt, expiration_datetime


def decode_jwt(
    token: str,
    *,
    secret_key: str,
    algorithm: str = "HS256",
) -> JWTUserPayload | None:
    try:
        decoded_token = jwt.decode(
            token,
            secret_key,
            algorithms=algorithm,
        )
        return JWTUserPayload.model_validate(decoded_token)

    except Exception:
        return None
