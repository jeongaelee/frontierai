import streamlit as st  
import requests  
import uuid  
import os  
import json, threading, time
from msal_streamlit import login  
from dotenv import load_dotenv  
try:
    import websocket  # websocket-client
except ImportError:
    websocket = None
  
load_dotenv()  
  
BASE_BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:7000")  
CHAT_URL = f"{BASE_BACKEND_URL}/chat"  
HISTORY_URL = f"{BASE_BACKEND_URL}/history"  
SESSION_RESET_URL = f"{BASE_BACKEND_URL}/reset_session"  
WS_URL = BASE_BACKEND_URL.replace("http", "ws") + "/ws/chat"
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "true").lower() in ("1", "true", "yes")
  
# ───────────────── helpers ──────────────────  
def auth_headers() -> dict:  
    tok = st.session_state.get("token")  
    return {"Authorization": f"Bearer {tok}"} if tok else {}  
  
# ───────────────── Sidebar ──────────────────  
with st.sidebar:  
    if "token" not in st.session_state:
        st.session_state.token = None

    if DISABLE_AUTH:
        # Auto-provision a pseudo token so rest of UI works
        if not st.session_state.token:
            st.session_state.token = "dev-local-token"
        st.success("Auth disabled (DEV mode)")
    else:
        login_btn = st.button("🔐  Sign-in", disabled=bool(st.session_state.token))  
        if login_btn:  
            st.session_state.token = login()  
            st.write(st.session_state.get("token"))  
        st.write("Signed-in" if st.session_state.token else "Not signed-in")  
        if st.button("🚪 Sign out", disabled=not st.session_state.token):  
            st.session_state.token = None  
            if "session_id" in st.session_state:  
                st.session_state["session_id"] = str(uuid.uuid4())  
            st.success("Signed out.")  

    st.title("⚙️  Controls")  
    if st.button("🗘  New chat", key="new_chat") and st.session_state.get("session_id"):  
        requests.post(  
            SESSION_RESET_URL,  
            json={"session_id": st.session_state["session_id"]},  
            headers=auth_headers(),  
            timeout=20,  
        )  
  
# ───────────────── Page title ────────────────  
st.markdown(  
    "<h1 style='display:flex; align-items:center;'>AI Chat Assistant 🤖</h1>",  
    unsafe_allow_html=True,  
)  
  
# ───────────── Load or initialize session ────────────────  
if "session_id" not in st.session_state:  
    st.session_state["session_id"] = str(uuid.uuid4())  
  
conversation_history = []  
  
# Fetch existing history from backend  
if st.session_state.token:  
    try:  
        response = requests.get(  
            f"{HISTORY_URL}/{st.session_state['session_id']}",  
            headers=auth_headers(),  
            timeout=20,  
        )  
        if response.status_code == 200:  
            history_data = response.json()  
            conversation_history = history_data.get("history", [])  
    except Exception:  
        pass  
  
# ───────────────── Chat history ─────────────  
for msg in conversation_history:  
    with st.chat_message(msg["role"]):  
        st.markdown(msg["content"])  
  
# ───────────────── WebSocket support ─────────────
if "ws_events" not in st.session_state:
    st.session_state.ws_events = []
if "ws_connected" not in st.session_state:
    st.session_state.ws_connected = False
if "ws" not in st.session_state:
    st.session_state.ws = None
if "ws_started" not in st.session_state:
    st.session_state.ws_started = False
if "_last_ws_append_ts" not in st.session_state:
    st.session_state._last_ws_append_ts = 0.0

def _ensure_ws():
    if websocket is None:
        return False
    if st.session_state.ws_connected:
        return True
    if st.session_state.ws_started:
        return True
    def on_message(ws, message):
        print(f"[WS] Received message: {message[:100]}...")  # Debug log
        try:
            data = json.loads(message)
        except Exception:
            return
        if "ws_events" not in st.session_state:
            st.session_state["ws_events"] = []
        st.session_state.ws_events.append(data)
        # Debounce reruns (max 5 per second)
        import time as _t
        now = _t.time()
        if now - st.session_state._last_ws_append_ts > 0.2:
            st.session_state._last_ws_append_ts = now
            st.experimental_rerun()
    def on_error(ws, err):
        if "ws_events" not in st.session_state:
            st.session_state["ws_events"] = []
        st.session_state.ws_events.append({"type": "error", "message": str(err)})
    def on_close(ws, code, msg):
        st.session_state.ws_connected = False
        if "ws_events" not in st.session_state:
            st.session_state["ws_events"] = []
        st.session_state.ws_events.append({"type": "info", "message": "WebSocket closed"})
    def on_open(ws):
        st.session_state.ws_connected = True
        # register session (no prompt)
        payload = {"session_id": st.session_state["session_id"], "access_token": st.session_state.get("token")}
        ws.send(json.dumps(payload))
        if "ws_events" not in st.session_state:
            st.session_state["ws_events"] = []
        st.session_state.ws_events.append({"type": "info", "message": "WebSocket connected"})
        print(f"[WS] Connected for session {st.session_state['session_id']}")  # Debug log
    def run_ws():
        headers = []
        tok = st.session_state.get("token")
        if tok:
            headers.append(f"Authorization: Bearer {tok}")
        ws_app = websocket.WebSocketApp(
            WS_URL,
            header=headers,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        st.session_state.ws = ws_app
        ws_app.run_forever(ping_interval=25, ping_timeout=10)
    threading.Thread(target=run_ws, daemon=True).start()
    st.session_state.ws_started = True
    # brief wait
    time.sleep(0.2)
    return True

# Start WebSocket connection immediately when token is available
if st.session_state.token and not st.session_state.ws_started:
    _ensure_ws()

def send_ws_prompt(prompt: str) -> bool:
    # Ensure connection is ready
    if not _ensure_ws():
        st.warning("⚠️ WebSocket not available, using REST fallback")
        return False
    
    # Wait for connection
    for i in range(40):
        if st.session_state.ws_connected:
            break
        time.sleep(0.05)
    
    if not st.session_state.ws_connected:
        st.warning(f"⚠️ WebSocket connection timeout after 2s, using REST fallback")
        return False
    
    payload = {
        "session_id": st.session_state["session_id"],
        "prompt": prompt,
        "access_token": st.session_state.get("token"),
    }
    try:
        st.session_state.ws.send(json.dumps(payload))
        st.info("✅ Sent via WebSocket - watch for streaming updates below...")
        return True
    except Exception as e:
        st.session_state.ws_events.append({"type": "error", "message": f"Send failed: {e}"})
        st.error(f"❌ WebSocket send failed: {e}")
        return False

# Render pushed events (after existing REST history)
for ev in st.session_state.ws_events:
    t = ev.get("type")
    if t == "token":
        with st.chat_message("assistant"):
            st.markdown(ev.get("content", ""))
    elif t in ("message", "final"):
        with st.chat_message("assistant"):
            st.markdown(ev.get("content", ""))
    elif t == "tool_call":
        with st.chat_message("assistant"):
            st.markdown(f"🔧 Tool call: {ev.get('calls')}")
    elif t == "tool_result":
        for r in ev.get("results", []):
            with st.chat_message("assistant"):
                st.markdown(f"✅ {r.get('content')}")
    # Magentic-specific events
    elif t == "orchestrator":
        kind = ev.get("kind", "plan")
        icon = "🧠" if kind == "plan" else "📊" if kind == "progress" else "✅"
        with st.chat_message("assistant"):
            st.markdown(f"{icon} **Orchestrator {kind.upper()}**")
            st.markdown(ev.get("content", ""))
    elif t == "agent_start":
        agent_name = ev.get("agent_id", "unknown").replace("_", " ").title()
        with st.chat_message("assistant"):
            st.info(f"🤖 **{agent_name}** is working...")
    elif t == "agent_token":
        agent_name = ev.get("agent_id", "unknown").replace("_", " ").title()
        with st.chat_message("assistant"):
            st.write(f"💬 {agent_name}: {ev.get('content', '')}")
    elif t == "agent_message":
        agent_name = ev.get("agent_id", "unknown").replace("_", " ").title()
        with st.chat_message("assistant"):
            st.markdown(f"**{agent_name}:**")
            st.markdown(ev.get("content", ""))
    elif t == "final_result":
        with st.chat_message("assistant"):
            st.success("✅ Final Answer")
            st.markdown(ev.get("content", ""))
    elif t == "error":
        st.error(ev.get("message"))
    elif t == "info":
        st.caption(ev.get("message"))

st.divider()

# ───────────────── Chat interaction (WS preferred, REST fallback) ─────────────  
prompt = st.chat_input("Type a message..." if st.session_state.token else "Sign-in to chat…")  
if prompt and st.session_state.token:  
    with st.chat_message("user"):  
        st.markdown(prompt)  
    used_ws = send_ws_prompt(prompt)
    if not used_ws:
        with st.spinner("Assistant (REST)…"):
            r = requests.post(
                CHAT_URL,
                json={"session_id": st.session_state["session_id"], "prompt": prompt},
                headers=auth_headers(),
                timeout=180,  # Increased from 60s to 180s for multi-agent workflows
            )
            r.raise_for_status()
            answer = r.json()["response"]
        with st.chat_message("assistant"):
            st.markdown(answer)