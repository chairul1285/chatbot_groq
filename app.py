from flask import Flask, request, render_template
import pickle, os
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

app = Flask(_name_)

# === Lokasi Vectorstore ===
VECTORSTORE_PATH = "chatbot/vectorstore.pkl"

# === Load vectorstore dari lokal ===
try:
    with open(VECTORSTORE_PATH, "rb") as f:
        vectorstore = pickle.load(f)

    # Patch jika atribut show_progress hilang
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

# === Prompt Template ===
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

# === Validasi Pertanyaan ===
def is_valid_question(question):
    question = question.strip().lower()
    greetings = {
        'hai', 'halo', 'hi', 'hello',
        'assalamualaikum', 'selamat pagi', 'selamat siang', 'selamat malam',
        'terima kasih', 'makasih', 'thanks', 'thank you',
        'ok', 'oke', 'baik', 'sip'
    }

    if question in greetings:
        return True

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

# === Proses Chat ===
def rag_chain_manual(question):
    try:
        if vectorstore is None:
            return "Data chatbot belum tersedia. Silakan coba lagi nanti."

        docs = vectorstore.similarity_search(question, k=4)
        context = "\n\n".join([doc.page_content for doc in docs])
        prompt = chat_prompt.format(context=context, question=question)
        response = llm.invoke(prompt)
        final_answer = output_parser.invoke(response)

        # Tambahkan link jika relevan
        if "formulir" in final_answer.lower():
            final_answer += (
                '<br><br>📄 Silakan unduh formulir di sini: '
                '<a href="http://localhost:5000/#download" target="_blank">disdukcapil.batangkab.go.id</a>'
            )
        if "alamat" in final_answer.lower():
            final_answer += (
                '<br><br>📍 Lihat lokasi di Google Maps: '
                '<a href="https://www.google.com/maps/place/Dinas+Kependudukan+dan+Pencatatan+Sipil+(DISDUKCAPIL)+Kabupaten+Batang/@-6.9158304,109.7216395" target="_blank">Google Maps</a>'
            )

        return final_answer

    except Exception as e:
        return f"❌ Terjadi kesalahan saat memproses: {str(e)}"

# === Routes ===
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

@app.route("/get", methods=["POST"])
def get_response():
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

# === Jalankan Aplikasi ===
if _name_ == "_main_":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)