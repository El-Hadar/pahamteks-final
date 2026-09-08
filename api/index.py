from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import json
import time
import random
import os

app = Flask(__name__)
CORS(app)

# PERUBAHAN PENTING: Kunci AI sekarang diambil dari brankas Vercel (Environment Variable)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-3.6-flash')

quiz_cache = {}

@app.route('/')
@app.route('/index.html')
def home():
    try:
        # Menyuruh Python mengambil file index.html di folder luar dan menampilkannya
        file_path = os.path.join(os.path.dirname(__file__), '..', 'index.html')
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"<h1>Tampilan sedang diproses...</h1><p>Silakan muat ulang (refresh) halaman ini. Error: {e}</p>"

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
    Khusus 'Bahasa Al-Qur'an', format question WAJIB:
    "<div style='font-size: 3.5rem; font-family: serif;' dir='rtl'>ARAB</div><div style='font-size: 1.4rem; color: #afafaf; margin-top: -5px;'>Latin</div>".
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
    Berikan jawaban interaktif dan ramah. Jika murid masih bingung, berikan contoh sederhana. Jika murid sudah paham, berikan apresiasi. Jangan gunakan markdown tebal/miring.
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
    Berikan: 1. Definisi singkat. 2. Terjemahan/Fungsi. 3. Satu contoh penggunaan dalam kalimat atau sintaks kode.
    Gunakan teks biasa yang rapi.
    """
    try:
        response = generate_with_retry(prompt)
        return jsonify({'result': response.text.strip()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
