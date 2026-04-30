"""Tests for JWT service."""
import time
from uuid import uuid4

import pytest
from stonks_backend.infrastructure.config import Settings
from stonks_backend.infrastructure.security.jwt_service import JWTService, TokenPair


class TestJWTService:
    @pytest.fixture
    def settings(self) -> Settings:
        return Settings(
            jwt_secret="test-secret-at-least-32-chars!!",
            jwt_algorithm="HS256",
            jwt_access_token_expire_minutes=15,
            jwt_refresh_token_expire_days=7,
            jwt_issuer="stonks-backend",
        )

    @pytest.fixture
    def jwt_svc(self, settings: Settings) -> JWTService:
        return JWTService.from_settings(settings)

    @pytest.fixture
    def user_id(self) -> str:
        return str(uuid4())

    def test_create_token_pair(self, jwt_svc: JWTService, user_id: str) -> None:
        tokens = jwt_svc.create_token_pair(user_id, "test@example.com")
        assert isinstance(tokens, TokenPair)
        assert len(tokens.access_token) > 50
        assert len(tokens.refresh_token) > 50
        assert tokens.token_type == "bearer"

    def test_decode_access_token(self, jwt_svc: JWTService, user_id: str) -> None:
        token = jwt_svc.create_access_token(user_id, "test@example.com")
        payload = jwt_svc.decode_access_token(token)
        assert payload.sub == user_id
        assert payload.type == "access"
        assert payload.iss == "stonks-backend"
        assert payload.email == "test@example.com"

    def test_decode_refresh_token(self, jwt_svc: JWTService, user_id: str) -> None:
        token = jwt_svc.create_refresh_token(user_id)
        payload = jwt_svc.decode_refresh_token(token)
        assert payload.sub == user_id
        assert payload.type == "refresh"
        assert payload.iss == "stonks-backend"

    def test_expired_access_token(self, settings: Settings, user_id: str) -> None:
        """Token with -1 minute TTL should be rejected."""
        settings.jwt_access_token_expire_minutes = -1
        jwt_svc = JWTService.from_settings(settings)
        token = jwt_svc.create_access_token(user_id, "test@example.com")
        with pytest.raises(ValueError, match="Invalid token"):
            jwt_svc.decode_access_token(token)

    def test_expired_refresh_token(self, settings: Settings, user_id: str) -> None:
        """Token with -1 day TTL should be rejected."""
        settings.jwt_refresh_token_expire_days = -1
        jwt_svc = JWTService.from_settings(settings)
        token = jwt_svc.create_refresh_token(user_id)
        with pytest.raises(ValueError, match="Invalid token"):
            jwt_svc.decode_refresh_token(token)

    def test_wrong_secret(self, user_id: str) -> None:
        s1 = Settings(jwt_secret="secret-one-32-chars-long-enough!")
        s2 = Settings(jwt_secret="secret-two-32-chars-long-enough!")
        jwt1 = JWTService.from_settings(s1)
        jwt2 = JWTService.from_settings(s2)

        token = jwt1.create_access_token(user_id, "test@stnks.com")
        with pytest.raises(ValueError, match="Invalid token"):
            jwt2.decode_access_token(token)

    def test_wrong_issuer(self, user_id: str) -> None:
        s1 = Settings(jwt_secret="test-secret-at-least-32-chars!!", jwt_issuer="issuer-a")
        s2 = Settings(jwt_secret="test-secret-at-least-32-chars!!", jwt_issuer="issuer-b")
        jwt1 = JWTService.from_settings(s1)
        jwt2 = JWTService.from_settings(s2)

        token = jwt1.create_access_token(user_id, "email@test.com")
        with pytest.raises(ValueError, match="Invalid token"):
            jwt2.decode_access_token(token)

    def test_refresh_token_used_as_access(self, jwt_svc: JWTService, user_id: str) -> None:
        refresh = jwt_svc.create_refresh_token(user_id)
        with pytest.raises(ValueError, match="not an access token"):
            jwt_svc.decode_access_token(refresh)

    def test_access_token_used_as_refresh(self, jwt_svc: JWTService, user_id: str) -> None:
        access = jwt_svc.create_access_token(user_id, "test@stonks.com")
        with pytest.raises(ValueError, match="not a refresh token"):
            jwt_svc.decode_refresh_token(access)

    def test_garbage_token(self, jwt_svc: JWTService) -> None:
        with pytest.raises(ValueError, match="Invalid token"):
            jwt_svc.decode_access_token("not.a.jwt")

    def test_token_has_exp_and_iat(self, jwt_svc: JWTService, user_id: str) -> None:
        token = jwt_svc.create_access_token(user_id, "test@stonks.com")
        payload = jwt_svc.decode_access_token(token)
        now = int(time.time())
        assert payload.iat <= now
        assert payload.exp > now
        assert payload.exp > payload.iat
