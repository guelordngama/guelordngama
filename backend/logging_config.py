"""Configuration de la journalisation SafeCity."""
import logging
import sys


def setup_logging(level="INFO"):
    logger = logging.getLogger("safecity")
    if logger.handlers:  # évite la double configuration
        return logger
    logger.setLevel(getattr(logging, level, logging.INFO))
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger
