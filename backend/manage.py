"""Commandes d'administration SafeCity.

Usage :
    python -m backend.manage create-admin --email admin@ex.org --password '...' --name 'Nom'
    python -m backend.manage list-staff
    python -m backend.manage test-email --to destinataire@example.com
"""
import argparse
import sys

from . import create_app
from .extensions import db
from .models import ROLES, Team, User
from .security import hash_password


def _create_admin(args):
    app = create_app()
    with app.app_context():
        role = args.role if args.role in ROLES else "admin"
        existing = User.query.filter(db.func.lower(User.email) == args.email.lower()).first()
        if existing:
            existing.password_hash = hash_password(args.password)
            existing.role = role
            existing.name = args.name or existing.name
            db.session.commit()
            print(f"Compte mis à jour : {existing.email} ({existing.role})")
        else:
            user = User(
                name=args.name or args.email.split("@")[0],
                email=args.email.lower(),
                role=role,
                password_hash=hash_password(args.password),
            )
            db.session.add(user)
            db.session.commit()
            print(f"Compte créé : {user.email} ({user.role})")


def _list_staff(_args):
    app = create_app()
    with app.app_context():
        for u in User.query.filter(User.role != "citizen").order_by(User.role.desc()).all():
            print(f"  {u.id:>3}  {u.role:<10}  {u.name:<24}  {u.email}")


def _relocate_teams(_args):
    """Repositionne vers le centre-ville configuré les équipes de patrouille
    situées trop loin (ex. anciennes équipes de démo restées à Kinshasa) — pour
    que la « distance équipe » redevienne réaliste sur un déploiement existant."""
    from .geo import haversine_m

    app = create_app()
    with app.app_context():
        clat = app.config["DEFAULT_PATROL_LAT"]
        clng = app.config["DEFAULT_PATROL_LNG"]
        moved = 0
        for t in Team.query.all():
            if t.patrol_lat is None or t.patrol_lng is None:
                continue
            if haversine_m(t.patrol_lat, t.patrol_lng, clat, clng) > 100_000:  # > 100 km
                t.patrol_lat, t.patrol_lng = clat, clng
                moved += 1
                print(f"  → {t.name} repositionnée")
        if moved:
            db.session.commit()
        print(f"{moved} équipe(s) repositionnée(s) vers le centre ({clat}, {clng}).")


def _list_citizens(_args):
    """Liste les comptes citoyens (diagnostic de la page « Gestion des citoyens »)."""
    app = create_app()
    with app.app_context():
        citizens = User.query.filter_by(role="citizen").order_by(
            User.created_at.desc()).all()
        print(f"{len(citizens)} citoyen(s) inscrit(s) :")
        for u in citizens:
            created = (u.created_at.isoformat() if u.created_at else "")[:19]
            print(f"  {u.id:>3}  {u.name:<24}  {u.phone or '—':<16}  "
                  f"{u.email or '—':<28}  {created}")


def _purge_old(args):
    """Purge de conservation : supprime les alertes clôturées anciennes."""
    from .services.retention import purge_old_alerts

    app = create_app()
    with app.app_context():
        days = args.days if args.days is not None else app.config["RETENTION_DAYS"]
        n = purge_old_alerts(days)
        print(f"Purge terminée : {n} alerte(s) clôturée(s) de plus de {days} jours supprimée(s).")


def _purge_demo(args):
    """Supprime les comptes de démonstration (opérateur + personnels semés)."""
    from .seed import _DEMO_STAFF

    app = create_app()
    with app.app_context():
        demo_emails = [app.config["DEMO_OPERATOR_EMAIL"]] + [e for _, e, *_ in _DEMO_STAFF]
        rows = User.query.filter(db.func.lower(User.email).in_(
            [e.lower() for e in demo_emails])).all()
        if not rows:
            print("Aucun compte de démonstration trouvé (déjà nettoyé).")
            return
        # Sécurité : refuser si cela supprimerait le dernier administrateur.
        remaining_admins = User.query.filter(
            User.role == "admin",
            db.func.lower(User.email).notin_([e.lower() for e in demo_emails])).count()
        if remaining_admins == 0:
            print("⚠ Refus : aucun administrateur réel ne subsisterait. Créez d'abord "
                  "un vrai admin :\n  python -m backend.manage create-admin --email … "
                  "--password … --name …")
            sys.exit(1)
        for u in rows:
            print(f"  suppression : {u.email} ({u.role})")
            db.session.delete(u)
        db.session.commit()
        print(f"{len(rows)} compte(s) de démonstration supprimé(s).")
        if app.config.get("SEED_DEMO_OPERATOR"):
            print("⚠ ATTENTION : SAFECITY_SEED_DEMO est encore ACTIF — les comptes de "
                  "démo seront RECRÉÉS au prochain redémarrage. Mettez "
                  "SAFECITY_SEED_DEMO=false puis redémarrez AVANT de purger.")


def _delete_user(args):
    """Supprime un compte par e-mail."""
    app = create_app()
    with app.app_context():
        u = User.query.filter(db.func.lower(User.email) == args.email.lower()).first()
        if not u:
            print(f"Aucun compte pour {args.email}.")
            sys.exit(1)
        if u.role == "admin" and User.query.filter(User.role == "admin").count() <= 1:
            print("⚠ Refus : c'est le dernier administrateur. Créez-en un autre d'abord.")
            sys.exit(1)
        db.session.delete(u)
        db.session.commit()
        print(f"Compte supprimé : {args.email} ({u.role}).")


def _test_email(args):
    """Envoie un e-mail de test pour vérifier la configuration SMTP (Gmail)."""
    from .services import notifications

    app = create_app()
    with app.app_context():
        if not notifications.smtp_configured():
            print("SMTP non configuré : définissez SAFECITY_SMTP_HOST / _USER / "
                  "_PASSWORD / _FROM (voir .env.example).")
            sys.exit(1)
        cfg = app.config
        print(f"Envoi d'un e-mail de test via {cfg['SMTP_HOST']}:{cfg['SMTP_PORT']} "
              f"(expéditeur {cfg['SMTP_FROM']}) → {args.to} …")
        try:
            notifications.send_email_message(
                [args.to], "SafeCity — e-mail de test",
                "Ceci est un e-mail de test SafeCity.\n\n"
                "Si vous le recevez, la configuration Gmail/SMTP fonctionne : les "
                "citoyens recevront leurs codes de vérification par e-mail.")
        except Exception as e:
            print(f"ÉCHEC : {e}")
            print("Piste : pour Gmail, activez la validation en 2 étapes puis "
                  "utilisez un « mot de passe d'application » (16 caractères), pas "
                  "le mot de passe habituel du compte.")
            sys.exit(1)
        print("OK : e-mail envoyé. Vérifiez la boîte de réception (et les spams).")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="backend.manage")
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create-admin", help="Créer/mettre à jour un compte personnel")
    c.add_argument("--email", required=True)
    c.add_argument("--password", required=True)
    c.add_argument("--name", default=None)
    c.add_argument("--role", default="admin", choices=ROLES)
    c.set_defaults(func=_create_admin)

    sub.add_parser("list-staff", help="Lister les comptes personnels").set_defaults(func=_list_staff)
    sub.add_parser("list-citizens",
                   help="Lister les comptes citoyens inscrits").set_defaults(func=_list_citizens)
    sub.add_parser("relocate-teams",
                   help="Repositionner les équipes de patrouille égarées vers le "
                        "centre-ville configuré").set_defaults(func=_relocate_teams)

    pg = sub.add_parser("purge-old", help="Supprimer les alertes clôturées anciennes (conservation)")
    pg.add_argument("--days", type=int, default=None,
                    help="Âge en jours (défaut : SAFECITY_RETENTION_DAYS)")
    pg.set_defaults(func=_purge_old)

    te = sub.add_parser("test-email", help="Envoyer un e-mail de test (vérifie le SMTP/Gmail)")
    te.add_argument("--to", required=True, help="Adresse destinataire de l'e-mail de test")
    te.set_defaults(func=_test_email)

    sub.add_parser("purge-demo",
                   help="Supprimer les comptes de démonstration (safecity.local)").set_defaults(func=_purge_demo)

    du = sub.add_parser("delete-user", help="Supprimer un compte par e-mail")
    du.add_argument("--email", required=True)
    du.set_defaults(func=_delete_user)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
