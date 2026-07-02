import os
from app import create_app
from app.extensions import db

application = create_app("production")

with application.app_context():
    db.create_all()
    from app.models.user import User
    admin_email = os.getenv("ADMIN_EMAIL", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if admin_email and admin_password:
        if not User.query.filter_by(email=admin_email).first():
            admin = User(nome="Administrador", email=admin_email, is_admin=True)
            admin.set_senha(admin_password)
            db.session.add(admin)
            db.session.commit()

if __name__ == "__main__":
    application.run()
