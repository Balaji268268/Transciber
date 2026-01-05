from flask import Flask, request, render_template, jsonify
import os

app = Flask(__name__)

# Where uploaded files will be stored
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_audio():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file selected"}), 400

    audio_file = request.files["audio"]

    # allowed extensions
    allowed_ext = ["wav", "mp3"]
    file_ext = audio_file.filename.split(".")[-1].lower()

    if file_ext not in allowed_ext:
        return jsonify({"error": "File format not supported"}), 400

    # save file
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], audio_file.filename)
    audio_file.save(save_path)

    return jsonify({
        "message": "Uploaded successfully",
        "filename": audio_file.filename
    }), 200

if __name__ == "__main__":
    app.run(debug=True)
