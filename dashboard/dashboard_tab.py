import streamlit as st
import pandas as pd
import datetime
from pathlib import Path

from binance.client import Client
from src.core_and_scheduler import fetch_last_closed_candle
from symbols import SYMBOLS
from models import Order
from src.adapters import BinanceAdapter, BybitAdapter

# Mapping timeframe -> (Binance interval, millisecondi)
INTERVAL_MAP = {
    'M5':    ('5m',    5 * 60 * 1000),
    'H1':    ('1h',    1 * 3600 * 1000),
    'H4':    ('4h',    4 * 3600 * 1000),
    'Daily': ('1d',   24 * 3600 * 1000),
}

APP_NAME = "Crypto MultiBot"  # scegli il nome che preferisci
MAIN_ASSET = "USDC"


def show_dashboard_tab(tab, user, adapters, session):
    with tab:

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
        try:
            adapter = adapters[selected_exchange]
            balance = adapter.get_balance(MAIN_ASSET)
            st.sidebar.write(f"**{MAIN_ASSET}: {balance:,.2f}**")
        except Exception as e:
            st.sidebar.warning("Saldo non disponibile")

        st.sidebar.subheader("Nuovo Trade")
        with st.sidebar.form("trade_form", clear_on_submit=True):
            symbols_filtered = [s for s in SYMBOLS if s.endswith("USDC")]
            symbol = st.selectbox("Simbolo", symbols_filtered)
            quantity = st.number_input("Quantità", min_value=0.0, format="%.4f")
            entry_price = st.number_input("Entry Price", min_value=0.0, format="%.2f")
            max_entry = st.number_input(
                "Max Entry Price (annulla oltre)",
                min_value=entry_price,
                format="%.2f",
                help="Se la candela close > questo, il segnale verrà annullato"
            )
            entry_interval = st.selectbox("Entry Interval", list(INTERVAL_MAP.keys()))
            take_profit = st.number_input("Take Profit", min_value=0.0, format="%.2f")
            stop_loss = st.number_input("Stop Loss", min_value=0.0, format="%.2f")
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
                    if last_close > max_entry:
                        st.error(f"❌ Candela {entry_interval} ({last_close:.2f}) > Max Entry; segnale annullato.")
                    elif last_close >= take_profit:
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
                        session.commit()
                        st.success("✅ Trade aggiunto come PENDING")
                        st.rerun()

        # ----------- QUERY E TABELLE ORDINI -----------
        pending  = session.query(Order).filter_by(user_id=user.id, status="PENDING").all()
        executed = session.query(Order).filter_by(user_id=user.id, status="EXECUTED").all()

        # ----- TABELLA ORDINI PENDING -----
        st.subheader("Ordini PENDING")
        header_cols = st.columns([0.6,0.8,1.5,1,1.2,1.2,1.2,1.2,1,1.8,0.6])
        header_names = [
            "ID", "Side", "Simbolo", "Quantità", "Entry", "Max Entry", "TP", "SL", "TF Entry", "Data creazione", "❌"
        ]
        for col, name in zip(header_cols, header_names):
            col.markdown(f"**{name}**")

        if not pending:
            st.write("Nessun ordine pendente.")
        else:
            for o in pending:
                cols = st.columns([0.6,0.8,1.5,1,1.2,1.2,1.2,1.2,1,1.8,0.6])
                cols[0].write(o.id)
                cols[1].write(o.side)
                cols[2].write(o.symbol)
                cols[3].write(float(o.quantity))
                cols[4].write(float(o.entry_price))
                cols[5].write(float(o.max_entry) if o.max_entry else "-")
                cols[6].write(float(o.take_profit))
                cols[7].write(float(o.stop_loss))
                cols[8].write(o.entry_interval)
                cols[9].write(o.created_at.strftime("%Y-%m-%d %H:%M"))
                if cols[10].button("❌", key=f"cancel_{o.id}"):
                    o.status = "CANCELLED"  # oppure "CLOSED_MANUAL" se vuoi unificare lo status
                    o.closed_at = datetime.datetime.now(datetime.timezone.utc)
                    print(f"Ordine {o.id} cancellato, status: {o.status}, closed_at: {o.closed_at}")
                    session.commit()
                    st.rerun()
        st.markdown("---")

        # ----- TABELLA ORDINI ESEGUITI (A MERCATO) -----
        st.subheader("Ordini A MERCATO")
        header_cols = st.columns([0.6,0.8,1.5,1,1.3,1.8,1.3,1.3,1,0.6])
        header_names = [
            "ID", "Side", "Simbolo", "Quantità", "Prezzo Esecuzione", "Data Esecuzione", "TP", "SL", "TF SL", "❌"
        ]
        for col, name in zip(header_cols, header_names):
            col.markdown(f"**{name}**")

        if not executed:
            st.write("Nessun ordine eseguito.")
        else:
            for o in executed:
                cols = st.columns([0.6,0.8,1.5,1,1.3,1.8,1.3,1.3,1,0.6])
                cols[0].write(o.id)
                cols[1].write(o.side)
                cols[2].write(o.symbol)
                cols[3].write(float(o.quantity))
                cols[4].write(float(o.executed_price or 0))
                cols[5].write(o.executed_at.strftime("%Y-%m-%d %H:%M") if o.executed_at else "-")
                cols[6].write(float(o.take_profit))
                cols[7].write(float(o.stop_loss))
                cols[8].write(o.stop_interval or "-")
                if cols[9].button("❌", key=f"close_{o.id}"):
                    adapter = adapters.get("binance")
                    if not adapter:
                        st.error("Adapter Binance non configurato")
                    else:
                        try:
                            adapter.close_position_market(o.symbol, float(o.quantity))
                            o.status    = "CLOSED_MANUAL"
                            o.closed_at = datetime.datetime.now(datetime.timezone.utc)
                            print(f"Sto chiudendo l'ordine {o.id}, status {o.status}, closed_at {o.closed_at}")
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

