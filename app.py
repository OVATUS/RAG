import streamlit as st
from hybrid_rag import HybridRAG

# TODO 5A: ตั้งค่า Streamlit page
st.set_page_config(page_title="Coding Assistant", page_icon="🤖", layout="wide")

# TODO 5B: โหลด RAG engine ด้วย st.cache_resource
@st.cache_resource
def load_rag():
    try:
        return HybridRAG()
    except Exception as e:
        st.error(f"ระบบยังไม่พร้อม: {e} (กรุณารัน setup.py ก่อน)")
        return None

rag = load_rag()

# TODO 5C: ตั้งค่า session state สำหรับ chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("🤖 Coding Assistant")
    st.markdown("ถามคำถามเกี่ยวกับโค้ดในโปรเจกต์ของคุณ")
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# TODO 5D: สร้าง chat input และ query handler
if prompt := st.chat_input("Ask about your codebase..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if rag is None:
            st.error("Error: RAG Engine not loaded.")
        else:
            with st.spinner("Searching codebase..."):
                result = rag.query(prompt)
                answer = result["answer"]
                mode = result["source"]
                sources = result.get("docs", [])

            st.markdown(answer)
            st.caption(f"Mode: {'🔗 Graph' if mode == 'graph' else '🔍 Vector'}")

            # แสดง sources ใน expander
            if sources:
                with st.expander(f"📎 Sources ({len(sources)} chunks)"):
                    for src in sources:
                        st.code(f"File: {src.get('file', '?')}\nFunction: {src.get('function', '?')}")

    st.session_state.messages.append({"role": "assistant", "content": answer})