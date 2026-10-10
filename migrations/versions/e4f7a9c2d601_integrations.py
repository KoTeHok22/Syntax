from alembic import op
import sqlalchemy as sa

revision = "e4f7a9c2d601"
down_revision = "d2e5f8a1b304"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("oidc_issuer", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("oidc_subject", sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint("uq_user_oidc_identity", ["oidc_issuer", "oidc_subject"])
    op.add_column("candidate_profiles", sa.Column("portfolio_evidence", sa.JSON(), nullable=True))
    op.add_column("employer_profiles", sa.Column("ats_webhook_url", sa.String(length=2048), nullable=True))
    op.add_column("applications", sa.Column("ats_delivery_status", sa.String(length=16), server_default="pending", nullable=False))
    op.add_column("applications", sa.Column("ats_delivery_attempts", sa.Integer(), server_default="0", nullable=False))
    op.add_column("applications", sa.Column("ats_delivery_error", sa.String(length=255), nullable=True))
    op.add_column("applications", sa.Column("ats_delivered_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("pvn_achievements", schema=None) as batch_op:
        batch_op.add_column(sa.Column("source_issuer", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("external_id", sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint(
            "uq_pvn_external_achievement",
            ["candidate_profile_id", "source_issuer", "external_id"],
        )
    op.create_table(
        "designer_audits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("candidate_profile_id", sa.Integer(), sa.ForeignKey("candidate_profiles.id"), nullable=False, index=True),
        sa.Column("scenario", sa.String(length=4000), nullable=False),
        sa.Column("task_key", sa.String(length=64), nullable=True),
        sa.Column("screenshot_data_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("violations", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("evaluation", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("candidate_profile_id", "task_key", name="uq_designer_audit_task"),
    )


def downgrade():
    op.drop_table("designer_audits")
    with op.batch_alter_table("pvn_achievements", schema=None) as batch_op:
        batch_op.drop_constraint("uq_pvn_external_achievement", type_="unique")
        batch_op.drop_column("external_id")
        batch_op.drop_column("source_issuer")
    for field in ("ats_delivered_at", "ats_delivery_error", "ats_delivery_attempts", "ats_delivery_status"):
        op.drop_column("applications", field)
    op.drop_column("employer_profiles", "ats_webhook_url")
    op.drop_column("candidate_profiles", "portfolio_evidence")
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_constraint("uq_user_oidc_identity", type_="unique")
        batch_op.drop_column("oidc_subject")
        batch_op.drop_column("oidc_issuer")
