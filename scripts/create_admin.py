"""
Create the initial admin user.
Usage: python scripts/create_admin.py
       python scripts/create_admin.py --email admin@example.com --senha MinhaS3nha!
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _resolver_destino():
    """Define o DATABASE_URL do processo ANTES de importar o app.

    A classe Config lê DATABASE_URL no momento do import (é atributo de
    classe): resolver isto depois criaria o usuário no banco local mesmo
    tendo sido pedido produção — falha silenciosa, o script diz "criado".
    """
    from dotenv import load_dotenv
    load_dotenv()

    destino = None
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == "--database-url" and i + 1 < len(argv):
            destino = argv[i + 1]
        elif arg.startswith("--database-url="):
            destino = arg.split("=", 1)[1]
    destino = destino or os.environ.get("PROD_DATABASE_URL")

    if destino:
        if destino.startswith("postgres://"):
            destino = destino.replace("postgres://", "postgresql://", 1)
        os.environ["DATABASE_URL"] = destino


_resolver_destino()

from app import create_app
from app.extensions import db
from app.models.user import User


def create_admin(email: str, nome: str, senha: str) -> None:
    app = create_app()
    with app.app_context():
        # Mostra em qual banco escreveu (senha oculta) — sem isso é fácil criar
        # o usuário no banco errado e não perceber.
        import re
        uri = re.sub(r"://([^:/@]+):[^@]+@", r"://\1:***@", app.config["SQLALCHEMY_DATABASE_URI"])
        print(f"[INFO] Banco de destino: {uri}")
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
    parser.add_argument(
        "--database-url", default=None,
        help="Banco de destino. Se omitido, usa PROD_DATABASE_URL do ambiente/.env; "
             "se essa também não existir, usa o banco configurado normalmente (o local).",
    )
    args = parser.parse_args()

    # Permite criar o usuário direto em produção sem alterar o DATABASE_URL
    # do ambiente local de desenvolvimento.
    destino = args.database_url or os.getenv("PROD_DATABASE_URL")
    if destino:
        if destino.startswith("postgres://"):
            destino = destino.replace("postgres://", "postgresql://", 1)
        os.environ["DATABASE_URL"] = destino

    if not args.email:
        args.email = input("E-mail do admin: ").strip()
    if not args.senha:
        import getpass
        args.senha = getpass.getpass("Senha do admin: ")

    if len(args.senha) < 8:
        print("Erro: a senha deve ter no mínimo 8 caracteres.")
        sys.exit(1)

    create_admin(args.email, args.nome, args.senha)
