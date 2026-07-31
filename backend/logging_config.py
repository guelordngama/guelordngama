"""Configuration de la journalisation SafeCity."""
import logging
import sys


class _MuteTileAccessLog(logging.Filter):
    """Cache les journaux d'accès Werkzeug des tuiles de carte.

    Une seule vue de carte déclenche des dizaines de « GET /tiles/…/….png »
    qui inondent la console (et paraissent en rouge dans PyCharm car Werkzeug
    écrit sur stderr) alors que ce sont des requêtes normales — souvent des
    replis sur fond neutre lorsque ce poste n'a pas accès au CDN. On masque ces
    lignes-là uniquement ; les vraies erreurs Werkzeug (4xx/5xx, etc.) passent.
    """

    def filter(self, record):
        msg = record.getMessage()
        return "GET /tiles/" not in msg


def setup_logging(level="INFO"):
    # Réduit le bruit des journaux d'accès aux tuiles (voir la classe ci-dessus).
    wlog = logging.getLogger("werkzeug")
    if not any(isinstance(f, _MuteTileAccessLog) for f in wlog.filters):
        wlog.addFilter(_MuteTileAccessLog())

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
