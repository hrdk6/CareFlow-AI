"""Test fixtures: a real PostgreSQL + pgvector database seeded with a small synthetic hospital.

Defaults keep the suite fast and offline: hashing embeddings, no cross-encoder, extractive LLM mode.
Tests needing downloaded models are marked `models`; live-LLM tests are marked `llm`.
Point CAREFLOW_TEST_DATABASE_URL at a disposable database (default: local dev cluster on :5433).
"""
import os
import tempfile
from pathlib import Path

os.environ.update({
    "CAREFLOW_ENVIRONMENT": "test",
    "CAREFLOW_DATABASE_URL": os.environ.get(
        "CAREFLOW_TEST_DATABASE_URL", "postgresql+psycopg://careflow:careflow@127.0.0.1:5433/careflow_test"),
    "CAREFLOW_JWT_SECRET": "test-secret-" + "x" * 40,
    "CAREFLOW_EMBEDDING_PROVIDER": "hashing",
    "CAREFLOW_RERANKER_PROVIDER": "none",
    "CAREFLOW_LLM_PROVIDER": "extractive",
    # backend/.env is also read by Settings, so pin every behaviour-affecting option explicitly.
    "CAREFLOW_LLM_TOOL_CALLING": "auto",
    "CAREFLOW_INJECTION_POLICY": "quarantine",
    "CAREFLOW_LLM_CONTEXT_BUDGET_CHARS": "12000",
    "CAREFLOW_STORAGE_DIR": tempfile.mkdtemp(prefix="careflow-test-"),
    "CAREFLOW_LOG_LEVEL": "WARNING",
})

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.ratelimit import login_limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_engine, get_session_factory  # noqa: E402
from app.models import Patient, User  # noqa: E402

PASSWORD = "Test-Password-123"
BACKEND = Path(__file__).resolve().parents[1]
EMAILS = {"admin": "admin@careflow.demo", "doctor": "dr.rao@careflow.demo", "cardio": "dr.mensah@careflow.demo",
          "nurse": "nurse.kim@careflow.demo", "reception": "reception@careflow.demo"}


def pytest_configure(config):
    for marker in ("models", "llm"):
        config.addinivalue_line("markers", f"{marker}: see conftest")


@pytest.fixture(scope="session", autouse=True)
def database():
    engine = get_engine()
    # The fixture drops every table: refuse to touch anything that is not clearly a test database.
    if not (engine.url.database or "").endswith("_test"):
        pytest.exit(f"Refusing to run: '{engine.url.database}' is not a *_test database", returncode=2)
    with engine.begin() as conn:
        Base.metadata.drop_all(conn)
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")  # the real migration, not create_all

    from app.ml.registry import sync_registry
    from app.ml.similarity import rebuild_all_representations
    from app.rag.demo_corpus import ingest_demo_corpus
    from app.seed.generator import HospitalGenerator

    Session = get_session_factory()
    with Session() as db:
        HospitalGenerator(db, seed=7, n_patients=60, demo_password=PASSWORD).run()
        db.commit()
        sync_registry(db)
        rebuild_all_representations(db)
        db.commit()
    with Session() as db:
        result = ingest_demo_corpus(db)
        assert not result["failed"], result
    yield


@pytest.fixture
def db():
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="session")
def client():
    from app.main import app

    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_limiter():
    login_limiter._events.clear()
    yield


@pytest.fixture(scope="session")
def tokens(client):
    out = {}
    for role, email in EMAILS.items():
        r = client.post("/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        out[role] = r.json()["access_token"]
    login_limiter._events.clear()
    client.cookies.clear()  # tests authenticate explicitly with bearer headers
    return out


@pytest.fixture
def auth(tokens):
    def headers(role: str) -> dict:
        return {"Authorization": f"Bearer {tokens[role]}"}

    return headers


@pytest.fixture
def demo_patient(db) -> Patient:
    return db.scalar(select(Patient).where(Patient.mrn == "P1024"))


@pytest.fixture
def users(db) -> dict[str, User]:
    return {role: db.scalar(select(User).where(User.email == email)) for role, email in EMAILS.items()}


@pytest.fixture
def restricted_patient(db, users) -> Patient:
    """A patient Dr. Rao (General Medicine) is NOT allowed to see."""
    from app.auth.access import AccessPolicy

    visible = AccessPolicy(db, users["doctor"]).accessible_patient_ids()
    patient = db.scalar(select(Patient).where(Patient.id.not_in(visible)).order_by(Patient.id).limit(1))
    assert patient is not None
    return patient
