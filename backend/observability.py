"""Suivi d'erreurs (Sentry) — actif uniquement si SAFECITY_SENTRY_DSN est défini.

Permet d'être alerté automatiquement quand le serveur rencontre une erreur en
production (traces d'exception centralisées). Sans DSN, ne fait rien.
"""
import logging

log = logging.getLogger("safecity")


def init_sentry(config):
    dsn = getattr(config, "SENTRY_DSN", None)
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[FlaskIntegration()],
            environment=config.ENV,
            traces_sample_rate=float(getattr(config, "SENTRY_TRACES_RATE", 0.0)),
            send_default_pii=False,  # ne jamais transmettre de données personnelles
        )
        log.info("Suivi d'erreurs Sentry activé (env=%s).", config.ENV)
    except Exception as e:  # pragma: no cover - dépend du paquet/réseau
        log.warning("Initialisation de Sentry impossible : %s", e)
