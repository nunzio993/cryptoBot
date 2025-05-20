# file: dashboard/logs.py
import streamlit as st
from pathlib import Path
LOG_PATH = Path('logs') / 'scheduler.log'

def show_logs_tab(tab):
    with tab:
        st.markdown('---')
        st.subheader('Logs')
        if LOG_PATH.exists():
            lines = LOG_PATH.read_text().splitlines()[-100:]
        else:
            lines = [f'Log file non trovato: {LOG_PATH}']
        st.text_area('Ultime 100 righe', value="\n".join(lines), height=400)

