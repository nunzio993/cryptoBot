"""
Script per aggiungere Bybit exchange al database
"""
from models import SessionLocal, Exchange

def add_bybit():
    session = SessionLocal()
    try:
        # Check if bybit already exists
        existing = session.query(Exchange).filter_by(name="bybit").first()
        if existing:
            print("Bybit exchange already exists!")
            return
        
        # Add bybit
        bybit = Exchange(name="bybit", display_name="Bybit")
        session.add(bybit)
        session.commit()
        print("Bybit exchange added successfully!")
    finally:
        session.close()

if __name__ == "__main__":
    add_bybit()
