def test_core_imports():
    from app.core import config, exceptions, logging

    assert config
    assert logging
    assert exceptions


def test_domain_imports():
    from app.domain import clinica, notificaciones, pagos, personas, turnos

    assert turnos
    assert pagos
    assert notificaciones
    assert clinica
    assert personas


def test_infrastructure_imports():
    from app.infrastructure import db, integrations, queue

    assert db
    assert queue
    assert integrations


def test_api_imports():
    from app.api import internal, public, webhooks

    assert public
    assert internal
    assert webhooks


def test_main_app_imports():
    from app.main import app

    assert app is not None
    assert app.title == "Turnos Odontología API"
