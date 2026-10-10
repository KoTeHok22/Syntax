from alembic import op
import sqlalchemy as sa

revision = "b8c3d5e7f901"
down_revision = "a7b2c9d4e610"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("candidate_profiles", sa.Column("grade_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("test_sessions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("test_sessions", "expires_at")
    op.drop_column("candidate_profiles", "grade_confirmed_at")
