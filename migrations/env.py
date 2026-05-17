import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger(__name__)


def get_engine():
    return current_app.extensions['migrate'].db.engine


def get_engine_url():
    return get_engine().url.render_as_string(hide_password=False).replace('%', '%%')


config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=get_metadata(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []

    conf_args = {
        'connection': get_engine().connect(),
        'target_metadata': get_metadata(),
        'process_revision_directives': process_revision_directives,
    }

    with conf_args['connection'] as connection:
        context.configure(**conf_args)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
