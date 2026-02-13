import os
import shutil
import time
import json
import imageio_ffmpeg
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from clerk_backend_api import Clerk
from functools import wraps
from deep_translator import GoogleTranslator

# Speaker diarization
try:
    from pyannote.audio import Pipeline
    import torch
    import librosa
    DIARIZATION_AVAILABLE = True
except ImportError:
    DIARIZATION_AVAILABLE = False
    print("Warning: pyannote.audio not installed. Speaker diarization disabled.")

# --- FFMPEG Configuration for Whisper ---
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
ffmpeg_dir = os.path.dirname(ffmpeg_exe)
target_ffmpeg = os.path.join(ffmpeg_dir, "ffmpeg.exe")

# Whisper calls 'ffmpeg', so we need an executable with that exact name in PATH
if not os.path.exists(target_ffmpeg):
    try:
        shutil.copy(ffmpeg_exe, target_ffmpeg)
        print(f"Created ffmpeg.exe at {target_ffmpeg}")
    except Exception as e:
        print(f"Failed to create ffmpeg.exe: {e}")

# Inject into PATH
os.environ["PATH"] += os.pathsep + ffmpeg_dir

import whisper
from transformers import pipeline
import librosa
import numpy as np
from deep_translator import GoogleTranslator

# -------------------- Configuration --------------------
# Configure Flask to look for templates and static files in the frontend directory
basedir = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(basedir, "../frontend/templates")
static_dir = os.path.join(basedir, "../frontend/static")

app = Flask(__name__, 
            template_folder=template_dir,
            static_folder=static_dir)
CORS(app)  # Enable CORS

UPLOAD_FOLDER = os.path.join(basedir, "uploads")
HISTORY_FILE = os.path.join(basedir, "history.json")

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# -------------------- Clerk Authentication --------------------
CLERK_SECRET_KEY = "sk_test_VZJlwKWegCCcq6SftOAp5fXDJcMXSEZDmIUr1Zs2TL"
clerk_client = Clerk(bearer_auth=CLERK_SECRET_KEY)

def require_auth(f):
    """Decorator to protect routes - requires valid Clerk session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get session token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header:
            # Try to get from cookie (same-origin requests)
            session_token = request.cookies.get('__session')
        else:
            # Extract from Bearer token
            session_token = auth_header.replace('Bearer ', '')
        
        if not session_token:
            return jsonify({"error": "Unauthorized - No session token"}), 401
        
        try:
            # Verify the session token with Clerk
            session = clerk_client.sessions.verify_token(session_token)
            if not session:
                return jsonify({"error": "Invalid session"}), 401
            
            # Attach user_id to request for use in route
            request.user_id = session.get('sub')
            return f(*args, **kwargs)
        except Exception as e:
            print(f"Auth error: {e}")
            return jsonify({"error": "Authentication failed"}), 401
    
    return decorated_function

# -------------------- AI Models --------------------
print("Loading Whisper Model...")
# Use 'base' or 'small' for better accuracy than 'tiny' if machine permits
asr_model = whisper.load_model("tiny") 

print("Loading Summarization Model...")
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

# -------------------- Helper Functions --------------------

def calculate_sonic_dna(audio_path, transcript):
    """
    Calculates Energy, Pace, and Clarity.
    Pace is now calculated as true Words Per Minute (WPM) from transcript.
    """
    try:
        y, sr = librosa.load(audio_path) 
        duration_seconds = librosa.get_duration(y=y, sr=sr)
        
        # 1. Energy (RMS) -> 0-100
        rms = librosa.feature.rms(y=y)[0]
        avg_rms = np.mean(rms)
        energy = min(int(avg_rms * 1000), 100) # Scaling factor
        energy = max(energy, 10)

        # 2. Pace (True Words Per Minute)
        word_count = len(transcript.split())
        if duration_seconds > 0:
            pace = int(word_count / (duration_seconds / 60))
        else:
            pace = 0

        # Normalizing pace to 0-100 scale for radar chart (assuming 150-200 is fast)
        pace_score = min(int((pace / 200) * 100), 100)

        # 3. Clarity (Spectral Centroid as proxy)
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        avg_centroid = np.mean(centroid)
        clarity = min(int(avg_centroid / 50), 100) # Scaling
        
        return {
            "energy": energy,
            "pace": pace_score,
            "clarity": clarity,
            "duration": int(duration_seconds),
            "rms": int(avg_rms * 100),
            "raw_pace": pace
        }
    except Exception as e:
        print(f"Sonic DNA Error: {e}")
        return {
            "energy": 50, 
            "pace": 50, 
            "clarity": 50, 
            "duration": 0,
            "rms": 50,
            "raw_pace": 0
        }

# -------------------- Translator --------------------
def translate_texts(transcript, summary, target_lang):
    """
    Translate transcript and summary to target language using GoogleTranslator.
    Returns original text if translation fails or target_lang is 'en' or None.
    """
    if not target_lang or target_lang == 'en' or target_lang == 'original':
        return transcript, summary
    
    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        # Split long texts to handle Google's 5000 char limit
        translated_transcript = translator.translate(transcript[:4999]) if len(transcript) <= 4999 else transcript
        translated_summary = translator.translate(summary)
        return translated_transcript, translated_summary
    except Exception as e:
        print(f"Translation error: {e}")
        return transcript, summary

def perform_diarization(audio_file_path):
    """
    Perform speaker diarization using pyannote.audio
    Returns speaker segments or None if single speaker/unavailable
    """
    if not DIARIZATION_AVAILABLE:
        print("Diarization unavailable")
        return None
    
    try:
        # Load audio with librosa to bypass torchcodec issues
        print(f"Loading audio for diarization: {audio_file_path}")
        waveform, sample_rate = librosa.load(audio_file_path, sr=16000, mono=True)
        
        # Convert to torch tensor and add channel dimension
        waveform_tensor = torch.from_numpy(waveform).unsqueeze(0)
        
        # Create audio dict format expected by pyannote
        audio_dict = {
            'waveform': waveform_tensor,
            'sample_rate': sample_rate
        }
        
        # Initialize pipeline with HuggingFace token
        print("Initializing diarization pipeline...")
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token="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"
        )
        
        # Run diarization with preloaded audio
        print("Running speaker diarization...")
        diarization = pipeline(audio_dict)
        
        # Extract speaker segments
        speaker_segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speaker_segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })
        
        # Count unique speakers
        unique_speakers = len(set([seg["speaker"] for seg in speaker_segments]))
        
        print(f"Detected {unique_speakers} speaker(s)")
        
        # If only one speaker, return None (no diarization needed)
        if unique_speakers <= 1:
            return None
        
        return {
            "num_speakers": unique_speakers,
            "segments": speaker_segments
        }
        
    except Exception as e:
        print(f"Diarization error: {e}")
        import traceback
        traceback.print_exc()
        return None

def format_transcript_with_speakers(transcript_text, diarization_result, whisper_segments):
    """
    Format transcript with speaker labels for multi-speaker audio
    """
    if not diarization_result or not whisper_segments:
        return transcript_text
    
    # Match Whisper segments with speaker labels
    formatted_lines = []
    current_speaker = None
    
    for whisper_seg in whisper_segments:
        seg_start = whisper_seg.get('start', 0)
        seg_text = whisper_seg.get('text', '').strip()
        
        if not seg_text:
            continue
        
        # Find which speaker is talking at this timestamp
        speaker_label = None
        for diar_seg in diarization_result['segments']:
            if diar_seg['start'] <= seg_start <= diar_seg['end']:
                speaker_label = diar_seg['speaker']
                break
        
        if speaker_label and speaker_label != current_speaker:
            current_speaker = speaker_label
            # Simplify speaker labels (SPEAKER_00 -> Speaker 1)
            speaker_num = int(speaker_label.split('_')[-1]) + 1
            formatted_lines.append(f"\n\nSpeaker {speaker_num}: {seg_text}")
        elif seg_text:
            formatted_lines.append(seg_text)
    
    return ' '.join(formatted_lines)

def save_to_history(filename, transcript, summary, dna, bullet_points, keywords, confidence_score, word_count):
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
        "word_count": word_count
    }
    
    current_history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                current_history = json.load(f)
        except:
            pass
            
    current_history.insert(0, history_item) # Newest first
    
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

@app.route("/history-page")
def history_page():
    return render_template("history.html")

@app.route("/details")
def details_page():
    return render_template("details.html")

@app.route("/home")
def home_page():
    return render_template("home.html")

@app.route("/profile")
def profile_page():
    return render_template("profile.html")

# Upload Endpoint
# @require_auth  # Disabled - using frontend Clerk auth only
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'audio' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['audio']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = file.filename
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(file_path)
    
    # Get optional parameters
    target_lang = request.form.get('target_lang', 'original')
    enable_diarization = request.form.get('enable_diarization', 'false').lower() == 'true'

    try:
        # 1. Transcribe (Whisper)
        print("Transcribing...")
        result = asr_model.transcribe(file_path)
        transcript = result["text"].strip()
        segments = result.get('segments', [])
        
        # 2. Speaker Diarization (conditional based on user toggle)
        diarization_result = None
        if enable_diarization:
            print("Performing speaker diarization...")
            diarization_result = perform_diarization(file_path)
        
        # Format transcript with speaker labels if multiple speakers
        if diarization_result:
            transcript = format_transcript_with_speakers(transcript, diarization_result, segments)
            print(f"Formatted transcript with {diarization_result['num_speakers']} speakers")
        else:
            print("Single speaker detected - no diarization applied")
        
        # 3. Calculate Confidence Score
        segments = result.get('segments', [])
        if segments:
            avg_logprobs = [s.get('avg_logprob', -1.0) for s in segments]
            avg_confidence = np.mean([np.exp(lp) for lp in avg_logprobs])
            confidence_score = float(avg_confidence)
        else:
            confidence_score = 0.95 
            
        # 2. Summarize (BART)
        print("Summarizing...")
        word_count = len(transcript.split())
        
        if word_count > 50:
            input_text = transcript[:3000] 
            summary_res = summarizer(input_text, max_length=150, min_length=40, do_sample=False)
            summary = summary_res[0]['summary_text']
        else:
            summary = "Audio too short for AI summary."

        # 3. Sonic DNA (Librosa)
        print("Analyzing DNA...")
        dna = calculate_sonic_dna(file_path, transcript)
        
        # 4. Bullet Points & Keywords
        bullet_points = summary.split('. ')[:3]
        bullet_points = [b.strip() for b in bullet_points if b]
        
        # Keywords
        words = [w.lower().strip(".,!?") for w in transcript.split() if len(w) > 5]
        from collections import Counter
        word_freq = Counter(words)
        keywords = [pair[0].title() for pair in word_freq.most_common(5)]

        # 5. Translation (if requested)
        target_lang = request.form.get('target_lang', 'original')
        final_transcript = transcript
        final_summary = summary
        
        if target_lang and target_lang != 'original':
            print(f"Translating to {target_lang}...")
            final_transcript, final_summary = translate_texts(transcript, summary, target_lang)

        # 6. Save to History - ALWAYS save regardless of trial/auth mode
        print("Saving to history...")
        save_to_history(filename, final_transcript, final_summary, dna, bullet_points, keywords, confidence_score, word_count)

        return jsonify({
            "transcript": final_transcript,
            "summary": final_summary,
            "original_transcript": transcript,
            "original_summary": summary,
            "sonic_dna": dna,
            "word_count": word_count,
            "bullet_points": bullet_points,
            "keywords": keywords,
            "confidence_score": round(confidence_score * 100, 2),
            "audio_url": f"/uploads/{filename}",
            "num_speakers": diarization_result['num_speakers'] if diarization_result else 1
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

# History Endpoint (returns transcriptions history)
# @require_auth  # Commented out - using frontend auth only
@app.route('/history', methods=['GET'])
def get_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return jsonify(json.load(f))
        except:
            return jsonify([])
    return jsonify([])

@app.route('/history/<int:history_id>', methods=['DELETE'])
def delete_history_by_id(history_id):
    """Delete a history item by ID"""
    if not os.path.exists(HISTORY_FILE):
        return jsonify({"success": False, "error": "History file not found"}), 404
    
    try:
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
        
        # Filter out the item with matching ID
        updated_history = [item for item in history if item.get('id') != history_id]
        
        if len(updated_history) == len(history):
            return jsonify({"success": False, "error": "Item not found"}), 404
        
        # Save updated history
        with open(HISTORY_FILE, 'w') as f:
            json.dump(updated_history, f, indent=4)
        
        return jsonify({"success": True, "message": "Item deleted successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/history/delete-all", methods=["DELETE"])
def delete_all_history():
    """Delete all history entries"""
    try:
        if not os.path.exists(HISTORY_FILE):
            return jsonify({"success": False, "error": "History file not found"}), 404
        
        # Clear history file
        with open(HISTORY_FILE, 'w') as f:
            json.dump([], f)
        
        return jsonify({"success": True, "message": "All history deleted successfully"})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    try:
        # Remove from history
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
            new_history = [item for item in history if item['filename'] != filename]
            with open(HISTORY_FILE, 'w') as f:
                json.dump(new_history, f, indent=4)
        
        # Remove file
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        return jsonify({"message": "File deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/uploads/<filename>')
def serve_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

if __name__ == "__main__":
    app.run(debug=True, port=5000, use_reloader=False)
