from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '1b60da01b43c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('specialization', sa.String(length=64), nullable=False),
    sa.Column('grade', sa.String(length=16), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('specialization', 'grade', name='uq_category_spec_grade')
    )
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_categories_grade'), ['grade'], unique=False)
        batch_op.create_index(batch_op.f('ix_categories_specialization'), ['specialization'], unique=False)

    op.create_table('concepts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('domain', sa.String(length=64), nullable=False),
    sa.Column('grade', sa.String(length=16), nullable=False),
    sa.Column('difficulty_params', sa.JSON(), nullable=False),
    sa.Column('task_format', sa.String(length=32), nullable=False),
    sa.Column('question_template', sa.String(length=2000), nullable=False),
    sa.Column('correct_answer', sa.String(length=1000), nullable=False),
    sa.Column('distractors', sa.JSON(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name', 'grade', name='uq_concept_name_grade')
    )
    with op.batch_alter_table('concepts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_concepts_domain'), ['domain'], unique=False)
        batch_op.create_index(batch_op.f('ix_concepts_grade'), ['grade'], unique=False)

    op.create_table('task_contexts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(length=128), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('label')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('consent_accepted', sa.Boolean(), nullable=False),
    sa.Column('pvn_id', sa.String(length=64), nullable=True),
    sa.Column('is_email_confirmed', sa.Boolean(), nullable=False),
    sa.Column('email_confirmation_token', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_pvn_id'), ['pvn_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_role'), ['role'], unique=False)

    op.create_table('candidate_profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('contacts', sa.JSON(), nullable=False),
    sa.Column('stack', sa.JSON(), nullable=False),
    sa.Column('years_of_experience', sa.Float(), nullable=False),
    sa.Column('soft_skills', sa.JSON(), nullable=False),
    sa.Column('specialization', sa.String(length=64), nullable=False),
    sa.Column('grade', sa.String(length=16), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('grade_changed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_visible', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_candidate_profiles_user_id'), ['user_id'], unique=True)

    op.create_table('employer_profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.String(length=2000), nullable=False),
    sa.Column('contacts', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('employer_profiles', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_employer_profiles_user_id'), ['user_id'], unique=True)

    op.create_table('pvn_achievements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('candidate_profile_id', sa.Integer(), nullable=False),
    sa.Column('achievement_type', sa.String(length=64), nullable=False),
    sa.Column('level', sa.String(length=32), nullable=False),
    sa.Column('achieved_at', sa.Date(), nullable=False),
    sa.Column('score', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('pvn_achievements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pvn_achievements_candidate_profile_id'), ['candidate_profile_id'], unique=False)

    op.create_table('invitations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employer_profile_id', sa.Integer(), nullable=False),
    sa.Column('candidate_profile_id', sa.Integer(), nullable=False),
    sa.Column('message', sa.String(length=4000), nullable=False),
    sa.Column('salary_from', sa.Integer(), nullable=False),
    sa.Column('salary_to', sa.Integer(), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('contact_method', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ),
    sa.ForeignKeyConstraint(['employer_profile_id'], ['employer_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('invitations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_invitations_candidate_profile_id'), ['candidate_profile_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_invitations_employer_profile_id'), ['employer_profile_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_invitations_status'), ['status'], unique=False)

    op.create_table('regular_tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employer_profile_id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=True),
    sa.Column('statement', sa.String(length=4000), nullable=False),
    sa.Column('task_format', sa.String(length=32), nullable=False),
    sa.Column('options', sa.JSON(), nullable=False),
    sa.Column('reference_answer', sa.JSON(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
    sa.ForeignKeyConstraint(['employer_profile_id'], ['employer_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('regular_tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_regular_tasks_employer_profile_id'), ['employer_profile_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_regular_tasks_is_active'), ['is_active'], unique=False)

    op.create_table('test_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('candidate_profile_id', sa.Integer(), nullable=False),
    sa.Column('grade', sa.String(length=16), nullable=False),
    sa.Column('task_count', sa.Integer(), nullable=False),
    sa.Column('correct_count', sa.Integer(), nullable=False),
    sa.Column('result_score', sa.Integer(), nullable=True),
    sa.Column('verdict', sa.String(length=32), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('test_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_test_sessions_candidate_profile_id'), ['candidate_profile_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_test_sessions_status'), ['status'], unique=False)

    op.create_table('vacancies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employer_profile_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.String(length=4000), nullable=False),
    sa.Column('stack', sa.JSON(), nullable=False),
    sa.Column('specialization', sa.String(length=64), nullable=False),
    sa.Column('grade', sa.String(length=16), nullable=False),
    sa.Column('salary_from', sa.Integer(), nullable=False),
    sa.Column('salary_to', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['employer_profile_id'], ['employer_profiles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('vacancies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_vacancies_employer_profile_id'), ['employer_profile_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_vacancies_status'), ['status'], unique=False)

    op.create_table('applications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('vacancy_id', sa.Integer(), nullable=False),
    sa.Column('candidate_profile_id', sa.Integer(), nullable=False),
    sa.Column('message', sa.String(length=4000), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ),
    sa.ForeignKeyConstraint(['vacancy_id'], ['vacancies.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_applications_candidate_profile_id'), ['candidate_profile_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_applications_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_applications_vacancy_id'), ['vacancy_id'], unique=False)

    op.create_table('regular_task_submissions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('regular_task_id', sa.Integer(), nullable=False),
    sa.Column('candidate_profile_id', sa.Integer(), nullable=False),
    sa.Column('is_correct', sa.Boolean(), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ),
    sa.ForeignKeyConstraint(['regular_task_id'], ['regular_tasks.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('regular_task_id', 'candidate_profile_id', name='uq_regular_submission')
    )
    with op.batch_alter_table('regular_task_submissions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_regular_task_submissions_candidate_profile_id'), ['candidate_profile_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_regular_task_submissions_regular_task_id'), ['regular_task_id'], unique=False)

    op.create_table('tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('concept_id', sa.Integer(), nullable=False),
    sa.Column('grade', sa.String(length=16), nullable=False),
    sa.Column('statement', sa.String(length=4000), nullable=False),
    sa.Column('task_format', sa.String(length=32), nullable=False),
    sa.Column('options', sa.JSON(), nullable=False),
    sa.Column('reference_answer', sa.JSON(), nullable=False),
    sa.Column('candidate_profile_id', sa.Integer(), nullable=True),
    sa.Column('session_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['candidate_profile_id'], ['candidate_profiles.id'], ),
    sa.ForeignKeyConstraint(['concept_id'], ['concepts.id'], ),
    sa.ForeignKeyConstraint(['session_id'], ['test_sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tasks_concept_id'), ['concept_id'], unique=False)

def downgrade() -> None:
    with op.batch_alter_table('tasks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tasks_concept_id'))

    op.drop_table('tasks')
    with op.batch_alter_table('regular_task_submissions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_regular_task_submissions_regular_task_id'))
        batch_op.drop_index(batch_op.f('ix_regular_task_submissions_candidate_profile_id'))

    op.drop_table('regular_task_submissions')
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_applications_vacancy_id'))
        batch_op.drop_index(batch_op.f('ix_applications_status'))
        batch_op.drop_index(batch_op.f('ix_applications_candidate_profile_id'))

    op.drop_table('applications')
    with op.batch_alter_table('vacancies', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vacancies_status'))
        batch_op.drop_index(batch_op.f('ix_vacancies_employer_profile_id'))

    op.drop_table('vacancies')
    with op.batch_alter_table('test_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_test_sessions_status'))
        batch_op.drop_index(batch_op.f('ix_test_sessions_candidate_profile_id'))

    op.drop_table('test_sessions')
    with op.batch_alter_table('regular_tasks', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_regular_tasks_is_active'))
        batch_op.drop_index(batch_op.f('ix_regular_tasks_employer_profile_id'))

    op.drop_table('regular_tasks')
    with op.batch_alter_table('invitations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_invitations_status'))
        batch_op.drop_index(batch_op.f('ix_invitations_employer_profile_id'))
        batch_op.drop_index(batch_op.f('ix_invitations_candidate_profile_id'))

    op.drop_table('invitations')
    with op.batch_alter_table('pvn_achievements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pvn_achievements_candidate_profile_id'))

    op.drop_table('pvn_achievements')
    with op.batch_alter_table('employer_profiles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_employer_profiles_user_id'))

    op.drop_table('employer_profiles')
    with op.batch_alter_table('candidate_profiles', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_candidate_profiles_user_id'))

    op.drop_table('candidate_profiles')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_role'))
        batch_op.drop_index(batch_op.f('ix_users_pvn_id'))
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
    op.drop_table('task_contexts')
    with op.batch_alter_table('concepts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_concepts_grade'))
        batch_op.drop_index(batch_op.f('ix_concepts_domain'))

    op.drop_table('concepts')
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_categories_specialization'))
        batch_op.drop_index(batch_op.f('ix_categories_grade'))

    op.drop_table('categories')
