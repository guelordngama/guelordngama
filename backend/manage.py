"""Commandes d'administration SafeCity.

Usage :
    python -m backend.manage create-admin --email admin@ex.org --password '...' --name 'Nom'
    python -m backend.manage list-staff
"""
import argparse
import sys

from . import create_app
from .extensions import db
from .models import ROLES, User
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


def _purge_old(args):
    """Purge de conservation : supprime les alertes clôturées anciennes."""
    from .services.retention import purge_old_alerts

    app = create_app()
    with app.app_context():
        days = args.days if args.days is not None else app.config["RETENTION_DAYS"]
        n = purge_old_alerts(days)
        print(f"Purge terminée : {n} alerte(s) clôturée(s) de plus de {days} jours supprimée(s).")


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

    pg = sub.add_parser("purge-old", help="Supprimer les alertes clôturées anciennes (conservation)")
    pg.add_argument("--days", type=int, default=None,
                    help="Âge en jours (défaut : SAFECITY_RETENTION_DAYS)")
    pg.set_defaults(func=_purge_old)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
