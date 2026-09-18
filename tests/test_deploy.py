"""Deployment behaviour: binding, health and the password gate.

A Blitz carries cropped images of a copyrighted textbook, so an instance that
is reachable from the internet must not be reachable by everyone. These tests
exist so that stays true.
"""

import os

import pytest
import yaml
from fastapi.testclient import TestClient

from blitz.server import auth


@pytest.fixture
def client(tmp_path, monkeypatch):
    from blitz import config, db
    from blitz.corpus.sample import load_all_samples

    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "blitz.json").write_text('{"version": 1, "mode": "test"}')
    import shutil as _shutil

    import blitz.studydesign.loader as _loader

    _shutil.copytree(config.STUDY_DESIGN_DIR, tmp_path / "study-designs")
    monkeypatch.setattr(config, "USER_DESIGN_DIR", tmp_path / "study-designs")
    monkeypatch.setattr(_loader, "USER_DESIGN_DIR", tmp_path / "study-designs")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.sqlite3")
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.sqlite3")
    import blitz.server.app as server

    monkeypatch.setattr(server, "OUT_DIR", tmp_path / "out")
    (tmp_path / "out").mkdir(exist_ok=True)
    with db.session(tmp_path / "t.sqlite3") as conn:
        load_all_samples(conn)
    return TestClient(server.app)


class TestStartupGuard:
    def test_localhost_needs_no_password(self, monkeypatch):
        monkeypatch.delenv(auth.PASSWORD_ENV, raising=False)
        auth.check_startup("127.0.0.1")     # must not raise

    @pytest.mark.parametrize("host", ["0.0.0.0", "10.0.0.5", "::"])
    def test_a_public_bind_without_a_password_refuses(self, host, monkeypatch):
        monkeypatch.delenv(auth.PASSWORD_ENV, raising=False)
        with pytest.raises(auth.MissingPassword, match="Refusing to serve"):
            auth.check_startup(host)

    def test_the_refusal_says_how_to_fix_it(self, monkeypatch):
        monkeypatch.delenv(auth.PASSWORD_ENV, raising=False)
        with pytest.raises(auth.MissingPassword) as exc:
            auth.check_startup("0.0.0.0")
        assert auth.PASSWORD_ENV in str(exc.value)
        assert "copyrighted" in str(exc.value)

    def test_a_public_bind_with_a_password_is_fine(self, monkeypatch):
        monkeypatch.setenv(auth.PASSWORD_ENV, "correct horse battery staple")
        auth.check_startup("0.0.0.0")

    def test_whitespace_is_not_a_password(self, monkeypatch):
        monkeypatch.setenv(auth.PASSWORD_ENV, "   ")
        with pytest.raises(auth.MissingPassword):
            auth.check_startup("0.0.0.0")


class TestAuthGate:
    PASSWORD = "test-secret-123"

    @pytest.fixture(autouse=True)
    def _password(self, monkeypatch):
        monkeypatch.setenv(auth.PASSWORD_ENV, self.PASSWORD)

    @pytest.mark.parametrize("path", ["/", "/api/subjects", "/style.css"])
    def test_everything_is_gated(self, client, path):
        assert client.get(path).status_code == 401

    def test_the_health_probe_is_not_gated(self, client):
        """Render's health check has no credentials to offer."""
        res = client.get("/healthz")
        assert res.status_code == 200
        assert res.json()["ok"] is True

    def test_the_health_probe_reports_that_protection_is_on(self, client):
        assert client.get("/healthz").json()["protected"] is True

    def test_the_right_password_gets_in(self, client):
        assert client.get("/", auth=("anyone", self.PASSWORD)).status_code == 200

    @pytest.mark.parametrize("supplied", ["", "wrong", "test-secret-12",
                                          "test-secret-1234"])
    def test_a_wrong_password_does_not(self, client, supplied):
        assert client.get("/", auth=("x", supplied)).status_code == 401

    def test_the_username_is_ignored(self, client):
        for user in ("jack", "", "admin"):
            assert client.get("/", auth=(user, self.PASSWORD)).status_code == 200

    def test_a_challenge_is_sent(self, client):
        """Without this the browser never offers a login box."""
        res = client.get("/")
        assert "Basic" in res.headers.get("www-authenticate", "")

    @pytest.mark.parametrize("header", [
        "Bearer abc", "Basic", "Basic !!!not-base64!!!", "Basic " + "x" * 12,
    ])
    def test_malformed_credentials_are_rejected_not_crashed(self, client, header):
        res = client.get("/", headers={"Authorization": header})
        assert res.status_code == 401

    def test_generated_sheets_are_gated_too(self, client):
        """The crops are the copyrighted part; they must not be public."""
        body = {"subject_id": "physics",
                "kk_ids": ["physics-u3-aos1-kk01", "physics-u3-aos1-kk05"]}
        made = client.post("/api/generate", json=body,
                           auth=("x", self.PASSWORD)).json()
        assert client.get(made["url"]).status_code == 401
        assert client.get(made["url"], auth=("x", self.PASSWORD)).status_code == 200


class TestUnprotectedLocalInstance:
    def test_no_password_means_no_gate(self, client, monkeypatch):
        monkeypatch.delenv(auth.PASSWORD_ENV, raising=False)
        assert client.get("/").status_code == 200
        assert client.get("/healthz").json()["protected"] is False


@pytest.fixture
def service():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    return yaml.safe_load((root / "render.yaml").read_text())["services"][0]


class TestBlueprint:

    def test_it_starts_the_app(self, service):
        assert service["startCommand"] == "blitz serve"
        assert "pip install -e ." in service["buildCommand"]

    def test_the_health_check_points_at_a_real_route(self, service, client,
                                                     monkeypatch):
        monkeypatch.delenv(auth.PASSWORD_ENV, raising=False)
        assert client.get(service["healthCheckPath"]).status_code == 200

    def test_a_password_is_generated(self, service):
        env = {e["key"]: e for e in service["envVars"]}
        assert env[auth.PASSWORD_ENV].get("generateValue") is True, (
            "the blueprint must generate a password, or the instance will "
            "refuse to start")

    def test_state_lives_on_the_persistent_disk(self, service):
        env = {e["key"]: e.get("value") for e in service["envVars"]}
        assert env["BLITZ_ROOT"] == service["disk"]["mountPath"], (
            "BLITZ_ROOT must point at the disk, or the index is lost on deploy")

    def test_the_plan_can_actually_have_a_disk(self, service):
        assert service["plan"] != "free", (
            "the free plan has no persistent disk, so the index would not "
            "survive a restart")
