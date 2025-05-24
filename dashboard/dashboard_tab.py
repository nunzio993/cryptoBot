import math
import textwrap
import streamlit as st
import pandas as pd
import datetime
from pathlib import Path
from sqlalchemy import Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine
from binance.client import Client
from src.core_and_scheduler import fetch_last_closed_candle
from symbols import SYMBOLS
from models import Order, User, SessionLocal
from src.adapters import BinanceAdapter, BybitAdapter
from models import APIKey, Exchange

# Mapping timeframe -> (Binance interval, millisecondi)
INTERVAL_MAP = {
    'M5':    ('5m',    5 * 60 * 1000),
    'H1':    ('1h',    1 * 3600 * 1000),
    'H4':    ('4h',    4 * 3600 * 1000),
    'Daily': ('1d',   24 * 3600 * 1000),
}

APP_NAME = "Crypto MultiBot"  # scegli il nme che preferisci
MAIN_ASSET = "USDC"

def is_position_open_binance(symbol, user, session, network_mode, required_qty):
    # Trova la chiave API giusta
    exchange = session.query(Exchange).filter_by(name="binance").first()
    if not exchange:
        return False
    key = session.query(APIKey).filter_by(
        user_id=user.id,
        exchange_id=exchange.id,
        is_testnet=(network_mode == "Testnet")
    ).first()
    if not key:
        return False

    adapter = BinanceAdapter(key.api_key, key.secret_key, testnet=(network_mode == "Testnet"))
    balance = adapter.get_balance(symbol.replace('USDC', ''))  # es: "TRXUSDC" -> "TRX"
    try:
        # Se hai almeno 0.01 di quell'asset, la posizione è "reale"
        return float(balance) > 0.01
    except Exception:
        return False



def show_dashboard_tab(tab, user, adapters, session, cookies):
    with tab:
        # ---- Gestione persistente modalità rete ----
        if "network_mode" not in st.session_state:
            st.session_state["network_mode"] = cookies.get("network_mode") or "Testnet"

        def set_network_mode_cookie():
            cookies["network_mode"] = st.session_state["network_mode"]
            cookies.save()

        st.sidebar.radio(
            "Modalità rete:",
            ("Testnet", "Mainnet"),
            key="network_mode",
            on_change=set_network_mode_cookie
        )
        # Ora il valore scelto è sempre in st.session_state["network_mode"]
        network_mode = st.session_state["network_mode"]

        exchange = session.query(Exchange).filter_by(name="binance").first()
        if not exchange:
            st.error("Exchange 'binance' non trovato!")
            return

        if network_mode == "Mainnet":
            key = session.query(APIKey).filter_by(
                user_id=user.id,
                exchange_id=exchange.id,
                is_testnet=False
            ).first()
        else:
            key = session.query(APIKey).filter_by(
                user_id=user.id,
                exchange_id=exchange.id,
                is_testnet=True
            ).first()

        if key is None:
            st.warning("Non hai configurato le API Key per questa modalità su Binance!")
            st.info("Vai al tab 'API Keys' per aggiungerle o modificarle.")
            return

        adapters = {
            "binance": BinanceAdapter(key.api_key, key.secret_key, testnet=(network_mode == "Testnet"))
        }


        # --- SCELTA EXCHANGE ---
        exchanges_available = [k for k in adapters.keys()]
        if not exchanges_available:
            st.error("Nessun exchange configurato nelle API Keys!")
            return
        # Mostra la selectbox per scegliere exchange
        selected_exchange = st.sidebar.selectbox(
            "Exchange",
            exchanges_available,
            format_func=lambda x: x.capitalize()
        )
        adapter = adapters[selected_exchange]

        # --- Form Nuovo Trade in sidebar ---
        st.sidebar.markdown("### Saldo")
        pending  = session.query(Order).filter_by(user_id=user.id, status="PENDING").all()
        executed = session.query(Order).filter_by(user_id=user.id, status="EXECUTED").all()

        try:
            adapter = adapters[selected_exchange]
            balance = adapter.get_balance(MAIN_ASSET)
            st.sidebar.write(f"**{MAIN_ASSET}: {balance:,.2f}**")

            usdc_bloccati_pending = sum(float(o.quantity) * float(o.max_entry) for o in pending if o.max_entry is not None)
            usdc_bloccati_executed = sum(float(o.quantity) * float(o.executed_price) for o in executed if o.executed_price is not None)
            usdc_bloccati = usdc_bloccati_pending + usdc_bloccati_executed
            usdc_disponibili = balance - usdc_bloccati
            st.sidebar.write(f"USDC disponibili: {usdc_disponibili:,.2f}")
        except Exception as e:
            st.sidebar.warning(f"Saldo non disponibile: {e}")



        st.sidebar.subheader("Nuovo Trade")
        with st.sidebar.form("trade_form", clear_on_submit=True):
            symbols_filtered = [s for s in SYMBOLS if s.endswith("USDC")]
            symbol = st.selectbox("Simbolo", symbols_filtered)
            quantity = st.number_input("Quantità", min_value=0.0, format="%.4f")
            entry_price = st.number_input("Entry Price", min_value=0.0, format="%.4f")
            if "max_entry" not in st.session_state or st.session_state["entry_price"] != entry_price:
                st.session_state["max_entry"] = entry_price + 1  # O il delta che vuoi
                st.session_state["entry_price"] = entry_price
            max_entry = st.number_input(
                "Max Entry Price (annulla oltre)",
                min_value=entry_price,
                format="%.4f",
                help="Se la candela close > questo, il segnale verrà annullato"
            )
            entry_interval = st.selectbox("Entry Interval", list(INTERVAL_MAP.keys()))
            take_profit = st.number_input("Take Profit", min_value=0.0, format="%.4f")
            stop_loss = st.number_input("Stop Loss", min_value=0.0, format="%.4f")
            stop_interval = st.selectbox("Stop Interval", list(INTERVAL_MAP.keys()))
            submitted = st.form_submit_button("Aggiungi Trade")
            if submitted:                # VALIDAZIONE DI BASE
                if not (stop_loss < entry_price < take_profit):
                    st.error("❌ Deve valere Stop Loss < Entry Price < Take Profit.")
                elif max_entry < entry_price:
                    st.error("❌ Max Entry deve essere ≥ Entry Price.")
                else:
                    # Controlla ultimo close
                    last_close = float(fetch_last_closed_candle(symbol, entry_interval)[4])
                    if last_close >= take_profit:
                        st.error(f"❌ Candela precedente {entry_interval} ({last_close:.2f}) ≥ TP; non inserito.")
                    else:
                        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                        order = Order(
                            user_id=user.id,
                            symbol=symbol,
                            side="LONG",
                            quantity=quantity,
                            status="PENDING",
                            entry_price=entry_price,
                            max_entry=max_entry,
                            take_profit=take_profit,
                            stop_loss=stop_loss,
                            entry_interval=entry_interval,
                            stop_interval=stop_interval,
                            created_at=now
                        )
                        session.add(order)
                        print("DEBUG ---", "entry_price:", entry_price, "max_entry:", max_entry)
                        session.commit()
                        st.success("✅ Trade aggiunto come PENDING")
                        st.rerun()

        # ----------- QUERY E TABELLE ORDINI -----------
        pending  = session.query(Order).filter_by(user_id=user.id, status="PENDING").all()
        executed = session.query(Order).filter_by(user_id=user.id, status="EXECUTED").all()

        # ----- TABELLA ORDINI PENDING -----
        st.subheader("Ordini PENDING")
        header_cols = st.columns([0.6,1.5,1,1.2,1.2,1.8,1.2,1.2,1,1.8,1.2])
        header_names = [
            "ID", "Simbolo", "Quantità", "Entry", "Max Entry", "Totale USDC", "TP", "SL", "TF Entry", "Data creazione", "Azioni"
        ]
        for col, name in zip(header_cols, header_names):
            col.markdown(f"**{name}**")

        if not pending:
            st.write("Nessun ordine pendente.")
        else:

            for o in pending:
                cols = st.columns([0.6,1.5,1,1.2,1.2,1.8,1.2,1.2,1,1.8,1.2])
                cols[0].write(o.id)
                cols[1].write(o.symbol)
                cols[2].write(float(o.quantity))
                cols[3].write(float(o.entry_price))
                cols[4].write(float(o.max_entry) if o.max_entry else "-")
                cols[5].write(float(o.quantity) * float(o.max_entry) if o.max_entry else "-")
                with cols[6]:
                    new_tp = st.number_input(
                        "",
                        min_value=0.0,
                        value=float(o.take_profit),
                        key=f"tp_pending_{o.id}",
                        step=0.01,
                        format="%.2f",
                        label_visibility="collapsed"
                    )
                with cols[7]:
                    new_sl = st.number_input(
                        "",
                        min_value=0.0,
                        value=float(o.stop_loss),
                        key=f"sl_pending_{o.id}",
                        step=0.01,
                        format="%.2f",
                        label_visibility="collapsed"
                    )
                cols[8].write(o.entry_interval)
                cols[9].write(o.created_at.strftime("%Y-%m-%d %H:%M"))
                with cols[10]:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("💾", key=f"update_pending_{o.id}"):
                            o.take_profit = new_tp
                            o.stop_loss = new_sl
                            session.commit()
                            st.success(f"TP/SL aggiornati per ordine {o.id} (PENDING)")
                            st.rerun()
                    with c2:
                        if st.button("❌", key=f"cancel_{o.id}"):
                            o.status = "CANCELLED"
                            o.closed_at = datetime.datetime.now(datetime.timezone.utc)
                            session.commit()
                            st.rerun()

        st.markdown("---")

        # ----- TABELLA ORDINI ESEGUITI (A MERCATO) -----
        # ----- TABELLA ORDINI ESEGUITI (A MERCATO) -----
        st.subheader("Ordini A MERCATO")
        header_cols = st.columns([0.6,1.5,1,1.3,1.8,1.8,1.6,1.6,1,1.2])
        header_names = [
            "ID", "Simbolo", "Quantità", "Prezzo Esecuzione", "Totale USDC", "data", "Data Esecuzione", "TP", "SL", "TF SL", "Azioni"
        ]
        for col, name in zip(header_cols, header_names):
            col.markdown(f"**{name}**")

        if not executed:
            st.write("Nessun ordine eseguito.")
        else:

            for o in executed:
                cols = st.columns([0.6,1.5,1,1.3,1.8,1.8,1.6,1.6,1,1.2])
                cols[0].write(o.id)
                cols[1].write(o.symbol)
                is_open = is_position_open_binance(o.symbol, user, session, network_mode, o.quantity)

                if is_open:
                    exchange = session.query(Exchange).filter_by(name="binance").first()
                    key = session.query(APIKey).filter_by(
                        user_id=user.id,
                        exchange_id=exchange.id,
                        is_testnet=(network_mode == "Testnet")
                    ).first()
                    adapter = BinanceAdapter(key.api_key, key.secret_key, testnet=(network_mode == "Testnet"))
                    asset_name = o.symbol.replace("USDC", "")
                    balance = adapter.get_balance(asset_name)
                    last_price = adapter.get_symbol_price(o.symbol)
                    real_qty = float(balance)
                    real_price = float(last_price)
                    real_total = real_qty * real_price

                    cols[2].write(f"{real_qty:,.4f}")
                    cols[3].write(f"{real_price:,.4f}")
                    cols[4].write(f"{real_total:,.2f}")
                else:
                    cols[2].write(float(o.quantity))
                    cols[3].write(float(o.executed_price or 0))
                    cols[4].write(float(o.quantity) * float(o.executed_price) if o.executed_price else "-")
                cols[5].write(o.executed_at.strftime("%Y-%m-%d %H:%M") if o.executed_at else "-")
                with cols[6]:
                    new_tp = st.number_input(
                        "",
                        min_value=0.0,
                        value=float(o.take_profit),
                        key=f"tp_exec_{o.id}",
                        step=0.01,
                        format="%.4f",
                        label_visibility="collapsed"
                    )
                with cols[7]:
                    new_sl = st.number_input(
                        "",
                        min_value=0.0,
                        value=float(o.stop_loss),
                        key=f"sl_exec_{o.id}",
                        step=0.01,
                        format="%.4f",
                        label_visibility="collapsed"
                    )
                cols[8].write(o.stop_interval or "-")
                with cols[9]:
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("💾", key=f"update_exec_{o.id}"):
                            try:
                                adapter = adapters.get("binance")
                                if not adapter:
                                    st.error("Adapter Binance non configurato")
                                else:
                                    adapter.update_spot_tp_sl(
                                        o.symbol,
                                        o.quantity,
                                        new_tp,
                                        new_sl,
                                        user_id=user.id
                                    )
                                    o.take_profit = new_tp
                                    o.stop_loss = new_sl
                                    session.commit()
                                    st.success(f"TP/SL aggiornati su Binance per ordine {o.id}")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Errore aggiornamento su Binance: {e}")
                    with c2:
                        if st.button("❌", key=f"close_{o.id}"):
                            adapter = adapters.get("binance")
                            if not adapter:
                                st.error("Adapter Binance non configurato")
                            else:
                                try:
                                    adapter.close_position_market(o.symbol, float(o.quantity))
                                    o.status    = "CLOSED_MANUAL"
                                    o.closed_at = datetime.datetime.now(datetime.timezone.utc)
                                    session.commit()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Errore chiusura: {e}")




        st.markdown("---")
        # ----- TABELLA ORDINI CHIUSI -----
        st.subheader("Ordini CHIUSI")
        header_cols = st.columns([0.6,0.8,1.5,1,1.2,1.3,1.2,1.2,1,1,1.8,1.8,1])
        header_names = [
            "ID", "Side", "Simbolo", "Quantità", "Entry", "Prezzo Esecuzione", "TP", "SL",
            "TF Entry", "TF SL", "Data Apertura", "Data Chiusura", "Status"
        ]
        for col, name in zip(header_cols, header_names):
            col.markdown(f"**{name}**")

        closed_statuses = ["CLOSED_TP", "CLOSED_SL", "CLOSED_MANUAL", "CANCELLED"]
        closed = session.query(Order)\
            .filter(
                Order.user_id == user.id,
                Order.status.in_(closed_statuses)
            )\
            .order_by(Order.closed_at.desc())\
            .all()
        print("ORDINI CHIUSI TROVATI:", [o.id for o in closed])

        if not closed:
            st.write("Nessun ordine chiuso.")
        else:
            for o in closed:
                cols = st.columns([0.6,0.8,1.5,1,1.2,1.3,1.2,1.2,1,1,1.8,1.8,1])
                cols[0].write(o.id)
                cols[1].write(o.side)
                cols[2].write(o.symbol)
                cols[3].write(float(o.quantity))
                cols[4].write(float(o.entry_price))
                cols[5].write(float(o.executed_price) if o.executed_price else "-")
                cols[6].write(float(o.take_profit))
                cols[7].write(float(o.stop_loss))
                cols[8].write(o.entry_interval)
                cols[9].write(o.stop_interval or "-")
                cols[10].write(o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "-")
                cols[11].write(o.closed_at.strftime("%Y-%m-%d %H:%M") if o.closed_at else "-")
                cols[12].write(o.status)

