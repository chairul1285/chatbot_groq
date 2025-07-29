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

    with open(destination, 'wb') as f:
        for chunk in response.iter_content(32768):
            if chunk:
                f.write(chunk)

# --- Cek dan Unduh .pkl jika Belum Ada ---
VECTORSTORE_PATH = "chatbot/vectorstore.pkl"
VECTORSTORE_ID = "1bX3Moq7-rZg4IDFrSXvEsgtUU2FiA7Fy"  # Ganti dengan ID asli

if not os.path.exists(VECTORSTORE_PATH):
    print("Mengunduh vectorstore dari Google Drive...")
    download_file_from_google_drive(VECTORSTORE_ID, VECTORSTORE_PATH)

# --- Load Vectorstore ---
with open(VECTORSTORE_PATH, "rb") as f:
    vectorstore = pickle.load(f)

# --- Patch jika atribut show_progress hilang ---
if hasattr(vectorstore, "embedding"):
    embedding_obj = vectorstore.embedding
    if not hasattr(embedding_obj, "show_progress"):
        setattr(embedding_obj, "show_progress", False)

# --- Inisialisasi Groq LLM ---
llm = ChatGroq(
    temperature=0,
    model_name="llama3-8b-8192",
    groq_api_key="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"
)

# --- Prompt Sistem ---
system_prompt = (
    "Anda adalah Rojo, asisten virtual yang menjawab pertanyaan tentang administrasi kependudukan di Disdukcapil. "
    "Gunakan informasi dari konteks untuk menjawab sejelas dan seakurat mungkin. "
    "Jika informasi tidak ditemukan secara langsung, berikan jawaban terbaik berdasarkan pengetahuan umum tentang prosedur Disdukcapil. "
    "Jawaban maksimal 3–4 kalimat dalam bahasa Indonesia yang ramah, jelas, dan langsung ke inti jawaban. "
    "Jika memungkinkan, berikan jawaban dalam bentuk poin-poin, dan pisahkan setiap poin di baris baru menggunakan tanda '-'. "
    "Gunakan satu baris untuk setiap poin agar mudah dibaca.\n\n"
    "{context}"
)

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{question}")
])

output_parser = StrOutputParser()

# === Fungsi Deteksi Sapaan ===
def is_greeting(question):
    greetings = {
        'hai', 'halo', 'hi', 'hello',
        'assalamualaikum', 'assalamu’alaikum', 'assalamu alaikum',
        'selamat pagi', 'selamat siang', 'selamat sore', 'selamat malam',
        'terima kasih', 'makasih', 'thanks', 'thank you',
        'ok', 'oke', 'baik', 'sip'
    }
    return question.strip().lower() in greetings

# === Fungsi Validasi Pertanyaan (untuk LLM) ===
def is_valid_question(question):
    question = question.strip().lower()

    if len(question) < 4:
        return False
    if len(question.split()) == 1:
        meaningless = {'ya', 'tidak', 'enggak', 'loh', 'lah', 'hmm', 'eh'}
        if question in meaningless or len(question) <= 3:
            return False

    keywords = [
        'ktp', 'akta', 'kelahiran', 'kematian', 'kartu keluarga', 'kk', 'nik',
        'dukcapil', 'pelayanan', 'dokumen', 'perekaman', 'pengurusan',
        'formulir', 'online', 'alamat', 'jam buka', 'syarat'
    ]
    if not any(word in question for word in keywords):
        return False

    return True

# --- RAG Function ---
def rag_chain_manual(question):
    try:
        docs = vectorstore.similarity_search(question, k=4)
        context = "\n\n".join([doc.page_content for doc in docs])
        prompt = chat_prompt.format(context=context, question=question)
        response = llm.invoke(prompt)
        final_answer = output_parser.invoke(response)

        # Tambahkan link hanya jika konteksnya relevan DAN belum ditambahkan
        if "formulir" in final_answer.lower():
            final_answer += (
            '<br><br>📄 Silakan unduh formulir di sini: '
            '<a href="https://disdukcapil.batangkab.go.id/?p=6" target="_blank">disdukcapil.batangkab.go.id</a>'
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
    if is_greeting(user_input):
        return "Ada yang bisa saya bantu terkait layanan administrasi kependudukan?"

    if is_valid_question(user_input):
        return rag_chain_manual(user_input)
    else:
        return "Maaf, saya kurang memahami pertanyaan Anda. Silakan tulis pertanyaan yang lebih spesifik terkait layanan Dukcapil."

# --- Run Server ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))  # default ke 5000 jika PORT tidak disetel
    app.run(host='0.0.0.0', port=port)