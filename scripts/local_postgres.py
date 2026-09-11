"""Run a local PostgreSQL 16 + pgvector for development WITHOUT Docker.

Uses the binaries bundled in the `pgserver` wheel (dev dependency). Docker users
should ignore this and use docker-compose instead.

    uv run --project backend python scripts/local_postgres.py start|stop|status
"""
import os
import subprocess
import sys
import time
from pathlib import Path

import pgserver
import psycopg

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "backend" / ".pgdata-local"
PORT = int(os.environ.get("CAREFLOW_LOCAL_PG_PORT", "5433"))
BIN = Path(pgserver.__file__).parent / "pginstall" / "bin"
DBS = ["careflow", "careflow_test"]


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(BIN / args[0]), *args[1:]], capture_output=True, text=True)


def start() -> None:
    if not (DATA / "PG_VERSION").exists():
        DATA.mkdir(parents=True, exist_ok=True)
        r = _run("initdb", "-D", str(DATA), "-U", "postgres", "--auth=trust", "-E", "UTF8")
        if r.returncode:
            sys.exit(r.stderr)
    if _run("pg_ctl", "-D", str(DATA), "status").returncode != 0:
        log = DATA / "server.log"
        subprocess.Popen(
            [str(BIN / "pg_ctl"), "-D", str(DATA), "-l", str(log), "-o", f"-p {PORT}", "start"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(40):
            time.sleep(0.5)
            if _run("pg_ctl", "-D", str(DATA), "status").returncode == 0:
                break
    with psycopg.connect(f"postgresql://postgres@127.0.0.1:{PORT}/postgres", autocommit=True) as c:
        if not c.execute("select 1 from pg_roles where rolname='careflow'").fetchone():
            c.execute("create role careflow login password 'careflow' createdb")
        for db in DBS:
            if not c.execute("select 1 from pg_database where datname=%s", (db,)).fetchone():
                c.execute(f'create database "{db}" owner careflow')
    for db in DBS:
        with psycopg.connect(f"postgresql://postgres@127.0.0.1:{PORT}/{db}", autocommit=True) as c:
            c.execute("create extension if not exists vector")
    print(f"PostgreSQL running: postgresql+psycopg://careflow:careflow@127.0.0.1:{PORT}/careflow")


def stop() -> None:
    print(_run("pg_ctl", "-D", str(DATA), "stop", "-m", "fast").stdout.strip())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "start"
    {"start": start, "stop": stop,
     "status": lambda: print(_run("pg_ctl", "-D", str(DATA), "status").stdout.strip())}[cmd]()
