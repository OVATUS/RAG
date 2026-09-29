import streamlit as st
from hybrid_rag import HybridRAG

# TODO 5A: ตั้งค่า Streamlit page
st.set_page_config(page_title="Coding Assistant", page_icon="🤖", layout="wide")


# TODO 5B: โหลด RAG engine ด้วย st.cache_resource
# ให้ raise error ออกมา (ไม่ return None) เพื่อไม่ให้ความล้มเหลวถูกแคชไว้จนต้องรีสตาร์ท
@st.cache_resource
def load_rag():
    return HybridRAG()


try:
    rag = load_rag()
except Exception as e:
    rag = None
    st.error(f"ระบบยังไม่พร้อม: {e} (กรุณารัน setup.py ก่อน และเปิด Ollama)")

# TODO 5C: ตั้งค่า session state สำหรับ chat history
if "messages" not in st.session_state:
    st.session_state.messages = []


def render_extras(mode, sources, graph_rows):
    st.caption(f"Mode: {'🔗 Graph' if mode == 'graph' else '🔍 Vector'}")
    if graph_rows:
        with st.expander(f"🔗 Graph relationships ({len(graph_rows)})"):
            st.code("\n".join(graph_rows))
    if sources:
        with st.expander(f"📎 Sources ({len(sources)} chunks)"):
            for src in sources:
                st.code(
                    f"File: {src.get('file', '?')}\n"
                    f"Function: {src.get('function', '?')} (line {src.get('line', '?')})"
                )


with st.sidebar:
    st.title("🤖 Coding Assistant")
    st.markdown("ถามคำถามเกี่ยวกับโค้ดในโปรเจกต์ของคุณ")
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_extras(message.get("mode"), message.get("sources"), message.get("graph_rows"))

# TODO 5D: สร้าง chat input และ query handler
if prompt := st.chat_input("Ask about your codebase..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if rag is None:
            st.error("Error: RAG Engine not loaded.")
        else:
            try:
                with st.spinner("Searching codebase..."):
                    result = rag.query(prompt)
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาดตอนค้นหา: {e}")
            else:
                st.markdown(result["answer"])
                render_extras(result["source"], result.get("docs"), result.get("graph_rows"))
                # เก็บลง history เฉพาะตอนตอบสำเร็จ (แก้ NameError เดิม)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "mode": result["source"],
                    "sources": result.get("docs"),
                    "graph_rows": result.get("graph_rows"),
                })