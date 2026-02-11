from flask import Flask, request, render_template, jsonify, send_from_directory, send_file
import os
import json
import time
import shutil
import numpy as np
import librosa
import soundfile as sf
import warnings
from io import BytesIO
import threading

# ML/AI Imports
import whisper
from transformers import pipeline
from deep_translator import GoogleTranslator
from fpdf import FPDF
import imageio_ffmpeg

warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

# -------------------- Configuration --------------------
app = Flask(__name__, 
            template_folder="../frontend/templates",
            static_folder="../frontend/static")

app.secret_key = "TranscribeFlow_Secret_Key" # Keep it simple for local dev
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024 # 200MB limit

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {"mp3", "wav", "mp4", "mov", "m4a"}

# -------------------- FFMPEG Configuration --------------------
# Ensure ffmpeg is available for Whisper
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
ffmpeg_dir = os.path.dirname(ffmpeg_exe)
target_ffmpeg = os.path.join(ffmpeg_dir, "ffmpeg.exe")

if not os.path.exists(target_ffmpeg):
    try:
        shutil.copy(ffmpeg_exe, target_ffmpeg)
    except Exception as e:
        print(f"Failed to copy ffmpeg: {e}")

os.environ["PATH"] += os.pathsep + ffmpeg_dir

# -------------------- Model Initialization (Lazy Loading) --------------------
asr_model = None
summarizer = None

def get_asr_model():
    global asr_model
    if asr_model is None:
        print("Loading Whisper Model...")
        asr_model = whisper.load_model("base")
    return asr_model

def get_summarizer():
    global summarizer
    if summarizer is None:
        print("Loading Summarization Model...")
        summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    return summarizer

# -------------------- Helper Functions --------------------

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def calculate_sonic_dna(audio_path, transcript):
    """
    Calculates Energy, Pace, and Clarity.
    """
    try:
        # Load with librosa
        y, sr = librosa.load(audio_path, duration=60) 
        duration_seconds = librosa.get_duration(y=y, sr=sr)
        
        # 1. Energy (RMS) -> 0-100
        rms = librosa.feature.rms(y=y)[0]
        avg_rms = np.mean(rms)
        energy = min(int(avg_rms * 1000), 100)
        energy = max(energy, 10)

        # 2. Pace (Words Per Minute)
        word_count = len(transcript.split())
        full_duration = librosa.get_duration(filename=audio_path)
        if full_duration > 0:
            pace = int(word_count / (full_duration / 60))
        else:
            pace = 0

        # 3. Clarity (Spectral Centroid)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        avg_centroid = np.mean(centroid)
        clarity = min(int(avg_centroid / 30), 100)
        
        return {
            "energy": energy,
            "pace": pace,
            "clarity": clarity
        }
    except Exception as e:
        print(f"Sonic DNA Error: {e}")
        return {"energy": 50, "pace": 120, "clarity": 70}

def save_to_history(filename, transcript, summary, dna, bullet_points, keywords, confidence_score, word_count, audio_url, duration):
    """Persists record to history.json"""
    history_item = {
        "id": int(time.time()),
        "filename": filename,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "transcript": transcript,
        "summary": summary,
        "sonic_dna": dna,
        "bullet_points": bullet_points,
        "keywords": keywords,
        "confidence_score": confidence_score,
        "word_count": word_count,
        "audio_url": audio_url,
        "duration": duration
    }
    
    current_history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                current_history = json.load(f)
        except:
            pass
            
    # Add to beginning
    current_history.insert(0, history_item) 
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(current_history, f, indent=4)
        
    return current_history

# -------------------- Routes --------------------

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/upload-page")
def upload_page():
    return render_template("upload.html")

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'audio' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['audio']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400

    filename = file.filename
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)

    try:
        # 1. Transcribe (Whisper)
        print("Transcribing...")
        # Lazy load model
        model = get_asr_model()
        result = model.transcribe(file_path)
        transcript = result["text"].strip()
        
        # Calculate Confidence Score
        segments = result.get('segments', [])
        if segments:
            avg_logprobs = [s.get('avg_logprob', -1.0) for s in segments]
            # Convert logprob to prob
            avg_confidence = np.mean([np.exp(lp) for lp in avg_logprobs])
            confidence_score = float(avg_confidence)
        else:
            confidence_score = 0.95
            
        # 2. Summarize (BART)
        print("Summarizing...")
        word_count = len(transcript.split())
        
        if word_count > 50:
            # Chunking for summarizer if massive
            input_text = transcript[:3000] # Truncate for safety/speed
            summ_pipe = get_summarizer()
            summary_res = summ_pipe(input_text, max_length=150, min_length=40, do_sample=False)
            summary = summary_res[0]['summary_text']
        else:
            summary = "Audio too short for AI summary."

        # 3. Sonic DNA (Librosa)
        print("Analyzing DNA...")
        # Recalculate duration from the librosa load inside calculate_sonic_dna? 
        # No, calculate_sonic_dna loads it internally. 
        # We should load it once if we want to be efficient, but for now let's just get duration.
        # Check calculate_sonic_dna implementation? 
        # It's better to just get duration here using soundfile or librosa if we haven't loaded it.
        # Actually, let's just use soundfile on file_path for speed.
        import soundfile as sf
        f = sf.SoundFile(file_path)
        duration = f.frames / f.samplerate
        
        dna = calculate_sonic_dna(file_path, transcript)
        
        # 4. Bullet Points & Keywords
        # Generate bullets from summary sentences, limit to 3
        bullet_points = [s.strip() for s in summary.split('.') if len(s.strip()) > 10]
        bullet_points = bullet_points[:3] 
        
        # Simple Keyword Extraction
        words = [w.lower().strip(".,!?") for w in transcript.split() if len(w) > 5]
        from collections import Counter
        keywords = [pair[0].title() for pair in Counter(words).most_common(5)]

        # 5. Save History
        audio_url = f"/uploads/{filename}"
        save_to_history(filename, transcript, summary, dna, bullet_points, keywords, confidence_score, word_count, audio_url, duration)

        return jsonify({
            "transcript": transcript,
            "summary": summary,
            "sonic_dna": dna,
            "audio_url": audio_url,
            "duration": duration,
            "word_count": word_count,
            "bullet_points": bullet_points,
            "keywords": keywords,
            "confidence_score": confidence_score,
            "audio_url": f"/uploads/{filename}",
            "filename": filename
        })

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/translate', methods=['POST'])
def translate_text():
    data = request.json
    transcript = data.get('transcript', '')
    summary = data.get('summary', '')
    target_lang = data.get('target_lang', 'es')

    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        
        # Limit to 4999 chars to avoid API errors
        translated_transcript = translator.translate(transcript[:4999]) if transcript else "" 
        translated_summary = translator.translate(summary[:4999]) if summary else ""

        return jsonify({
            "translated_transcript": translated_transcript,
            "translated_summary": translated_summary
        })
    except Exception as e:
        print(f"Translation Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/history', methods=['GET'])
def get_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return jsonify(json.load(f))
        except:
            return jsonify([])
    return jsonify([])

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    try:
        # 1. Remove from history
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
            
            new_history = [item for item in history if item['filename'] != filename]
            
            with open(HISTORY_FILE, 'w') as f:
                json.dump(new_history, f, indent=4)
        
        # 2. Remove file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return jsonify({"message": "File deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/uploads/<filename>')
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/download_pdf', methods=['POST'])
def download_pdf():
    data = request.json
    title = data.get("title", "Transcript")
    transcript = data.get("transcript", "")
    summary = data.get("summary", "")
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"TranscribeFlow Report: {title}", ln=1, align='C')
    
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="Summary", ln=1, align='L')
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=summary)
    
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(200, 10, txt="Transcript", ln=1, align='L')
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=transcript)
    
    # Output to buffer
    buffer = BytesIO()
    pdf_output = pdf.output(dest='S').encode('latin-1') # specific encoding for FPDF
    buffer.write(pdf_output)
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name=f"{title}_report.pdf", mimetype='application/pdf')

if __name__ == "__main__":
    # use_reloader=False is important on Windows with heavy ML libs to avoid "WinError 10038"
    app.run(debug=True, port=5001, use_reloader=False)
