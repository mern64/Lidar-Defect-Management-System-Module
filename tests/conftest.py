import os

import pytest

from app import create_app
from app.extensions import db
from app.models import User


@pytest.fixture()
def app(tmp_path):
    db_file = tmp_path / "test.db"
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_file}",
            "DATABASE_URL": f"sqlite:///{db_file}",
            "SKIP_SCHEMA_EVOLUTION": True,
        }
    )

    with app.app_context():
        db.drop_all()
        db.create_all()

        dev = User(username="dev1", role="developer", is_active=True, is_available=True)
        dev.set_password("password123")
        db.session.add(dev)

        manager = User(username="manager1", role="manager", is_active=True, is_available=True)
        manager.set_password("password123")
        db.session.add(manager)

        dev_inactive = User(username="dev2", role="developer", is_active=False, is_available=True)
        dev_inactive.set_password("password123")
        db.session.add(dev_inactive)

        inspector = User(username="insp1", role="inspector", is_active=True, is_available=True)
        inspector.set_password("password123")
        db.session.add(inspector)

        db.session.commit()

    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def login_dev(client):
    response = client.post(
        "/login",
        data={"username": "dev1", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    return client


@pytest.fixture()
def login_manager(client):
    response = client.post(
        "/login",
        data={"username": "manager1", "password": "password123"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    return client
