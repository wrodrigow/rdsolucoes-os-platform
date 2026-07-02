"""
Initialize the database, create all tables, seed initial data, and create admin user.
Usage: python scripts/init_db.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import User


def init_db() -> None:
    app = create_app()
    with app.app_context():
        print("Criando tabelas...")
        db.create_all()
        print("[OK] Tabelas criadas.")

        admin_email = os.getenv("ADMIN_EMAIL", "")
        admin_password = os.getenv("ADMIN_PASSWORD", "")

        if admin_email and admin_password:
            existing = User.query.filter_by(email=admin_email).first()
            if not existing:
                admin = User(nome="Administrador", email=admin_email, is_admin=True)
                admin.set_senha(admin_password)
                db.session.add(admin)
                db.session.commit()
                print(f"[OK] Admin criado: {admin_email}")
            else:
                print(f"[INFO] Admin '{admin_email}' já existe.")
        else:
            print("[INFO] ADMIN_EMAIL/ADMIN_PASSWORD não definidos no .env — pule ou rode create_admin.py.")

        from app.models.key import Key
        total_keys = Key.query.count()
        print(f"[INFO] Keys no banco: {total_keys}")

        print("\nBanco inicializado com sucesso.")
        print("Próximos passos:")
        print("  1. python scripts/import_keys.py keys.txt")
        print("  2. python run.py")


if __name__ == "__main__":
    init_db()
