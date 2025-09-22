
from apps.api.db.session import SessionLocal
from apps.api.db.models import User

def main():
    db = SessionLocal()
    if not db.query(User).count():
        db.add(User(risk_profile="LOW", capital=100.0, prefs={"pairs":[]}, api_connected=False))
        db.commit()
    db.close()
    print("Seed done.")

if __name__ == "__main__":
    main()
