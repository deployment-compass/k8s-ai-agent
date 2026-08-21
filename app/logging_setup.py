import logging

from app.config import Settings

APP_LOGGER_ROOT = "app"

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(settings: Settings) -> None:
    """Configure console logging for the application.

    Enabled: app loggers emit at AGENT_LOG_LEVEL.
    Disabled: app loggers drop to ERROR so failures still surface.
    """
    logging.basicConfig(format=LOG_FORMAT)

    root = logging.getLogger(APP_LOGGER_ROOT)
    if settings.agent_log_enabled:
        level_name = settings.agent_log_level.strip().upper()
        level = logging.getLevelName(level_name)
        if not isinstance(level, int):
            level = logging.INFO
        root.setLevel(level)
    else:
        root.setLevel(logging.ERROR)
