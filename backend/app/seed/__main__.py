"""Seed the database with the synthetic hospital.

    uv run python -m app.seed [--reset] [--if-empty] [--patients 240] [--seed 7] [--with-documents]

The demo password comes from CAREFLOW_DEMO_PASSWORD (see .env.example). All data is synthetic.
"""
import argparse
import os
import sys
import time

from sqlalchemy import func, select, text

from app.db.session import get_session_factory
from app.models import Patient
from app.seed.generator import HospitalGenerator

TABLES_IN_DELETE_ORDER = [
    "imaging_reports", "imaging_studies", "vital_signs", "ai_drafts", "ai_query_traces", "audit_logs", "ml_predictions", "patient_embeddings", "model_versions", "lab_reports",
    "document_chunks", "documents", "prescriptions", "diagnoses", "medical_records", "admissions",
    "appointments", "care_assignments", "users", "patients", "doctors", "medications", "role_permissions",
    "permissions", "roles", "departments",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete all existing data first")
    ap.add_argument("--if-empty", action="store_true", help="do nothing if patients already exist")
    ap.add_argument("--patients", type=int, default=240)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--with-documents", action="store_true", help="also ingest the demo knowledge base")
    args = ap.parse_args()

    password = os.environ.get("CAREFLOW_DEMO_PASSWORD", "CareFlow-Demo-2026")
    Session = get_session_factory()
    with Session() as db:
        existing = db.scalar(select(func.count()).select_from(Patient))
        if existing and args.if_empty:
            # Features added after this database was seeded get their synthetic data once (idempotent).
            from app.seed.imaging import seed_imaging
            from app.seed.vitals import seed_vitals

            added = seed_vitals(db, seed=args.seed)
            films = seed_imaging(db, seed=args.seed)
            db.commit()
            extra = [f"{added} bedside observations for current inpatients" if added else "",
                     f"{films} radiology studies" if films else ""]
            extra = [e for e in extra if e]
            print(f"Database already seeded ({existing} patients) - skipping"
                  + (f"; added {' and '.join(extra)}." if extra else "."))
            return
        if existing and not args.reset:
            sys.exit("Database is not empty. Re-run with --reset to wipe it or --if-empty to skip.")
        if args.reset:
            db.execute(text(f"TRUNCATE {', '.join(TABLES_IN_DELETE_ORDER)} RESTART IDENTITY CASCADE"))
            db.commit()
        t0 = time.perf_counter()
        stats = HospitalGenerator(db, seed=args.seed, n_patients=args.patients, demo_password=password).run()
        db.commit()
        print(f"Seeded {stats} in {time.perf_counter() - t0:.1f}s")

    from app.ml.registry import sync_registry
    from app.ml.similarity import rebuild_all_representations

    with Session() as db:
        sync_registry(db)
        n = rebuild_all_representations(db)
        db.commit()
        print(f"Registered models; built {n} patient similarity representations")

    # After the registry, so a scored film can point at the model version that scored it.
    from app.seed.imaging import seed_imaging

    with Session() as db:
        films = seed_imaging(db, seed=args.seed)
        db.commit()
        print(f"Ingested {films} de-identified demo radiographs" if films
              else "No demo radiographs found (run: python -m ml.data.build_demo_studies)")

    if args.with_documents:
        from app.rag.demo_corpus import ingest_demo_corpus

        with Session() as db:
            print(ingest_demo_corpus(db))
    print("Demo accounts (password from CAREFLOW_DEMO_PASSWORD): admin@careflow.demo, dr.rao@careflow.demo, "
          "dr.mensah@careflow.demo, nurse.kim@careflow.demo, reception@careflow.demo")


if __name__ == "__main__":
    main()
