import os
import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
st.set_page_config(page_title="cripto multiexchange", layout="wide")
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from models import init_db, SessionLocal, User, Exchange
from src.adapters import BinanceAdapter, BybitAdapter
from dashboard.dashboard_tab import show_dashboard_tab
from dashboard.profile import show_profile_tab
from dashboard.apikeys import show_apikeys_tab
from dashboard.logs import show_logs_tab

# —————————————
# 1) Configurazione pagina
# —————————————
#st.set_page_config(page_title="cripto multiexchange", layout="wide")

# Riduci lo spazio bianco sopra il titolo
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem !important;
    }
    header[data-testid="stHeader"] {
        height: 0rem;
        min-height: 0rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# —————————————
# 2) Cookie manager
# —————————————
COOKIE_PASSWORD = os.getenv("COOKIE_PASSWORD", "ChangeMe32Chars!")
cookies = EncryptedCookieManager(prefix="binance", password=COOKIE_PASSWORD)
if not cookies.ready():
    cookies.load()   # inietta il JS per recuperare i cookie
    st.stop()

# —————————————
# 3) DB e Session
# —————————————
init_db()
session = SessionLocal()
print("DATABASE_URL (core):", os.getenv("DATABASE_URL"))

# —————————————
# 4) Serializer per token
# —————————————
SECRET_KEY = os.getenv("SECRET_KEY", "ChangeThisTo32CharSecretKey!")
serializer = URLSafeTimedSerializer(SECRET_KEY, salt="auth-token")

def get_current_username():
    """Ritorna l’username se c’è un cookie valido, altrimenti None."""
    try:
        token = cookies.get("auth_token")
    except Exception:
        return None
    if not token:
        return None
    try:
        return serializer.loads(token, max_age=86400)
    except (BadSignature, SignatureExpired):
        return None

def set_login_cookie(username: str):
    """Crea, salva il cookie e ricarica la pagina."""
    token = serializer.dumps(username)
    cookies["auth_token"] = token
    cookies.save()
    st.rerun()

def clear_login_cookie():
    """Cancella il cookie e ricarica."""
    cookies["auth_token"] = ""
    cookies.save()
    st.rerun()

# —————————————
# 5) Controllo autenticazione
# —————————————
username = get_current_username()

if username is None:
    # Form di Login / Registrazione
    st.title("🔒 Binance Scheduler")
    mode = st.radio("Modalità:", ["Login", "Registrazione"])

    if mode == "Login":
        usr = st.text_input("Username", key="login_user")
        pwd = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Entra"):
            user = session.query(User).filter_by(username=usr).first()
            if not user or not check_password_hash(user.password_hash, pwd):
                st.error("Credenziali non valide.")
            else:
                set_login_cookie(usr)

    else:  # Registrazione
        new_user    = st.text_input("Nuovo Username", key="reg_user")
        new_email   = st.text_input("Email", key="reg_email")
        new_pwd     = st.text_input("Password", type="password", key="reg_pwd")
        confirm_pwd = st.text_input("Conferma Password", type="password", key="reg_confirm")
        if st.button("Registrati"):
            if not new_user or not new_email or not new_pwd or not confirm_pwd:
                st.error("Compila tutti i campi.")
            elif new_pwd != confirm_pwd:
                st.error("Le password non corrispondono.")
            elif "@" not in new_email or "." not in new_email:
                st.error("Email non valida.")
            elif session.query(User).filter_by(username=new_user).first():
                st.error("Username già esistente.")
            elif session.query(User).filter_by(email=new_email).first():
                st.error("Questa email è già registrata.")
            else:
                pwd_hash = generate_password_hash(new_pwd)
                session.add(User(username=new_user, email=new_email, password_hash=pwd_hash))
                session.commit()
                set_login_cookie(new_user)
    # Impedisce di raggiungere la dashboard finché non ci sono credenziali
    st.stop()

# —————————————
# 6) Utente autenticato
# —————————————
current_user = session.query(User).filter_by(username=username).first()
st.sidebar.write(f"👋 Benvenuto, **{current_user.username}**!")
if st.sidebar.button("Logout"):
    clear_login_cookie()

# —————————————
# 7) Seed Exchange + Adapter
# —————————————
if session.query(Exchange).count() == 0:
    session.add(Exchange(name="binance"))
    session.commit()

adapters = {}
for key in current_user.api_keys:
    if key.exchange.name == "binance":
        adapters["binance"] = BinanceAdapter(key.api_key, key.secret_key, testnet=True)
    elif key.exchange.name == "bybit":
        adapters["bybit"] = BybitAdapter(key.api_key, key.secret_key)

# —————————————
# 8) Dashboard Tabs
# —————————————

APP_NAME = "Crypto MultiBot"

st.markdown(
    f"<h1 style='text-align: center; margin-top: 0;'>{APP_NAME}</h1>",
    unsafe_allow_html=True
)
st.markdown(
    "<div style='text-align: center; margin-bottom: 1em;'>Gestisci i tuoi ordini su più exchange da un'unica dashboard.</div>",
    unsafe_allow_html=True
)

tabs = st.tabs(["Dashboard", "Profile", "API Keys", "Logs"])
show_dashboard_tab(tabs[0], current_user, adapters, session)
show_profile_tab(tabs[1], current_user, session)
show_apikeys_tab(tabs[2], current_user, session)
show_logs_tab(tabs[3])

