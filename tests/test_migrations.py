from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


ROOT = Path(__file__).resolve().parents[1]


def migration_config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_integrations_migration_supports_sqlite_upgrade_and_downgrade(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    database_url = f"sqlite:///{tmp_path / 'migrations.db'}"
    config = migration_config(database_url)

    engine = create_engine(database_url)
    try:
        command.upgrade(config, "d2e5f8a1b304")
        previous = inspect(engine)
        previous_columns = {
            table: {column["name"] for column in previous.get_columns(table)}
            for table in previous.get_table_names()
        }
        previous_indexes = {
            table: previous.get_indexes(table) for table in ("users", "pvn_achievements")
        }
        previous_foreign_keys = previous.get_foreign_keys("pvn_achievements")
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users (id, email, password_hash, role, consent_accepted, is_email_confirmed) "
                "VALUES (1, 'candidate@example.test', 'hash', 'candidate', 1, 1), "
                "(2, 'other@example.test', 'hash', 'candidate', 1, 1)"
            ))
            connection.execute(text(
                "INSERT INTO candidate_profiles "
                "(id, user_id, full_name, contacts, stack, years_of_experience, soft_skills, specialization, is_visible) "
                "VALUES (1, 1, 'Existing candidate', '{}', '[]', 0, '[]', 'backend', 1)"
            ))
            connection.execute(text(
                "INSERT INTO pvn_achievements (id, candidate_profile_id, achievement_type, level, achieved_at, score) "
                "VALUES (1, 1, 'competition', 'regional', '2026-01-01', 80), "
                "(2, 1, 'competition', 'regional', '2026-02-01', 90)"
            ))

        command.upgrade(config, "e4f7a9c2d601")
        upgraded = inspect(engine)
        assert upgraded.get_unique_constraints("users") == [{
            "name": "uq_user_oidc_identity", "column_names": ["oidc_issuer", "oidc_subject"],
        }]
        assert upgraded.get_unique_constraints("pvn_achievements") == [{
            "name": "uq_pvn_external_achievement",
            "column_names": ["candidate_profile_id", "source_issuer", "external_id"],
        }]
        assert "designer_audits" in upgraded.get_table_names()
        for table, indexes in previous_indexes.items():
            assert upgraded.get_indexes(table) == indexes
        assert upgraded.get_foreign_keys("pvn_achievements") == previous_foreign_keys

        with engine.begin() as connection:
            assert connection.execute(text("SELECT email FROM users WHERE id = 1")).scalar_one() == "candidate@example.test"
            assert connection.execute(text("SELECT score FROM pvn_achievements WHERE id = 1")).scalar_one() == 80
            connection.execute(text("UPDATE users SET oidc_issuer = 'issuer', oidc_subject = 'subject' WHERE id = 1"))
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(text("UPDATE users SET oidc_issuer = 'issuer', oidc_subject = 'subject' WHERE id = 2"))
            connection.execute(text("UPDATE pvn_achievements SET source_issuer = 'issuer', external_id = 'event' WHERE id = 1"))
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(text("UPDATE pvn_achievements SET source_issuer = 'issuer', external_id = 'event' WHERE id = 2"))

        command.downgrade(config, "d2e5f8a1b304")
        downgraded = inspect(engine)
        assert set(downgraded.get_table_names()) == set(previous_columns)
        for table, columns in previous_columns.items():
            assert {column["name"] for column in downgraded.get_columns(table)} == columns
        for table, indexes in previous_indexes.items():
            assert downgraded.get_indexes(table) == indexes
            assert not downgraded.get_unique_constraints(table)
        assert downgraded.get_foreign_keys("pvn_achievements") == previous_foreign_keys
        with engine.begin() as connection:
            assert connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 2
            assert connection.execute(text("SELECT COUNT(*) FROM pvn_achievements")).scalar_one() == 2
            assert connection.execute(text("SELECT full_name FROM candidate_profiles")).scalar_one() == "Existing candidate"
        command.upgrade(config, "e4f7a9c2d601")
    finally:
        engine.dispose()


def test_interview_schedule_migration_adds_and_drops_columns(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    database_url = f"sqlite:///{tmp_path / 'interview-migration.db'}"
    config = migration_config(database_url)

    engine = create_engine(database_url)
    try:
        command.upgrade(config, "f6a1b3c4d508")
        before = {column["name"] for column in inspect(engine).get_columns("applications")}
        assert "interview_at" not in before

        command.upgrade(config, "a7b2c9d4e610")
        after = {column["name"] for column in inspect(engine).get_columns("applications")}
        assert {"interview_at", "interview_duration", "interview_format", "interview_link", "interview_address"}.issubset(after)

        command.downgrade(config, "f6a1b3c4d508")
        reverted = {column["name"] for column in inspect(engine).get_columns("applications")}
        assert "interview_at" not in reverted
    finally:
        engine.dispose()
