import os
from alembic import context
from sqlalchemy import create_engine
from backend.db.models import metadata
url = os.environ['DATABASE_URL']
if not url.startswith('postgresql+psycopg://'):
    raise RuntimeError('DATABASE_URL must use postgresql+psycopg://')
if context.is_offline_mode():
    context.configure(url=url, target_metadata=metadata, literal_binds=True, version_table='proofpay_alembic_version', include_schemas=True)
    with context.begin_transaction(): context.run_migrations()
else:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata, version_table='proofpay_alembic_version', include_schemas=True,
                          include_name=lambda name, type_, parent: name == 'proofpay' if type_ == 'schema' else parent.get('schema_name', 'proofpay') == 'proofpay')
        with context.begin_transaction(): context.run_migrations()
