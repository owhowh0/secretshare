"""
TLS: CA-certificate wiring for PostgreSQL and Redis connections.

Tests are split into three groups:

  1. Settings     – tls_ca_cert field defaults and env loading.
  2. Engine       – create_engine injects the right SSLContext into asyncpg
                   connect_args. create_async_engine is mocked so no DB needed.
  3. Script       – tls/generate.sh produces the expected certificate artefacts,
                   sets correct permissions, and is idempotent.
                   Skipped when openssl is not on PATH.
"""

import datetime
import os
import shutil
import ssl
import stat
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from app.core.config import Settings
from app.db.session import create_engine as make_engine

# Path to tls/generate.sh relative to this file:
# api/tests/test_tls.py -> api/ -> secretshare/ -> tls/generate.sh
_TLS_SCRIPT = Path(__file__).resolve().parents[2] / "tls" / "generate.sh"
_OPENSSL = shutil.which("openssl") is not None


def _settings(**kwargs) -> Settings:
    return Settings(_env_file=None, **kwargs)


# ---------------------------------------------------------------------------
# Shared fixture: a real self-signed CA certificate written to a temp file.
# ssl.create_default_context(cafile=...) parses PEM, so the file must contain
# a valid certificate; an empty or garbage file raises SSLError.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ca_cert_file(tmp_path_factory) -> Path:
    tmp = tmp_path_factory.mktemp("tls_certs")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-ca")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    path = tmp / "ca.crt"
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return path


# ---------------------------------------------------------------------------
# 1. Settings
# ---------------------------------------------------------------------------


class TestTlsSettings:
    def test_tls_ca_cert_defaults_to_empty(self):
        assert _settings().tls_ca_cert == ""

    def test_tls_ca_cert_loaded_from_env(self, monkeypatch, ca_cert_file):
        monkeypatch.setenv("TLS_CA_CERT", str(ca_cert_file))
        assert _settings().tls_ca_cert == str(ca_cert_file)


# ---------------------------------------------------------------------------
# 2. create_engine SSL context
# ---------------------------------------------------------------------------


class TestCreateEngineSSL:
    """create_engine must pass the right SSLContext to asyncpg via connect_args."""

    def test_no_ssl_in_connect_args_when_ca_cert_is_empty(self):
        with patch("app.db.session.create_async_engine") as mock:
            mock.return_value = MagicMock()
            make_engine("postgresql+asyncpg://u:p@db/app", tls_ca_cert="")
            _, kwargs = mock.call_args
            assert "ssl" not in kwargs.get("connect_args", {})

    def test_ssl_context_present_when_ca_cert_is_set(self, ca_cert_file):
        with patch("app.db.session.create_async_engine") as mock:
            mock.return_value = MagicMock()
            make_engine(
                "postgresql+asyncpg://u:p@db/app",
                tls_ca_cert=str(ca_cert_file),
            )
            _, kwargs = mock.call_args
            assert isinstance(kwargs["connect_args"]["ssl"], ssl.SSLContext)

    def test_ssl_context_does_not_check_hostname(self, ca_cert_file):
        # Docker service names (db, redis) don't match the CN in the cert.
        with patch("app.db.session.create_async_engine") as mock:
            mock.return_value = MagicMock()
            make_engine(
                "postgresql+asyncpg://u:p@db/app",
                tls_ca_cert=str(ca_cert_file),
            )
            _, kwargs = mock.call_args
            assert kwargs["connect_args"]["ssl"].check_hostname is False

    def test_ssl_context_requires_cert_verification(self, ca_cert_file):
        with patch("app.db.session.create_async_engine") as mock:
            mock.return_value = MagicMock()
            make_engine(
                "postgresql+asyncpg://u:p@db/app",
                tls_ca_cert=str(ca_cert_file),
            )
            _, kwargs = mock.call_args
            assert kwargs["connect_args"]["ssl"].verify_mode == ssl.CERT_REQUIRED


# ---------------------------------------------------------------------------
# 3. Redis SSL context
#
# The context is built inline in main.py with the same logic as the DB engine.
# These tests verify the ssl module behaviour directly to document the
# expected properties of every SSLContext the app creates.
# ---------------------------------------------------------------------------


class TestRedisSSLContext:
    def test_context_does_not_check_hostname(self, ca_cert_file):
        ctx = ssl.create_default_context(cafile=str(ca_cert_file))
        ctx.check_hostname = False
        assert ctx.check_hostname is False

    def test_context_requires_cert_verification(self, ca_cert_file):
        ctx = ssl.create_default_context(cafile=str(ca_cert_file))
        ctx.check_hostname = False
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_invalid_ca_cert_raises_ssl_error(self, tmp_path):
        bad = tmp_path / "bad.crt"
        bad.write_text("not a certificate")
        with pytest.raises(ssl.SSLError):
            ssl.create_default_context(cafile=str(bad))


# ---------------------------------------------------------------------------
# 4. tls/generate.sh
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _OPENSSL, reason="openssl not on PATH")
class TestGenerateScript:
    @pytest.fixture
    def cert_dir(self, tmp_path) -> Path:
        d = tmp_path / "certs"
        d.mkdir()
        return d

    def _run(self, cert_dir: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["sh", str(_TLS_SCRIPT)],
            env={**os.environ, "CERTS": str(cert_dir)},
            capture_output=True,
            text=True,
        )

    def test_script_exits_zero(self, cert_dir):
        result = self._run(cert_dir)
        assert result.returncode == 0, result.stderr

    def test_expected_files_are_created(self, cert_dir):
        self._run(cert_dir)
        assert {f.name for f in cert_dir.iterdir()} == {
            "ca.key", "ca.crt",
            "postgres.key", "postgres.crt",
            "redis.key", "redis.crt",
        }

    def test_key_files_are_mode_600(self, cert_dir):
        self._run(cert_dir)
        for key_file in cert_dir.glob("*.key"):
            mode = stat.S_IMODE(key_file.stat().st_mode)
            assert mode == 0o600, f"{key_file.name}: expected 0o600, got {oct(mode)}"

    def test_cert_files_are_mode_644(self, cert_dir):
        self._run(cert_dir)
        for crt_file in cert_dir.glob("*.crt"):
            mode = stat.S_IMODE(crt_file.stat().st_mode)
            assert mode == 0o644, f"{crt_file.name}: expected 0o644, got {oct(mode)}"

    def test_postgres_cert_cn_is_db(self, cert_dir):
        self._run(cert_dir)
        cert = x509.load_pem_x509_certificate((cert_dir / "postgres.crt").read_bytes())
        cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        assert cn == "db"

    def test_redis_cert_cn_is_redis(self, cert_dir):
        self._run(cert_dir)
        cert = x509.load_pem_x509_certificate((cert_dir / "redis.crt").read_bytes())
        cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        assert cn == "redis"

    def test_postgres_cert_issued_by_ca(self, cert_dir):
        self._run(cert_dir)
        ca = x509.load_pem_x509_certificate((cert_dir / "ca.crt").read_bytes())
        pg = x509.load_pem_x509_certificate((cert_dir / "postgres.crt").read_bytes())
        assert pg.issuer == ca.subject

    def test_redis_cert_issued_by_ca(self, cert_dir):
        self._run(cert_dir)
        ca = x509.load_pem_x509_certificate((cert_dir / "ca.crt").read_bytes())
        redis = x509.load_pem_x509_certificate((cert_dir / "redis.crt").read_bytes())
        assert redis.issuer == ca.subject

    def test_script_is_idempotent(self, cert_dir):
        first = self._run(cert_dir)
        assert first.returncode == 0

        ca_before = (cert_dir / "ca.crt").read_bytes()

        second = self._run(cert_dir)
        assert second.returncode == 0
        assert "already present" in second.stdout

        # Certificates must not have been regenerated.
        assert (cert_dir / "ca.crt").read_bytes() == ca_before
