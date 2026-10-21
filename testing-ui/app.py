import os
import requests
import streamlit as st

st.set_page_config(page_title="ProofPay AI · Developer dashboard", layout="wide")
st.title("ProofPay AI — Day 1 testing")
st.caption("Synthetic data only · In-memory mock backend · No AI processing")
base_url = st.text_input("Backend connection URL", value=os.getenv("BACKEND_URL", "http://127.0.0.1:8000")).rstrip("/")

def call_api(method, path, **kwargs):
    try:
        response = requests.request(method, base_url + path, timeout=10, **kwargs)
        try:
            data = response.json()
        except ValueError:
            st.error(f"Backend returned non-JSON content (HTTP {response.status_code}).")
            return None
        if not response.ok:
            st.error(f"API request failed (HTTP {response.status_code})")
            st.json(data)
            return None
        return data
    except requests.RequestException as exc:
        st.error(f"Cannot reach backend: {exc}")
        return None

health = call_api("GET", "/api/v1/health")
if health:
    st.success(f"Backend health: {health['status']} ({health['mode']})")
transactions = call_api("GET", "/api/v1/transactions")
if not transactions:
    st.info("No transactions available. Check the backend URL and connection.")
    st.stop()
transaction_id = st.selectbox("Synthetic transaction", [t["id"] for t in transactions])
context = (base_url, transaction_id)
if st.session_state.get("context") != context:
    st.session_state.context = context
    st.session_state.pop("job", None)
    st.session_state.pop("demo", None)
details = call_api("GET", f"/api/v1/transactions/{transaction_id}")
if details:
    st.subheader("Transaction details")
    st.json(details)
if st.button("Create mock analysis job"):
    st.session_state.job = call_api("POST", f"/api/v1/transactions/{transaction_id}/analyze", json={})
if st.session_state.get("job"):
    if st.button("Refresh job status"):
        st.session_state.job = call_api("GET", f"/api/v1/analysis/{st.session_state.job['analysis_id']}")
    st.info("Mock jobs remain queued until Member 2's pipeline is integrated.")
    st.json(st.session_state.job)
if st.button("Retrieve static demo analysis"):
    st.session_state.demo = call_api("GET", f"/api/v1/transactions/{transaction_id}/demo-analysis")
if st.session_state.get("demo"):
    st.subheader("Static demo findings — contract fixture")
    st.caption("These findings are synthetic; they are not results from the queued job.")
    for finding in st.session_state.demo["findings"]:
        with st.container(border=True):
            st.write(f"Issue: {finding['issue_type']}")
            st.write(f"Severity: {finding['severity']}")
            st.write(finding["explanation"])
            st.write("Source IDs: " + ", ".join(finding["source_ids"]))
            st.write("Recommendation: " + finding["recommendation"])
