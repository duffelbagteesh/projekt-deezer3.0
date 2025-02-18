import os
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
import logging
from spleeter.separator import Separator
from werkzeug.exceptions import RequestEntityTooLarge
import yt_dlp
from urllib.parse import urlparse, parse_qs
import subprocess
from functools import wraps
import time
from collections import defaultdict
import threading
from prometheus_client import Counter, Gauge, generate_latest
import psutil
from datetime import datetime
from functools import wraps
import traceback

port = int(os.environ.get('PORT', 8080))

log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(level=logging.DEBUG)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUESTS_TOTAL = Counter('requests_total', 'Total requests processed')
PROCESSING_TIME = Counter('processing_time_seconds', 'Time spent processing requests')
MEMORY_USAGE = Gauge('memory_usage_percent', 'System memory usage')
CPU_USAGE = Gauge('cpu_usage_percent', 'System CPU usage')
FAILED_REQUESTS = Counter('failed_requests_total', 'Total failed requests')

class ResourceMonitor:
    def __init__(self):
        self.memory_threshold = int(os.getenv('MEMORY_THRESHOLD', 90))
        self._start_monitoring()

    def _start_monitoring(self):
        def monitor():
            while True:
                try:
                    memory_percent = psutil.virtual_memory().percent
                    cpu_percent = psutil.cpu_percent(interval=1)
                    
                    MEMORY_USAGE.set(memory_percent)
                    CPU_USAGE.set(cpu_percent)
                    
                    if memory_percent > self.memory_threshold:
                        logger.warning(f"High memory usage: {memory_percent}%")
                        
                    time.sleep(5)
                except Exception as e:
                    logger.error(f"Monitoring error: {str(e)}")

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

monitor = ResourceMonitor()

def check_resources(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            memory_percent = psutil.virtual_memory().percent
            if memory_percent > monitor.memory_threshold:
                logger.error(f"Memory usage too high: {memory_percent}%")
                return jsonify({
                    'error': 'Server is currently experiencing high load. Please try again later.'
                }), 503
            
            start_time = time.time()
            result = f(*args, **kwargs)
            PROCESSING_TIME.inc(time.time() - start_time)
            REQUESTS_TOTAL.inc()
            
            return result
        except Exception as e:
            FAILED_REQUESTS.inc()
            logger.error(f"Request failed: {str(e)}\n{traceback.format_exc()}")
            return jsonify({
                'error': 'An unexpected error occurred. Please try again later.'
            }), 500
    
    return decorated_function

@app.route('/metrics')
def metrics():
    return generate_latest()

@app.route('/health')
def health():
    memory_percent = psutil.virtual_memory().percent
    cpu_percent = psutil.cpu_percent(interval=1)
    
    return jsonify({
        'status': 'healthy' if memory_percent < monitor.memory_threshold else 'degraded',
        'memory_usage': f"{memory_percent}%",
        'cpu_usage': f"{cpu_percent}%",
        'timestamp': datetime.now().isoformat()
    })


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
            'extractor_retries': 3,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-User': '?1',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-Dest': 'document',
                'Referer': 'https://www.youtube.com/',
            },
            # Add proxy support
            'proxy': os.getenv('HTTP_PROXY', None),  # Will use system proxy if available
            'source_address': '0.0.0.0',  # Use all available network interfaces
            'sleep_interval': 1,  # Add a small delay between requests
            'max_sleep_interval': 5,
            'retries': 10,  # Increase retry attempts
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

# Rate limiting setup
RATE_LIMIT = 1  # requests
RATE_LIMIT_PERIOD = 60  # seconds
request_counts = defaultdict(lambda: {'count': 0, 'reset_time': 0})
request_lock = threading.Lock()

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = request.remote_addr
        current_time = time.time()
        
        with request_lock:
            if current_time > request_counts[ip]['reset_time']:
                request_counts[ip] = {'count': 0, 'reset_time': current_time + RATE_LIMIT_PERIOD}
            
            if request_counts[ip]['count'] >= RATE_LIMIT:
                return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429
            
            request_counts[ip]['count'] += 1
            
        return f(*args, **kwargs)
    return decorated_function

@app.route('/split-audio', methods=['POST'])
@rate_limit
@check_resources
def split_audio():
    try:
        youtube_url = request.form.get('youtubeUrl')
        audio_file = request.files.get('audioFile')

        if not youtube_url and not audio_file:
            return jsonify({
                'error': 'Please provide either a YouTube URL or upload an audio file.'
            }), 400

        # Add file size check
        if audio_file:
            if len(audio_file.read()) > int(os.getenv('MAX_UPLOAD_SIZE', 32100000)):
                return jsonify({
                    'error': 'File size exceeds maximum limit of 32.1MB'
                }), 413
            audio_file.seek(0)  # Reset file pointer after reading

        clean_previous_data()

        # Process YouTube URL
        if youtube_url:
            logger.info(f"Processing YouTube URL: {youtube_url}")
            temp_file_path = extract_audio_from_youtube(youtube_url)
            if not temp_file_path:
                return jsonify({
                    'error': 'Failed to download YouTube audio'
                }), 400

            try:
                result = process_with_spleeter(temp_file_path)
                os.remove(temp_file_path)  # Clean up
                return jsonify(result)
            except Exception as e:
                logger.error(f"Spleeter processing failed: {str(e)}")
                return jsonify({
                    'error': 'Audio processing failed'
                }), 500

        # Process uploaded file
        if audio_file:
            if not audio_file.filename.lower().endswith('.wav'):
                return jsonify({
                    'error': 'Invalid file format. Please upload a WAV file.'
                }), 400

            wav_path = os.path.join(app.config['upload_folder'], 'audio.wav')
            audio_file.save(wav_path)

            try:
                return jsonify(process_with_spleeter(wav_path))
            except Exception as e:
                logger.error(f"Spleeter processing failed: {str(e)}")
                return jsonify({
                    'error': 'Audio processing failed'
                }), 500

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'error': 'An unexpected error occurred'
        }), 500

def process_with_spleeter(audio_path):
    """Wrapper function for Spleeter processing with proper error handling"""
    try:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        file_size = os.path.getsize(audio_path)
        if file_size > int(os.getenv('MAX_UPLOAD_SIZE', 32100000)):
            raise ValueError("File size exceeds maximum limit")

        # Get base filename without extension
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        output_dir = os.path.join(split_audio_dir, base_name)
        os.makedirs(output_dir, exist_ok=True)

        separator.separate_to_file(audio_path, split_audio_dir)

        return {
            'vocalsPath': f'/public/tracks/{base_name}/vocals.wav',
            'drumsPath': f'/public/tracks/{base_name}/drums.wav',
            'bassPath': f'/public/tracks/{base_name}/bass.wav',
            'instrumentsPath': f'/public/tracks/{base_name}/other.wav',
        }
    except Exception as e:
        logger.error(f"Error in process_with_spleeter: {str(e)}\n{traceback.format_exc()}")
        raise
        

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)