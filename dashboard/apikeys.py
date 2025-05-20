# file: dashboard/apikeys.py
import streamlit as st
from sqlalchemy.exc import IntegrityError
from models import APIKey, Exchange

def show_apikeys_tab(tab, user, session):
    with tab:
        st.header('Gestione API Keys')
        for key in user.api_keys:
            c1, c2, c3 = st.columns([2, 4, 1])
            c1.write(key.exchange.name)
            c2.write(key.api_key)
            if c3.button('Elimina', key=f'del_{key.id}'):
                session.delete(key)
                session.commit()
                st.rerun()
        with st.form('form_add'):
            st.subheader('Aggiungi API Key')
            exs = session.query(Exchange).order_by(Exchange.name).all()
            exchange_dict = {e.name: e.id for e in exs}
            exchange_name = st.selectbox('Exchange', list(exchange_dict.keys()))
            exchange_id = exchange_dict[exchange_name]
            a = st.text_input('API Key')
            s = st.text_input('Secret')
            if st.form_submit_button('Aggiungi'):
                if a and s:
                    # Cerca se esiste già una chiave per questo utente e questo exchange
                    existing = session.query(APIKey).filter_by(
                        user_id=user.id, exchange_id=exchange_id
                    ).first()
                    if existing:
                        # Elimina la vecchia API key prima di aggiungere la nuova
                        session.delete(existing)
                        session.commit()
                    try:
                        session.add(APIKey(user_id=user.id, exchange_id=exchange_id, api_key=a, secret_key=s))
                        session.commit()
                        st.success('API Key inserita/sostituita!')
                        st.rerun()
                    except IntegrityError:
                        session.rollback()
                        st.error('Errore inserimento')
                else:
                    st.error('Campi obbligatori')

