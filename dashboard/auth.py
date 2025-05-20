# file: dashboard/auth.py
import os
import streamlit as st
import yaml
from pathlib import Path
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash
from models import init_db, SessionLocal, User, Exchange, APIKey
import streamlit_authenticator as stauth

# Initialize DB and session
init_db()
session = SessionLocal()

# Seed exchanges if empty
def seed_exchanges():
    if session.query(Exchange).count() == 0:
        for name in ["binance", "bybit", "kraken", "ftx"]:
            session.add(Exchange(name=name))
        session.commit()
seed_exchanges()

# Authenticate or register user

def authenticate_user():
    # Load credentials.yaml
    with open("credentials.yaml") as file:
        config = yaml.safe_load(file)
    auth = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"]
    )
    mode = st.sidebar.selectbox("Entra o registrati", ["Login", "Registrazione"])
    if mode == "Registrazione":
        st.sidebar.header("Nuovo Utente")
        new_user = st.sidebar.text_input("Username", key="reg_user")
        new_pwd  = st.sidebar.text_input("Password", type="password", key="reg_pwd")
        if st.sidebar.button("Registrati"):
            if not new_user or not new_pwd:
                st.sidebar.error("Compila entrambi i campi.")
            else:
                # Append to YAML
                yaml_obj = yaml.safe_load(open("credentials.yaml"))
                users_block = yaml_obj["credentials"]["users"]
                if new_user in users_block:
                    st.sidebar.error("Username già esistente.")
                else:
                    hashed = generate_password_hash(new_pwd)
                    users_block[new_user] = {"name": new_user, "password": hashed}
                    with open("credentials.yaml", "w") as fp:
                        yaml.dump(yaml_obj, fp)
                    st.sidebar.success("Registrazione completata! Effettua il login.")
        st.stop()
    # Login
    auth.login(location='main', key='Login')
    if not st.session_state.get('authentication_status'):
        st.warning("🔒 Inserisci username e password")
        st.stop()
    # Sync user in DB
    env_username = st.session_state.get('username')
    user = session.query(User).filter_by(username=env_username).first()
    if user is None:
        user = User(username=env_username, password_hash="")
        session.add(user)
        session.commit()
        user = session.query(User).filter_by(username=env_username).first()
    # Build adapters dict placeholder
    adapters = {}
    # load api keys and assign adapters here or later in dashboard_tab
    return user, adapters, session

