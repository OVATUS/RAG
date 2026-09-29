```markdown
# 🤖 Local Coding Assistant (Hybrid RAG)

ระบบ AI ผู้ช่วยวิเคราะห์โค้ดแบบทำงานบนเครื่อง 100% (Local) โดยใช้สถาปัตยกรรม **Hybrid RAG** ที่ผสานการทำงานระหว่าง **Vector Search (FAISS)** เพื่อค้นหาความหมาย และ **Graph Database (Kuzu)** เพื่อสืบค้นโครงสร้างความสัมพันธ์ของโค้ด

## 🛠 Tech Stack
- **Environment:** `uv` (Pinned to Python 3.12)
- **UI:** Streamlit
- **LLM & Embeddings:** Ollama (`qwen2.5-coder:7b` และ `nomic-embed-text`)
- **Database:** FAISS (Vector DB), Kuzu (Graph DB)

## 📋 Prerequisites (สิ่งที่ต้องมีก่อนเริ่ม)
1. **[uv](https://docs.astral.sh/uv/getting-started/installation/)**: สำหรับจัดการ Python Environment ให้รวดเร็ว
2. **[Ollama](https://ollama.com/)**: สำหรับรัน AI Model ภายในเครื่อง

---

## 🚀 Setup & Installation (วิธีติดตั้ง)

**1. Clone the repository**
```bash
git clone https://github.com/OVATUS/RAG.git
cd <ชื่อโฟลเดอร์_REPO>

```

**2. ติดตั้ง Dependencies**
โปรเจกต์นี้ใช้ `uv` ในการจัดการแพ็กเกจ (บังคับใช้ Python 3.12 เพื่อให้รองรับ Kuzu) รันคำสั่งเดียวเพื่อซิงค์ไลบรารีทั้งหมดจากไฟล์ `uv.lock`:

```bash
uv sync
```

**3. ดาวน์โหลด AI Models (Ollama)**
เปิด Terminal/PowerShell แล้วรันคำสั่งเพื่อโหลดโมเดลภาษาและโมเดลทำเวกเตอร์:

```bash
ollama pull qwen2.5-coder:7b
ollama pull nomic-embed-text
```

*(หมายเหตุ: ต้องรันโปรแกรม Ollama ทิ้งไว้เบื้องหลังเสมอขณะใช้งานระบบ)*
---
## 💡 How to Use (วิธีใช้งาน)

**Step 1: เตรียมชุดข้อมูล (Dataset)**
นำไฟล์โค้ด Python (`.py`) ที่ต้องการให้ AI ช่วยวิเคราะห์ ไปใส่ไว้ในโฟลเดอร์ `my_dataset/`

**Step 2: สร้างฐานข้อมูล (Indexing)**
รันคำสั่งด้านล่างเพื่อสแกนโค้ด ระบบจะสร้างโฟลเดอร์ `vector_db` และ `graph_db` ขึ้นมาอัตโนมัติ:

```bash
uv run python setup.py
```

**Step 3: เปิดหน้าจอ UI**
เมื่อฐานข้อมูลพร้อมแล้ว ให้รันคำสั่งนี้เพื่อเปิดหน้าต่าง Streamlit Chat บนเบราว์เซอร์:

```bash
uv run streamlit run app.py
```
## 📁 Project Structure

* `setup.py`: สคริปต์สแกนโค้ด (AST) และแปลงข้อมูลลง FAISS / Kuzu
* `hybrid_rag.py`: ระบบ Backend (Question Router) ที่สับรางคำถามไปยังโหมด Vector หรือ Graph อัตโนมัติ
* `app.py`: หน้าจอติดต่อผู้ใช้ (Streamlit)
* `my_dataset/`: โฟลเดอร์สำหรับวางไฟล์โค้ดต้นฉบับ
