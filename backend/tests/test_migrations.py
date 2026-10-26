import os, subprocess, sys

def test_alembic_upgrade_matches_models(tmp_path):
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{tmp_path}/m.db", "APP_SCHEDULER": "0"}
    here = os.path.dirname(os.path.dirname(__file__))
    alembic = [sys.executable, "-m", "alembic"]
    assert subprocess.run(alembic + ["upgrade", "head"], cwd=here, env=env, capture_output=True).returncode == 0
    chk = subprocess.run(alembic + ["check"], cwd=here, env=env, capture_output=True, text=True)
    assert chk.returncode == 0, chk.stdout + chk.stderr
