"""add genes table

Revision ID: a1b2c3d4e5f6
Revises: d82b4ac13731
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'd82b4ac13731'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'genes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('low', sa.Float(), nullable=True),
        sa.Column('high', sa.Float(), nullable=True),
        sa.Column('decimals', sa.Integer(), nullable=True),
        sa.Column('options', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('order', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_genes_id'), 'genes', ['id'], unique=False)
    op.create_index(op.f('ix_genes_project_id'), 'genes', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_genes_project_id'), table_name='genes')
    op.drop_index(op.f('ix_genes_id'), table_name='genes')
    op.drop_table('genes')
