import logging

__all__ = ['VERSION', 'logger', 'set_log_level']

VERSION = "0.3.3"

logger = logging.getLogger("cereja")
logger.setLevel(logging.ERROR)


def set_log_level(level: int):
    """
    Default log level is INFO

    CRITICAL = 50
    FATAL = CRITICAL
    ERROR = 40
    WARNING = 30
    WARN = WARNING
    INFO = 20
    DEBUG = 10
    NOTSET = 0
    """
    if not isinstance(level, int):
        raise TypeError(f"Value is'nt valid. {set_log_level.__doc__}")
    logger.setLevel(level)
    logger.info(f"Update log level to {level}")
