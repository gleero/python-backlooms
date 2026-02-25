import uuid

import pytest
from pydantic import ValidationError

from backlooms.auth import JWTUserPayload


def test_jwt_payload_empty():
    with pytest.raises(ValidationError):
        JWTUserPayload.model_validate({})


def test_jwt_payload_i_number():
    m = JWTUserPayload.model_validate({"i": 42})
    assert m.i == 42
    assert m.n is None
    assert m.t == "u"
    assert m.exp is None


def test_jwt_payload_i_uuid():
    uuid_value = uuid.uuid4()
    m = JWTUserPayload.model_validate({"i": str(uuid_value)})

    assert isinstance(m.i, uuid.UUID)
    assert str(m.i) == str(uuid_value)
    assert m.n is None
    assert m.t == "u"
    assert m.exp is None


def test_jwt_payload_fields():
    m = JWTUserPayload.model_validate({"i": 42, "n": "test", "exp": 12345})

    assert m.i == 42
    assert m.n == "test"
    assert m.exp == 12345
    assert m.t == "u"


def test_jwt_payload_type_token():
    m = JWTUserPayload.model_validate({"i": 42, "t": "t"})

    assert m.t == "t"


def test_jwt_payload_type_other():
    with pytest.raises(ValidationError):
        JWTUserPayload.model_validate({"i": 42, "t": "xxx"})
