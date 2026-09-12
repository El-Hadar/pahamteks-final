from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import json
import time
import random
import os

app = Flask(__name__)
CORS(app)

# Konfigurasi Gemini dari Environment Variable Vercel
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-3.6-flash')

# Cache untuk menyimpan soal kuis sementara agar lebih cepat dimuat ulang
quiz_cache = {}

# --- SISTEM DATABASE MEMORI & OTP ---
users_db = {}
otp_db = {}  # Database sementara untuk menyimpan kode OTP

@app.route('/api/send_otp', methods=['POST'])
def send_otp():
    data = request.json
    email = data.get('email', '').strip()
    
    if not email:
        return jsonify({'error': 'Email wajib diisi!'}), 400
    if email in users_db:
        return jsonify({'error': 'Email sudah terdaftar! Silakan Sign In.'}), 400
        
    # Simulasi pengiriman OTP (Di sistem nyata menggunakan SMTP/SendGrid)
    otp_db[email] = "123456" 
    return jsonify({'message': 'Kode verifikasi telah dikirim ke email Anda!'})

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    fname = data.get('fname', '').strip()
    lname = data.get('lname', '').strip()
    oname = data.get('oname', '').strip()
    otp_code = data.get('otp', '').strip()
    
    if not email or not password or not fname or not lname:
        return jsonify({'error': 'Nama Depan, Belakang, Email, dan Sandi wajib diisi!'}), 400
        
    # Validasi OTP
    if email not in otp_db or otp_db[email] != otp_code:
        return jsonify({'error': 'Kode OTP salah atau kedaluwarsa!'}), 400
        
    if email in users_db:
        return jsonify({'error': 'Email sudah terdaftar!'}), 400
        
    # Gabungkan nama (Nama Tambahan opsional)
    full_name = f"{fname} {lname}"
    if oname: 
        full_name += f" {oname}"
        
    users_db[email] = {'name': full_name, 'password': password}
    del otp_db[email] # Bersihkan OTP setelah sukses terdaftar
    
    return jsonify({'message': 'Verifikasi sukses! Pendaftaran berhasil.', 'name': full_name})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    
    if email not in users_db:
        return jsonify({'error': 'Email tidak ditemukan!'}), 400
        
    if users_db[email]['password'] != password:
        return jsonify({'error': 'Kata sandi salah!'}), 400
        
    return jsonify({'message': 'Login berhasil!', 'name': users_db[email]['name']})

# --- SERVER LOGS TRACKING ---
@app.route('/api/user_log', methods=['POST'])
def user_log():
    data = request.json
    user_identifier = data.get('user', 'Tamu')
    activity = data.get('activity', '')
    score = data.get('score', 0)
    category = data.get('category', 'General')
    
    print(f"[SERVER LOG TRACKER] User: {user_identifier} | Kategori: {category} | Aktivitas: {activity} | Skor: {score}")
    return jsonify({'status': 'logged', 'message': 'Aktivitas berhasil dicatat di server.'})

# --- DAFTAR LENGKAP BAHASA DUNIA ---
LANGUAGES = {
    "afrikaans": "af", "albanian": "sq", "amharic": "am", "arabic": "ar", "armenian": "hy", "azerbaijani": "az",
    "basque": "eu", "belarusian": "be", "bengali": "bn", "bosnian": "bs", "bulgarian": "bg", "catalan": "ca",
    "cebuano": "ceb", "chichewa": "ny", "chinese (simplified)": "zh-cn", "chinese (traditional)": "zh-tw",
    "corsican": "co", "croatian": "hr", "czech": "cs", "danish": "da", "dutch": "nl", "english": "en",
    "esperanto": "eo", "estonian": "et", "filipino": "tl", "finnish": "fi", "french": "fr", "frisian": "fy",
    "galician": "gl", "georgian": "ka", "german": "de", "greek": "el", "gujarati": "gu", "haitian creole": "ht",
    "hausa": "ha", "hawaiian": "haw", "hebrew": "he", "hindi": "hi", "hmong": "hmn", "hungarian": "hu",
    "icelandic": "is", "igbo": "ig", "indonesian": "id", "irish": "ga", "italian": "it", "japanese": "ja",
    "javanese": "jw", "kannada": "kn", "kazakh": "kk", "khmer": "km", "korean": "ko", "kurdish (kurmanji)": "ku",
    "kyrgyz": "ky", "lao": "lo", "latin": "la", "latvian": "lv", "lithuanian": "lt", "luxembourgish": "lb",
    "macedonian": "mk", "malagasy": "mg", "malay": "ms", "malayalam": "ml", "maltese": "mt", "maori": "mi",
    "marathi": "mr", "mongolian": "mn", "myanmar (burmese)": "my", "nepali": "ne", "norwegian": "no",
    "pashto": "ps", "persian": "fa", "polish": "pl", "portuguese": "pt", "punjabi": "pa", "romanian": "ro",
    "russian": "ru", "samoan": "sm", "scots gaelic": "gd", "serbian": "sr", "sesotho": "st", "shona": "sn",
    "sindhi": "sd", "sinhala": "si", "slovak": "sk", "slovenian": "sl", "somali": "so", "spanish": "es",
    "sundanese": "su", "swahili": "sw", "swedish": "sv", "tajik": "tg", "tamil": "ta", "telugu": "te",
    "thai": "th", "turkish": "tr", "ukrainian": "uk", "urdu": "ur", "uzbek": "uz", "vietnamese": "vi",
    "welsh": "cy", "xhosa": "xh", "yiddish": "yi", "yoruba": "yo", "zulu": "zu"
}

def generate_with_retry(prompt, max_retries=3, sleep_time=20):
    for attempt in range(max_retries):
        try:
            return model.generate_content(prompt)
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower():
                if attempt < max_retries - 1:
                    time.sleep(sleep_time)
                    continue 
                else:
                    raise Exception("Tutor AI kami sedang diakses oleh banyak murid secara bersamaan saat ini. Yuk, rehatkan mata sejenak sekitar 1 menit, lalu coba lagi ya! ☕")
            else:
                raise e

@app.route('/api/languages', methods=['GET'])
def get_languages():
    return jsonify(LANGUAGES)

@app.route('/api/translate', methods=['POST'])
def translate_text():
    data = request.json
    if not data or 'text' not in data:
        return jsonify({'error': 'Teks tidak ditemukan'}), 400
        
    teks = data.get('text', '').strip()
    source_lang = data.get('source', 'auto')
    target_lang = data.get('target', 'en')
    
    if not teks: return jsonify({'translated_text': ''})

    source_name = "Auto Detect"
    target_name = "English"
    for name, code in LANGUAGES.items():
        if code == source_lang: source_name = name
        if code == target_lang: target_name = name
            
    try:
        prompt = f"""
        Translate this text from {source_name} to {target_name}: "{teks}"
        Keep slang/idioms natural. Do not explain.
        CRITICAL RULE: If {target_name} uses a non-Latin script, output EXACTLY in this format:
        [Native Script]
        
        [Latin Pronunciation/Romaji]
        """
        response = generate_with_retry(prompt)
        return jsonify({'translated_text': response.text.strip().strip('"')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_quiz', methods=['POST'])
def generate_quiz():
    data = request.json
    categories = data.get('categories', [])
    level = data.get('level', 'Pemula')
    
    cache_key = f"{level}_{'_'.join(categories)}"
    
    if cache_key in quiz_cache:
        cached_data = quiz_cache[cache_key].copy()
        random.shuffle(cached_data) 
        return jsonify(cached_data)
        
    prompt = f"""
    Buat 5 soal kuis {level} untuk materi: {', '.join(categories)}.
    Format WAJIB JSON Array utuh tanpa markdown (```).
    Bentuk JSON:
    [{{ "instruction": "Perintah", "question": "Soal", "options": ["A", "B", "C", "D"], "answer": "Jawaban" }}]
    """
    
    try:
        response = generate_with_retry(prompt)
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").strip("json").strip("html").strip()
            
        quiz_data = json.loads(raw_text)
        quiz_cache[cache_key] = quiz_data
        return jsonify(quiz_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_challenge', methods=['POST'])
def generate_challenge():
    data = request.json
    category = data.get('category', 'General')
    
    prompt = f"""
    Buat 3 soal ujian tantangan (Challenge Mode ber-timer) yang SANGAT SULIT & kompleks untuk topik: {category}.
    Soal harus berupa studi kasus menjebak atau analisis panjang berstandar profesional.
    Format WAJIB JSON Array utuh tanpa markdown (```).
    Bentuk JSON:
    [{{ "instruction": "Tantangan Analisis", "question": "Soal studi kasus...", "options": ["A", "B", "C", "D"], "answer": "Jawaban Benar" }}]
    """
    try:
        response = generate_with_retry(prompt)
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").strip("json").strip("html").strip()
        return jsonify(json.loads(raw_text))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/explain_answer', methods=['POST'])
def explain_answer():
    data = request.json
    pertanyaan = data.get('question', '')
    jawaban = data.get('answer', '')
    
    prompt = f"""
    Kamu adalah guru les profesional yang ramah. Murid sedang mengecek soal: "{pertanyaan}". Jawaban benar: "{jawaban}".
    Jelaskan dengan ringkas mengapa itu benar. 
    LALU, WAJIB akhiri dengan kalimat tanya santai seperti: "Apakah kamu udah paham soal pembahasan ini? Atau kamu ingin melihat kamus dulu?"
    """
    try:
        response = generate_with_retry(prompt)
        return jsonify({'explanation': response.text.strip()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat_tutor', methods=['POST'])
def chat_tutor():
    data = request.json
    user_msg = data.get('message', '')
    history = data.get('history', '')
    
    prompt = f"""
    Kamu adalah Tutor AI PahamTeks.
    Konteks percakapan sebelumnya: {history}
    Murid merespons: "{user_msg}"
    Berikan jawaban interaktif dan ramah. Jangan gunakan markdown tebal/miring berlebihan.
    """
    try:
        response = generate_with_retry(prompt)
        return jsonify({'reply': response.text.strip()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/dictionary', methods=['POST'])
def dictionary():
    data = request.json
    keyword = data.get('keyword', '')
    
    prompt = f"""
    Kamu adalah 'Kamus Pintar AI'. Pengguna mencari kata/istilah/konsep: "{keyword}".
    Berikan: 1. Definisi singkat. 2. Terjemahan/Fungsi. 3. Satu contoh penggunaan.
    Gunakan teks biasa yang rapi.
    """
    try:
        response = generate_with_retry(prompt)
        return jsonify({'result': response.text.strip()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
@app.route('/index.html')
def home():
    try:
        file_path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"<h1>Memuat Tampilan...</h1><p>Silakan muat ulang halaman. Error: {e}</p>"