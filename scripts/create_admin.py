"""
Create the initial admin user.
Usage: python scripts/create_admin.py
       python scripts/create_admin.py --email admin@example.com --senha MinhaS3nha!
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.user import User


def create_admin(email: str, nome: str, senha: str) -> None:
    app = create_app()
    with app.app_context():
        existing = User.query.filter_by(email=email).first()
        if existing:
            if existing.is_admin:
                print(f"[AVISO] Usuário '{email}' já existe e já é admin.")
            else:
                existing.is_admin = True
                db.session.commit()
                print(f"[OK] Usuário '{email}' promovido a admin.")
            return

        admin = User(nome=nome, email=email, is_admin=True)
        admin.set_senha(senha)
        db.session.add(admin)
        db.session.commit()
        print(f"[OK] Admin criado com sucesso.")
        print(f"     E-mail: {email}")
        print(f"     Acesse: /admin")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Criar usuário administrador")
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL", ""))
    parser.add_argument("--nome", default="Administrador")
    parser.add_argument("--senha", default=os.getenv("ADMIN_PASSWORD", ""))
    args = parser.parse_args()

    if not args.email:
        args.email = input("E-mail do admin: ").strip()
    if not args.senha:
        import getpass
        args.senha = getpass.getpass("Senha do admin: ")

    if len(args.senha) < 8:
        print("Erro: a senha deve ter no mínimo 8 caracteres.")
        sys.exit(1)

    create_admin(args.email, args.nome, args.senha)
