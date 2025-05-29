import os
import streamlit as st
from streamlit_cookies_manager import EncryptedCookieManager
st.set_page_config(page_title="cripto multiexchange", layout="wide")
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from streamlit_js_eval import streamlit_js_eval
import requests
from models import init_db, SessionLocal, User, Exchange
from src.adapters import BinanceAdapter, BybitAdapter
from dashboard.dashboard_tab import show_dashboard_tab
from dashboard.profile import show_profile_tab
from dashboard.apikeys import show_apikeys_tab
from dashboard.logs import show_logs_tab

from dotenv import load_dotenv
load_dotenv()
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

RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY")



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


import random

def genera_operazione():
    operazioni = [
        ("+", lambda a, b: a + b),
        ("-", lambda a, b: a - b),
        ("*", lambda a, b: a * b),
    ]
    op, func = random.choice(operazioni)
    a, b = random.randint(1, 10), random.randint(1, 10)
    if op == "-" and a < b:
        a, b = b, a
    domanda = f"Quanto fa {a} {op} {b}?"
    risultato = func(a, b)
    return domanda, risultato

# Genera il captcha solo se non già presente
if 'captcha_domanda' not in st.session_state:
    domanda, risultato = genera_operazione()
    st.session_state['captcha_domanda'] = domanda
    st.session_state['captcha_risposta'] = risultato

if username is None:
    st.title("🔒 Binance Scheduler")
    mode = st.radio("Modalità:", ["Login", "Registrazione"])

    if mode == "Login":
        usr = st.text_input("Username", key="login_user")
        pwd = st.text_input("Password", type="password", key="login_pwd")
        captcha_input = st.text_input(f"Captcha: {st.session_state['captcha_domanda']}", key="captcha_input_login")

        if st.button("Entra"):
            user = session.query(User).filter_by(username=usr).first()
            if not user or not check_password_hash(user.password_hash, pwd):
                st.error("Credenziali non valide.")
            elif str(captcha_input).strip() != str(st.session_state['captcha_risposta']):
                st.error("Captcha errato! Riprova.")
                # RIGENERA solo ora
                domanda, risultato = genera_operazione()
                st.session_state['captcha_domanda'] = domanda
                st.session_state['captcha_risposta'] = risultato
            else:
                # Login ok, resetta captcha per sicurezza
                st.session_state.pop('captcha_domanda', None)
                st.session_state.pop('captcha_risposta', None)
                set_login_cookie(usr)

    else:  # Registrazione
        new_user    = st.text_input("Nuovo Username", key="reg_user")
        new_email   = st.text_input("Email", key="reg_email")
        new_pwd     = st.text_input("Password", type="password", key="reg_pwd")
        confirm_pwd = st.text_input("Conferma Password", type="password", key="reg_confirm")
        captcha_input = st.text_input(f"Captcha: {st.session_state['captcha_domanda']}", key="captcha_input_reg")

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
            elif str(captcha_input).strip() != str(st.session_state['captcha_risposta']):
                st.error("Captcha errato! Riprova.")
                # RIGENERA solo ora
                domanda, risultato = genera_operazione()
                st.session_state['captcha_domanda'] = domanda
                st.session_state['captcha_risposta'] = risultato
            else:
                # Registrazione ok, resetta captcha per sicurezza
                st.session_state.pop('captcha_domanda', None)
                st.session_state.pop('captcha_risposta', None)
                pwd_hash = generate_password_hash(new_pwd)
                session.add(User(username=new_user, email=new_email, password_hash=pwd_hash))
                session.commit()
                set_login_cookie(new_user)

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
show_dashboard_tab(tabs[0], current_user, adapters, session, cookies)
show_profile_tab(tabs[1], current_user, session)
show_apikeys_tab(tabs[2], current_user, session)
show_logs_tab(tabs[3])

