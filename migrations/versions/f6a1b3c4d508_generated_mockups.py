from alembic import op
import sqlalchemy as sa

revision = "f6a1b3c4d508"
down_revision = "e4f7a9c2d601"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("designer_audits", sa.Column("reference_defects", sa.JSON(), server_default="[]", nullable=False))


def downgrade():
    op.drop_column("designer_audits", "reference_defects")
