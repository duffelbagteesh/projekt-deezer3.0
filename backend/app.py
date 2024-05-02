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


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/public/<path:filename>')
def serve_static(filename):
    response = send_from_directory(os.path.join(os.getcwd(), 'public'), filename)
    response.headers['Cache-Control'] = 'no-store'
    return response

separator = Separator('spleeter:4stems')

@app.route('/split-audio', methods=['POST'])
def split_audio():
    # get uploaded audio file
    audio_file = request.files['audioFile']

    # Delete the previously uploaded file
    for filename in os.listdir('public/uploads'):
        if filename.endswith('.wav'):
            os.remove(os.path.join('public/uploads', filename))

    # Delete the previously separated tracks
    for filename in os.listdir('public/tracks'):
        if filename.endswith('.wav'):
            os.remove(os.path.join('public/tracks', filename))

     # Check if the file is too large
    if len(audio_file.read()) > 50 * 1024 * 1024:  # 50 MB
        return jsonify({'error': 'File is too large. Please upload a file smaller than 50 MB.'}), 400

    # Reset file pointer to beginning
    audio_file.seek(0)

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
        'vocalsPath': '/public/tracks/audio/vocals.wav',
        'drumsPath': '/public/tracks/audio/drums.wav',
        'bassPath': '/public/tracks/audio/bass.wav',
        'instrumentsPath': '/public/tracks/audio/other.wav',
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
