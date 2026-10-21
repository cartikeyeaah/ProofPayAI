"""Add isolated application schema. Does not modify legacy public tables."""
from alembic import op
from database.migrations.schema_v1 import metadata
revision = '0001_application'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.execute('CREATE SCHEMA IF NOT EXISTS proofpay')
    metadata.create_all(op.get_bind())

def downgrade():
    raise RuntimeError('Destructive downgrade is intentionally disabled; restore a reviewed backup instead.')
