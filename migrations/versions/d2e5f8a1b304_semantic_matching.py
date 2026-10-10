from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "d2e5f8a1b304"
down_revision = "a1c4e8f2d907"
branch_labels = None
depends_on = None


def upgrade():
    postgres = op.get_bind().dialect.name == "postgresql"
    for table in ("candidate_profiles", "vacancies"):
        op.add_column(table, sa.Column("embedding", Vector(1024) if postgres else sa.JSON(), nullable=True))
        op.add_column(table, sa.Column("embedding_text", sa.Text(), nullable=True))
        op.add_column(table, sa.Column("embedding_model", sa.String(255), nullable=True))
    op.add_column("candidate_profiles", sa.Column("resume_text", sa.Text(), nullable=True))
    op.add_column("candidate_profiles", sa.Column("assessment_text", sa.Text(), nullable=True))


def downgrade():
    for field in ("assessment_text", "resume_text"):
        op.drop_column("candidate_profiles", field)
    for table in ("vacancies", "candidate_profiles"):
        for field in ("embedding_model", "embedding_text", "embedding"):
            op.drop_column(table, field)
