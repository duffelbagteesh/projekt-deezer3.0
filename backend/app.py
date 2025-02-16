import os
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
import logging
import tempfile
from spleeter.separator import Separator
from werkzeug.exceptions import RequestEntityTooLarge
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import yt_dlp
import json
from urllib.parse import urlparse, parse_qs
import subprocess

port = int(os.environ.get('PORT', 80))

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, template_folder='../frontend/templates')
app.secret_key = 'your_secret_key'
split_audio_dir = os.path.join(os.getcwd(), 'public', 'tracks')
app.config['upload_folder'] = os.path.join(os.getcwd(), 'public', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 32.2 * 1024 * 1024  # 32MB

separator = Separator('spleeter:4stems')

def process_audio_with_spleeter(audio_path):
    """
    Processes the given audio file with Spleeter. If the file is not WAV, converts it first.
    """
    # Determine file extension
    file_extension = os.path.splitext(audio_path)[-1].lower()

    # Convert to WAV if it's not already in WAV format
    if file_extension != ".wav":
        converted_audio_path = audio_path.replace(file_extension, ".wav")
        convert_command = f"ffmpeg -i {audio_path} -acodec pcm_s16le -ar 44100 {converted_audio_path}"
        subprocess.run(convert_command, shell=True, check=True)
        audio_path = converted_audio_path  # Use the converted file

    # Run Spleeter
    output_dir = "output"
    spleeter_command = f"spleeter separate -p spleeter:4stems -o {output_dir} {audio_path}"
    
    try:
        subprocess.run(spleeter_command, shell=True, check=True)
        return f"{output_dir}/{os.path.basename(audio_path).replace('.wav', '')}"
    except subprocess.CalledProcessError as e:
        print(f"Error running Spleeter: {e}")
        return None

def extract_audio_from_youtube(youtube_url):
    try:
        # Ensure downloads directory exists
        os.makedirs('downloads', exist_ok=True)
        
        # Create a cookies directory in the app folder
        cookies_dir = os.path.join(os.getcwd(), 'downloads', 'cookies')
        os.makedirs(cookies_dir, exist_ok=True)
        cookies_file = os.path.join(cookies_dir, 'youtube.cookies')
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(id)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
                'preferredquality': '192',
            }],
            'nocheckcertificate': True,
            'geo_bypass': True,
            'cookiefile': cookies_file,
            'quiet': False,
            'noplaylist': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            }
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(youtube_url, download=True)
            video_id = info_dict.get('id', None)
            if video_id:
                filename = f"downloads/{video_id}.wav"
                if os.path.exists(filename):
                    return filename
                else:
                    raise Exception("File was not downloaded successfully")
            else:
                raise Exception("Failed to extract video ID")

    except Exception as e:
        print(f"Error extracting audio from YouTube: {e}")
        return None

def clean_previous_data():
    uploaded_file_path = os.path.join(app.config['upload_folder'], 'audio.wav')
    if os.path.exists(uploaded_file_path):
        os.remove(uploaded_file_path)

    track_dir = os.path.join('public', 'tracks', 'audio')
    if os.path.exists(track_dir):
        for filename in os.listdir(track_dir):
            if filename.endswith('.wav'):
                os.remove(os.path.join(track_dir, filename))

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify({'error': 'File is too large. Please upload a file smaller than 32 MB.'}), 413

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/public/<path:filename>')
def serve_static(filename):
    response = send_from_directory(os.path.join(os.getcwd(), 'public'), filename)
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.route('/split-audio', methods=['POST'])
def split_audio():
    youtube_url = request.form.get('youtubeUrl')
    audio_file = request.files.get('audioFile')

    clean_previous_data()

    if youtube_url:
        try:
            logging.debug(f"Processing YouTube URL: {youtube_url}")
            
            temp_file_path = extract_audio_from_youtube(youtube_url)

            # ensure the file was downloaded
            if not temp_file_path or not os.path.exists(temp_file_path):
                raise ValueError("Could not download audio from YouTube.")
            
            # Get the video ID from the filename (without the .wav extension)
            video_id = os.path.splitext(os.path.basename(temp_file_path))[0]
            
            # Create output directory if it doesn't exist
            output_dir = os.path.join(split_audio_dir, video_id)
            os.makedirs(output_dir, exist_ok=True)
            
            separator.separate_to_file(temp_file_path, split_audio_dir)
            
            os.remove(temp_file_path)
            
            return jsonify({
                'vocalsPath': f'/public/tracks/{video_id}/vocals.wav',
                'drumsPath': f'/public/tracks/{video_id}/drums.wav',
                'bassPath': f'/public/tracks/{video_id}/bass.wav',
                'instrumentsPath': f'/public/tracks/{video_id}/other.wav',
            })
        except Exception as e:
            logging.error(f"Error processing YouTube URL: {e}")
            return jsonify({'error': str(e)}), 500

    if audio_file:
        if not audio_file.filename.lower().endswith('.wav'):
            return jsonify({'error': 'Invalid file format. Please upload a WAV file.'}), 400

        wav_path = os.path.join(app.config['upload_folder'], 'audio.wav')
        audio_file.save(wav_path)

        separator.separate_to_file(wav_path, split_audio_dir)

        return jsonify({
            'vocalsPath': '/public/tracks/audio/vocals.wav',
            'drumsPath': '/public/tracks/audio/drums.wav',
            'bassPath': '/public/tracks/audio/bass.wav',
            'instrumentsPath': '/public/tracks/audio/other.wav',
        })

    return jsonify({'error': 'Please provide either a YouTube URL or upload an audio file.'}), 400
        

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)