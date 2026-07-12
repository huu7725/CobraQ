"""initial_schema — CobraQ v4 map and quiz tables

Revision ID: 001
Revises:
Create Date: 2026-07-11

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(20), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('grade_level', sa.String(50), nullable=True),
        sa.Column('school_name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Historical events
    op.create_table(
        'historical_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('short_description', sa.Text(), nullable=False),
        sa.Column('full_content', sa.Text(), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=True),
        sa.Column('year_range', sa.String(50), nullable=True),
        sa.Column('period', sa.String(100), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('region', sa.String(100), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=True),
        sa.Column('difficulty_level', sa.Integer(), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('image_caption', sa.Text(), nullable=True),
        sa.Column('video_url', sa.Text(), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('related_event_ids', sa.Text(), nullable=True),
        sa.Column('is_featured', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_historical_events_slug', 'historical_events', ['slug'], unique=True)

    # User map progress
    op.create_table(
        'user_map_progress',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('view_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('scrolled_to_content', sa.Boolean(), nullable=True),
        sa.Column('watched_video', sa.Boolean(), nullable=True),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('viewed_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['event_id'], ['historical_events.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'event_id', 'session_id', name='uq_user_event_session'),
    )
    op.create_index('ix_user_map_progress_user_id', 'user_map_progress', ['user_id'])
    op.create_index('ix_user_map_progress_event_id', 'user_map_progress', ['event_id'])
    op.create_index('ix_user_map_progress_session_id', 'user_map_progress', ['session_id'])

    # Map quiz sessions
    op.create_table(
        'map_quiz_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_token', sa.String(100), nullable=False),
        sa.Column('source_type', sa.String(20), nullable=True),
        sa.Column('source_scope', sa.String(500), nullable=True),
        sa.Column('num_questions_requested', sa.Integer(), nullable=False),
        sa.Column('num_questions_generated', sa.Integer(), nullable=True),
        sa.Column('time_limit_minutes', sa.Integer(), nullable=True),
        sa.Column('difficulty_level', sa.Integer(), nullable=True),
        sa.Column('context_event_ids', sa.String(1000), nullable=False),
        sa.Column('ai_model_used', sa.String(100), nullable=True),
        sa.Column('ai_prompt_tokens', sa.Integer(), nullable=True),
        sa.Column('ai_completion_tokens', sa.Integer(), nullable=True),
        sa.Column('generation_time_ms', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('time_taken_seconds', sa.Integer(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('total_questions', sa.Integer(), nullable=True),
        sa.Column('percentage', sa.Float(), nullable=True),
        sa.Column('is_completed', sa.Boolean(), nullable=True),
        sa.Column('is_submitted', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_map_quiz_sessions_user_id', 'map_quiz_sessions', ['user_id'])
    op.create_index('ix_map_quiz_sessions_session_token', 'map_quiz_sessions', ['session_token'], unique=True)

    # Map quiz questions
    op.create_table(
        'map_quiz_questions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('question_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(20), nullable=True),
        sa.Column('difficulty', sa.Integer(), nullable=True),
        sa.Column('choices', sa.Text(), nullable=False),
        sa.Column('correct_answer', sa.String(10), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('source_event_id', sa.Integer(), nullable=True),
        sa.Column('question_order', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['map_quiz_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_event_id'], ['historical_events.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_map_quiz_questions_session_id', 'map_quiz_questions', ['session_id'])
    op.create_index('ix_map_quiz_questions_source_event_id', 'map_quiz_questions', ['source_event_id'])

    # Map quiz answers
    op.create_table(
        'map_quiz_answers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('selected_choice', sa.String(10), nullable=True),
        sa.Column('is_correct', sa.Boolean(), nullable=True),
        sa.Column('time_spent_seconds', sa.Integer(), nullable=True),
        sa.Column('answered_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['map_quiz_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['map_quiz_questions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'question_id', name='uq_session_question_answer'),
    )
    op.create_index('ix_map_quiz_answers_session_id', 'map_quiz_answers', ['session_id'])
    op.create_index('ix_map_quiz_answers_user_id', 'map_quiz_answers', ['user_id'])

    # Quiz history
    op.create_table(
        'quiz_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('quiz_type', sa.String(20), nullable=False),
        sa.Column('quiz_session_id', sa.Integer(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('total_questions', sa.Integer(), nullable=False),
        sa.Column('percentage', sa.Float(), nullable=False),
        sa.Column('time_taken_seconds', sa.Integer(), nullable=True),
        sa.Column('difficulty_level', sa.Integer(), nullable=True),
        sa.Column('tags', sa.String(500), nullable=True),
        sa.Column('completed_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_quiz_history_user_id', 'quiz_history', ['user_id'])
    op.create_index('ix_quiz_history_quiz_type', 'quiz_history', ['quiz_type'])
    op.create_index('ix_quiz_history_completed_at', 'quiz_history', ['completed_at'])


def downgrade() -> None:
    op.drop_table('quiz_history')
    op.drop_table('map_quiz_answers')
    op.drop_table('map_quiz_questions')
    op.drop_table('map_quiz_sessions')
    op.drop_table('user_map_progress')
    op.drop_table('historical_events')
    op.drop_table('users')
