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

    # Convert audio file to bytes
    audio_bytes = io.BytesIO(audio_file.read())

     # Convert MP3 to WAV using pydub
    audio = AudioSegment.from_file(audio_bytes, format="mp3")
    wav_bytes = io.BytesIO()
    audio.export(wav_bytes, format="wav")
    wav_bytes.seek(0)  # reset cursor to start of file
    audio_bytes = wav_bytes
     # Load audio with scipy
    rate, audio = wavfile.read(audio_bytes)

    # Load with scipy ting
    rate, audio = wavfile.read(audio_bytes)

    # Convert the audio to float32 for Spleeter
    audio = audio.astype(np.float32) / 32767.0

    # mono to stereo
    if audio.ndim == 1:
        audio = np.repeat(audio[:, np.newaxis], 2, axis=1)

    # letting spleeter do the damn ting
    prediction = separator.separate(audio)

    # Export stemies to WAV files
    split_audio_files = {}
    for instrument, data in prediction.items():
        # Rescaling?
        data *= 32767.0
        data = data.astype(np.int16)

        # Setting split audio length to original audio length
        target_length = len(audio)
        padded_data = np.pad(data, ((0, target_length - len(data)), (0, 0)), mode='constant')
        truncated_data = padded_data[:target_length]

        # Export split audio file as WAV
        track_file = os.path.join(split_audio_dir, f'output_{instrument}.wav')
        wavfile.write(track_file, rate, truncated_data)
        split_audio_files[instrument] = f'/public/tracks/output_{instrument}.wav'

    # Return the actual done split audio
    return jsonify(split_audio_files)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
