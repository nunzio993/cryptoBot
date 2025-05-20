import streamlit as st
import secrets
from werkzeug.security import check_password_hash, generate_password_hash

# Sostituisci questo con il vero username del tuo bot Telegram (es: CryptoOrderNotifyBot)
BOT_LINK = "https://t.me/segnali_trading_Nunzio_bot"

def show_profile_tab(tab, user, session):
    with tab:
        st.header('Profilo Utente')
        st.write(f"**Username:** {user.username}")

        # --- CODICE TELEGRAM ---
        if not user.telegram_link_code:
            code = secrets.token_hex(4)
            user.telegram_link_code = code
            session.commit()
        else:
            code = user.telegram_link_code

        # ---- SEZIONE TELEGRAM MIGLIORATA ----
        st.markdown(f"""
        <div style="background-color: #f8f9fa; border-radius: 12px; padding: 1.3em 2em 1.1em 2em; margin-bottom: 1.3em; border: 1px solid #e0e0e0;">
            <span style="font-size: 1.18em; font-weight: bold;">🔗 Collega Telegram</span>
            <ul style="margin-top: 0.8em; margin-bottom: 0;">
              <li>Apri la chat con il <a href="{BOT_LINK}" target="_blank"><b>bot Telegram</b></a></li>
              <li>Invia questo comando per ricevere le notifiche dei tuoi ordini</b>:</li>
            </ul>
            <div style="margin-top: 1.2em; margin-bottom: 0.5em;">
                <code style="font-size:1.12em; background:#fcf2f2; color:#c7254e; border-radius:7px; padding:0.5em 1.3em;">
                    /link {code}
                </code>
            </div>
            <span style="color:#6c757d; font-size:0.99em;">Una volta collegato, riceverai le notifiche relative ai tuoi ordini.<br>Puoi scollegarti in qualsiasi momento dal bot.</span>
        </div>
        """, unsafe_allow_html=True)

        # --- CAMBIO PASSWORD (adesso dentro il tab!) ---
        with st.form('form_pwd'):
            st.subheader('Modifica Password')
            old = st.text_input('Vecchia password', type='password')
            new = st.text_input('Nuova password', type='password')
            confirm = st.text_input('Conferma nuova password', type='password')
            submit = st.form_submit_button('Salva')

            if submit:
                if not old or not new or not confirm:
                    st.error('Compila tutti i campi.')
                elif not check_password_hash(user.password_hash, old):
                    st.error('Vecchia password non corretta.')
                elif new != confirm:
                    st.error('Le nuove password non coincidono.')
                elif len(new) < 6:
                    st.error('La nuova password deve essere lunga almeno 6 caratteri.')
                else:
                    user.password_hash = generate_password_hash(new)
                    session.commit()
                    st.success('✅ Password aggiornata con successo!')

