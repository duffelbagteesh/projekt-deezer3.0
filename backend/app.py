from flask import Flask, render_template, request, jsonify, send_from_directory
import os
from spleeter.separator import Separator
from pydub import AudioSegment
import numpy as np
from scipy.io import wavfile
import io


app = Flask(__name__, template_folder='../frontend/templates')
split_audio_dir = os.path.join(os.getcwd(), 'public', 'tracks')
app.config['upload_folder'] = os.path.join(os.getcwd(), 'public', 'uploads')

def mp3_to_wav(mp3_path):
    wav_path = mp3_path.replace(".mp3", ".wav")
    audio = AudioSegment.from_mp3(mp3_path)
    audio.export(wav_path, format="wav")
    return wav_path


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/public/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.path.join(os.getcwd(), 'public'), filename)

separator = Separator('spleeter:4stems')

@app.route('/split-audio', methods=['POST'])
def split_audio():
    # get uploaded audio file
    audio_file = request.files['audioFile']

     # Check if the file is in WAV format
    if not audio_file.filename.lower().endswith('.wav'):
        return jsonify({'error': 'Invalid file format. Please upload a WAV file.'}), 400
    
     # Save the WAV file to the temporary directory
    wav_path = os.path.join(app.config['upload_folder'], 'audio.wav')
    audio_file.save(wav_path)

     # Perform audio separation
    separator.separate_to_file(wav_path, split_audio_dir)

    # Return the actual done split audio
    return jsonify({
        'vocalsPath': '/public/tracks/output_vocals.wav',
        'drumsPath': '/public/tracks/output_drums.wav',
        'bassPath': '/public/tracks/output_bass.wav',
        'instrumentsPath': '/public/tracks/output_other.wav',
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
