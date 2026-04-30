import threading
import time
import logging
import sys
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


def _wake_supabase_once():
    try:
        from utils import supabase
        resp = supabase.table("keepalive").select("id").limit(1).execute()
        if hasattr(resp, "error") and resp.error:
            logger.warning("Supabase wake returned error: %s", resp.error)
        else:
            logger.debug("Supabase wake successful")
    except Exception as e:
        logger.exception("Error while waking Supabase: %s", e)


def _run_loop(poll_seconds: int = 300):
    logger.info("Healthcheck thread started; waking Supabase every %s seconds", poll_seconds)
    while True:
        _wake_supabase_once()
        try:
            time.sleep(poll_seconds)
        except Exception:
            break


class HealthcheckConfig(AppConfig):
    name = 'healthcheck'
    verbose_name = 'Health Check'

    def ready(self):
        cmd_args = sys.argv
        skip_commands = ('makemigrations', 'migrate', 'collectstatic', 'shell', 'test')
        if any(c in cmd_args for c in skip_commands):
            return

        if os.environ.get('RUN_MAIN') == 'true' or 'runserver' in cmd_args or 'uwsgi' in cmd_args or 'gunicorn' in cmd_args:
            thread = threading.Thread(target=_run_loop, args=(300,), daemon=True)
            thread.start()
