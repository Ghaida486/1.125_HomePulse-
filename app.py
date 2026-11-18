"""HomePulse: monthly outlook, with the original annual app retained."""
from pathlib import Path
import streamlit as st

st.set_page_config(page_title="HomePulse",page_icon="🏠",layout="wide",initial_sidebar_state="collapsed")
with st.sidebar:
    st.markdown("### HomePulse")
    workspace = st.radio("Workspace",["Monthly home estimate","Original annual estimator"],key="homepulse_workspace")
    st.caption("Monthly outlook: state forecasts plus a survey-based home adjustment.")
if workspace == "Original annual estimator":
    legacy = Path(__file__).with_name("legacy_app.py")
    exec(compile(legacy.read_text(),str(legacy),"exec"),globals())
else:
    from homepulse.monthly_ui import render_monthly
    render_monthly()
