from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = ("b8c3d5e7f901", "d4b8f2c701e5")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("regular_task_submissions")
    op.add_column("regular_tasks", sa.Column("vacancy_id", sa.Integer(), nullable=True))
    op.create_index("ix_regular_tasks_vacancy_id", "regular_tasks", ["vacancy_id"])

    op.create_table(
        "regular_task_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("application_id", sa.Integer(), sa.ForeignKey("applications.id"), nullable=False, index=True),
        sa.Column("candidate_profile_id", sa.Integer(), sa.ForeignKey("candidate_profiles.id"), nullable=False, index=True),
        sa.Column("vacancy_id", sa.Integer(), sa.ForeignKey("vacancies.id"), nullable=False, index=True),
        sa.Column("task_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_score", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending", index=True),
        sa.Column("forced_finish", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("application_id", name="uq_regular_session_application"),
    )
    op.create_table(
        "regular_task_answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("regular_task_sessions.id"), nullable=False, index=True),
        sa.Column("regular_task_id", sa.Integer(), sa.ForeignKey("regular_tasks.id"), nullable=False, index=True),
        sa.Column("option_index", sa.Integer(), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("session_id", "regular_task_id", name="uq_regular_answer_task"),
    )


def downgrade() -> None:
    op.drop_table("regular_task_answers")
    op.drop_table("regular_task_sessions")
    op.drop_index("ix_regular_tasks_vacancy_id", table_name="regular_tasks")
    op.drop_column("regular_tasks", "vacancy_id")
    op.create_table(
        "regular_task_submissions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("regular_task_id", sa.Integer(), sa.ForeignKey("regular_tasks.id"), nullable=False, index=True),
        sa.Column("candidate_profile_id", sa.Integer(), sa.ForeignKey("candidate_profiles.id"), nullable=False, index=True),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("regular_task_id", "candidate_profile_id", name="uq_regular_submission"),
    )
