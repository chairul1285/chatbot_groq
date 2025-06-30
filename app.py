from flask import Flask, request, render_template
import pickle, os, requests
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

app = Flask(__name__)

# --- Fungsi Download dari Google Drive ---
def download_file_from_google_drive(file_id, destination):
    URL = "https://docs.google.com/uc?export=download"
    session = requests.Session()

    response = session.get(URL, params={'id': file_id}, stream=True)

    def get_confirm_token(response):
        for key, value in response.cookies.items():
            if key.startswith('download_warning'):
                return value
        return None

    token = get_confirm_token(response)
    if token:
        response = session.get(URL, params={'id': file_id, 'confirm': token}, stream=True)

    os.makedirs(os.path.dirname(destination), exist_ok=True)

    with open(destination, 'wb') as f:
        for chunk in response.iter_content(32768):
            if chunk:
                f.write(chunk)

# Unduh vectorstore jika belum ada
if not os.path.exists(VECTORSTORE_PATH):
    print("Mengunduh vectorstore.pkl dari Google Drive...")
    download_file_from_google_drive(VECTORSTORE_ID, VECTORSTORE_PATH)
    print("Unduhan selesai.")

# Load vectorstore
try:
    with open(VECTORSTORE_PATH, "rb") as f:
        vectorstore = pickle.load(f)

    # Optional: patch jika atribut hilang
    if hasattr(vectorstore, "embedding"):
        embedding_obj = vectorstore.embedding
        if not hasattr(embedding_obj, "show_progress"):
            setattr(embedding_obj, "show_progress", False)

except Exception as e:
    print("❌ Gagal membuka vectorstore.pkl:", e)
    vectorstore = None

# === Konfigurasi Groq LLM ===
llm = ChatGroq(
    temperature=0,
    model_name="llama3-8b-8192",
    groq_api_key="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"
)

# === Prompt LangChain ===
system_prompt = (
    "Anda adalah asisten untuk menjawab pertanyaan tentang administrasi kependudukan. "
    "Gunakan informasi dari konteks untuk menjawab dengan jelas, ringkas, dan dalam bahasa Indonesia. "
    "Jika tidak yakin, katakan 'mohon maaf saya tidak tahu, saya hanya akan menjawab terkait administrasi kependudukan'. "
    "Jawaban maksimal empat kalimat.\n\n"
    "{context}"
)

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{question}")
])

output_parser = StrOutputParser()

# --- RAG Function ---
def rag_chain_manual(question):
    try:
        if vectorstore is None:
            return "Data chatbot belum tersedia. Silakan coba lagi nanti."

        docs = vectorstore.similarity_search(question, k=4)
        context = "\n\n".join([doc.page_content for doc in docs])
        prompt = chat_prompt.format(context=context, question=question)
        response = llm.invoke(prompt)
        final_answer = output_parser.invoke(response)

        # Tambahkan link hanya jika konteksnya relevan DAN belum ditambahkan
        if "formulir" in final_answer.lower():
            final_answer += (
            '<br><br>📄 Silakan unduh formulir di sini: '
            '<a href="http://203.194.112.181:5000/#download" target="_blank">disdukcapil.batangkab.go.id</a>'
            )

        if "alamat" in final_answer.lower():
            final_answer += (
            '<br><br>📍 Alamat Disdukcapil Batang bisa dilihat di Google Maps: '
            '<a href="https://www.google.com/maps/place/Dinas+Kependudukan+dan+Pencatatan+Sipil+(DISDUKCAPIL)+Kabupaten+Batang/@-6.9158304,109.7216395" target="_blank">Lihat di Google Maps</a>'
            )
        return final_answer    

    except Exception as e:
        return f"Terjadi kesalahan: {str(e)}"

# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

@app.route("/get", methods=["POST"])
def get_bot_response():
    user_input = request.form.get("msg")
    if not user_input:
        return "Pertanyaan kosong."

    greetings = {
        'hai', 'halo', 'hi', 'hello',
        'assalamualaikum', 'selamat pagi', 'selamat siang', 'selamat malam',
        'terima kasih', 'makasih', 'thanks', 'thank you',
        'ok', 'oke', 'baik', 'sip'
    }
    if user_input.strip().lower() in greetings:
        return "Terima kasih, ada yang bisa kami bantu?"

    if not is_valid_question(user_input):
        return "Mohon maaf, saya hanya bisa menjawab pertanyaan terkait administrasi kependudukan."

    return rag_chain_manual(user_input)

# --- Run Server ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))  # default ke 5000 jika PORT tidak disetel
    app.run(host='0.0.0.0', port=port)
