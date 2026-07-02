"""
Import license keys from a text file into the database.
Usage: python scripts/import_keys.py keys.txt
       python scripts/import_keys.py keys.txt --dry-run
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models.key import Key


def import_keys(filepath: str, dry_run: bool = False) -> None:
    app = create_app()
    with app.app_context():
        with open(filepath, "r", encoding="utf-8") as f:
            raw_lines = [line.strip() for line in f if line.strip()]

        keys_to_insert = []
        skipped_blank = 0
        skipped_header = 0

        for line in raw_lines:
            if line.startswith("#") or line.lower().startswith("key"):
                skipped_header += 1
                continue
            if not line:
                skipped_blank += 1
                continue
            keys_to_insert.append(line)

        print(f"Arquivo: {filepath}")
        print(f"Linhas lidas: {len(raw_lines)}")
        print(f"Cabeçalhos/comentários ignorados: {skipped_header}")
        print(f"Keys candidatas: {len(keys_to_insert)}")

        existing = {k.key for k in Key.query.with_entities(Key.key).all()}
        novas = [k for k in keys_to_insert if k not in existing]
        duplicatas = len(keys_to_insert) - len(novas)

        print(f"Duplicatas (já existem no banco): {duplicatas}")
        print(f"Keys novas a importar: {len(novas)}")

        if dry_run:
            print("\n[DRY RUN] Nenhuma alteração foi feita no banco.")
            if novas:
                print("Exemplo das primeiras 5 keys novas:")
                for k in novas[:5]:
                    print(f"  {k}")
            return

        if not novas:
            print("\nNenhuma key nova para importar.")
            return

        for key_str in novas:
            db.session.add(Key(key=key_str, status="disponivel"))

        db.session.commit()
        print(f"\n[OK] {len(novas)} keys importadas com sucesso.")
        print(f"Total de keys disponíveis no banco: {Key.total_disponiveis()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python scripts/import_keys.py <arquivo.txt> [--dry-run]")
        sys.exit(1)

    filepath = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if not os.path.exists(filepath):
        print(f"Erro: arquivo '{filepath}' não encontrado.")
        sys.exit(1)

    import_keys(filepath, dry_run=dry_run)
