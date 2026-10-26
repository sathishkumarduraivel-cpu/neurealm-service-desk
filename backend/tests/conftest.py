import os, sys, pytest, warnings
warnings.filterwarnings("ignore")
os.environ["APP_SCHEDULER"] = "0"
os.environ["DATABASE_URL"] = "sqlite:///./test_servicedesk.db"
os.environ.pop("OPENAI_API_KEY", None); os.environ.pop("LLM_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
from app.main import app
from app import seed

@pytest.fixture(scope="session")
def client():
    seed.run(reset=True)
    with TestClient(app) as c:
        yield c
    if os.path.exists("test_servicedesk.db"): os.remove("test_servicedesk.db")

def _h(client, email, pw):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

@pytest.fixture(scope="session")
def admin(client): return _h(client, "admin@neurealm.com", "Admin@123")
@pytest.fixture(scope="session")
def agent(client): return _h(client, "agent@neurealm.com", "Agent@123")
@pytest.fixture(scope="session")
def user(client): return _h(client, "user@neurealm.com", "User@123")
