import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from brewing_api.platform.database import engine

pytestmark = pytest.mark.integration


def require_postgres() -> None:
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL integration database is not configured")


def test_phase2_constraints_and_append_only_inventory_ledger():
    require_postgres()
    now = datetime.now(UTC)
    user_id = uuid.uuid4()
    ingredient_id = uuid.uuid4()
    transaction_id = uuid.uuid4()
    with engine.connect() as connection, connection.begin():
        connection.execute(
            text(
                "INSERT INTO users (id, created_at, username, password_hash, is_active) "
                "VALUES (:id, :now, :username, 'integration-test-hash', true)"
            ),
            {"id": user_id, "now": now, "username": f"phase2-{user_id}"},
        )
        connection.execute(
            text(
                "INSERT INTO ingredients "
                "(id, created_at, owner_id, name, category, canonical_unit, attributes) "
                "VALUES (:id, :now, :owner, 'Golden Promise', 'FERMENTABLE', 'g', '{}')"
            ),
            {"id": ingredient_id, "now": now, "owner": user_id},
        )
        connection.execute(
            text(
                "INSERT INTO inventory_transactions "
                "(id, created_at, owner_id, ingredient_id, transaction_type, quantity, unit) "
                "VALUES (:id, :now, :owner, :ingredient, 'PURCHASE', 5000, 'g')"
            ),
            {
                "id": transaction_id,
                "now": now,
                "owner": user_id,
                "ingredient": ingredient_id,
            },
        )
        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError, match="append-only"):
            connection.execute(
                text("UPDATE inventory_transactions SET quantity = 1 WHERE id = :id"),
                {"id": transaction_id},
            )
        savepoint.rollback()

        savepoint = connection.begin_nested()
        with pytest.raises(DBAPIError):
            connection.execute(
                text(
                    "INSERT INTO inventory_transactions "
                    "(id, created_at, owner_id, ingredient_id, transaction_type, quantity, unit) "
                    "VALUES (:id, :now, :owner, :ingredient, 'PURCHASE', -1, 'g')"
                ),
                {
                    "id": uuid.uuid4(),
                    "now": now,
                    "owner": user_id,
                    "ingredient": ingredient_id,
                },
            )
        savepoint.rollback()
        connection.rollback()
