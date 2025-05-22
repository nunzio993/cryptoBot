def show_apikeys_tab(tab, user, session):
    with tab:
        import streamlit as st
        from models import APIKey, Exchange

        st.header("Gestione API Keys")

        # 1. Selezione Exchange
        exchanges = session.query(Exchange).all()
        if not exchanges:
            st.error("Nessun exchange disponibile nel sistema.")
            return
        exchange_names = [ex.name for ex in exchanges]
        selected_exchange_name = st.selectbox("Exchange", exchange_names)
        selected_exchange = next(ex for ex in exchanges if ex.name == selected_exchange_name)

        # 2. Selezione Network
        col1, col2 = st.columns(2)
        for net, label in zip([True, False], ["Testnet", "Mainnet"]):
            with col1 if net else col2:
                st.subheader(label)
                key = session.query(APIKey).filter_by(
                    user_id=user.id,
                    exchange_id=selected_exchange.id,
                    is_testnet=net
                ).first()
                api_key = st.text_input(
                    f"{label} API Key",
                    value=key.api_key if key else "",
                    key=f"{selected_exchange_name}_{label}_api"
                )
                secret_key = st.text_input(
                    f"{label} Secret Key",
                    value=key.secret_key if key else "",
                    type="password",
                    key=f"{selected_exchange_name}_{label}_secret"
                )
                save_btn = st.button(f"Salva {label}", key=f"{selected_exchange_name}_{label}_save")
                delete_btn = st.button(f"Elimina {label}", key=f"{selected_exchange_name}_{label}_del")
                if save_btn:
                    if not api_key or not secret_key:
                        st.error("API Key e Secret obbligatorie.")
                    else:
                        if key:
                            key.api_key = api_key
                            key.secret_key = secret_key
                            st.success(f"{label} aggiornata per {selected_exchange_name}.")
                        else:
                            session.add(APIKey(
                                user_id=user.id,
                                exchange_id=selected_exchange.id,
                                api_key=api_key,
                                secret_key=secret_key,
                                is_testnet=net
                            ))
                            st.success(f"{label} aggiunta per {selected_exchange_name}.")
                        session.commit()
                        st.rerun()
                if key and delete_btn:
                    session.delete(key)
                    session.commit()
                    st.success(f"{label} eliminata per {selected_exchange_name}.")
                    st.rerun()

