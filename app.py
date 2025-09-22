"""
Flask Web Application for YouTube Video Downloader
Provides a modern web interface for the YouTube downloader with trimming capabilities.
"""

import os
import sys
import json
import tempfile
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.exceptions import BadRequest

# Import our existing downloader functions
from youtube_downloader import (
    get_video_info,
    download_video,
    ffmpeg_available,
    install_requirements,
    parse_time_to_seconds,
    seconds_to_time_str
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Global variables for download status tracking
download_status = {}
download_lock = threading.Lock()

class DownloadProgress:
    def __init__(self, download_id):
        self.download_id = download_id
        self.status = 'pending'  # pending, downloading, trimming, completed, error
        self.progress = 0
        self.message = 'Initializing...'
        self.filename = None
        self.error = None
        self.created_at = datetime.now()
        
    def update(self, status=None, progress=None, message=None, filename=None, error=None):
        if status:
            self.status = status
        if progress is not None:
            self.progress = progress
        if message:
            self.message = message
        if filename:
            self.filename = filename
        if error:
            self.error = error

def generate_download_id():
    """Generate a unique download ID"""
    return f"dl_{int(time.time() * 1000)}"

def clean_old_downloads():
    """Clean up old download status entries (older than 1 hour)"""
    with download_lock:
        current_time = datetime.now()
        expired_downloads = []
        
        for download_id, progress in download_status.items():
            if (current_time - progress.created_at).seconds > 3600:  # 1 hour
                expired_downloads.append(download_id)
        
        for download_id in expired_downloads:
            del download_status[download_id]

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/video-info', methods=['POST'])
def api_video_info():
    """API endpoint to get video information"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            raise BadRequest('URL is required')
        
        url = data['url'].strip()
        if not url:
            raise BadRequest('URL cannot be empty')
        
        # Validate URL format (basic check)
        if not ('youtube.com' in url or 'youtu.be' in url):
            raise BadRequest('Please provide a valid YouTube URL')
        
        # Get video information using existing function
        video_info = get_video_info(url)
        
        if not video_info:
            return jsonify({'error': 'Failed to fetch video information'}), 400
        
        # Format the response for the frontend
        response_data = {
            'title': video_info.get('title'),
            'uploader': video_info.get('uploader'),
            'duration': video_info.get('duration'),
            'thumbnail': video_info.get('thumbnail'),
            'view_count': video_info.get('view_count'),
            'upload_date': video_info.get('upload_date'),
            'formats': []
        }
        
        # Process formats for frontend
        formats = video_info.get('formats', [])
        video_formats = []
        
        for fmt in formats:
            if fmt.get('vcodec') != 'none':  # Has video
                video_formats.append({
                    'format_id': fmt['format_id'],
                    'ext': fmt.get('ext'),
                    'height': fmt.get('height'),
                    'fps': fmt.get('fps'),
                    'filesize': fmt.get('filesize'),
                    'vcodec': fmt.get('vcodec'),
                    'acodec': fmt.get('acodec'),
                    'format_note': fmt.get('format_note'),
                    'quality': fmt.get('quality', 0)
                })
        
        # Sort by quality
        video_formats.sort(
            key=lambda x: (x['height'] or 0, x['fps'] or 0),
            reverse=True
        )
        
        response_data['formats'] = video_formats[:15]  # Top 15 formats
        
        return jsonify(response_data)
        
    except BadRequest as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error fetching video info: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/download', methods=['POST'])
def api_download():
    """API endpoint to start video download"""
    try:
        data = request.get_json()
        if not data:
            raise BadRequest('Request data is required')
        
        url = data.get('url', '').strip()
        format_id = data.get('format_id', '').strip()
        trim_times = data.get('trim_times')
        
        if not url:
            raise BadRequest('URL is required')
        if not format_id:
            raise BadRequest('Format ID is required')
        
        # Validate trim times if provided
        if trim_times:
            if not isinstance(trim_times, list) or len(trim_times) != 2:
                raise BadRequest('Trim times must be a list of two values [start, end]')
            
            start_seconds, end_seconds = trim_times
            if not isinstance(start_seconds, int) or not isinstance(end_seconds, int):
                raise BadRequest('Trim times must be integers (seconds)')
            
            if start_seconds >= end_seconds:
                raise BadRequest('End time must be after start time')
            
            if start_seconds < 0 or end_seconds < 0:
                raise BadRequest('Trim times cannot be negative')
        
        # Generate download ID
        download_id = generate_download_id()
        
        # Create progress tracker
        progress = DownloadProgress(download_id)
        with download_lock:
            download_status[download_id] = progress
        
        # Start download in background thread
        download_thread = threading.Thread(
            target=background_download,
            args=(download_id, url, format_id, trim_times)
        )
        download_thread.daemon = True
        download_thread.start()
        
        return jsonify({
            'download_id': download_id,
            'message': 'Download started successfully',
            'status': 'started'
        })
        
    except BadRequest as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error starting download: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/download-status/<download_id>')
def api_download_status(download_id):
    """API endpoint to check download status"""
    try:
        with download_lock:
            progress = download_status.get(download_id)
        
        if not progress:
            return jsonify({'error': 'Download not found'}), 404
        
        return jsonify({
            'download_id': download_id,
            'status': progress.status,
            'progress': progress.progress,
            'message': progress.message,
            'filename': progress.filename,
            'error': progress.error
        })
        
    except Exception as e:
        app.logger.error(f"Error checking download status: {e}")
        return jsonify({'error': 'Internal server error'}), 500

def background_download(download_id, url, format_id, trim_times):
    """Background function to handle video download"""
    try:
        with download_lock:
            progress = download_status[download_id]
        
        # Update status
        progress.update(status='downloading', progress=10, message='Starting download...')
        
        # Create downloads directory
        downloads_dir = os.path.join(os.path.dirname(__file__), 'downloads')
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Convert trim_times to tuple if provided
        trim_times_tuple = None
        if trim_times:
            trim_times_tuple = (trim_times[0], trim_times[1])
            progress.update(progress=20, message='Preparing trimmed download...')
        else:
            progress.update(progress=20, message='Preparing download...')
        
        # Download the video using existing function
        progress.update(progress=30, message='Downloading video...')
        
        # Call our existing download function
        download_video(
            url=url,
            format_id=format_id,
            output_path=downloads_dir,
            preferred_ext='mp4',
            trim_times=trim_times_tuple
        )
        
        # Find the downloaded file
        progress.update(progress=90, message='Finalizing...')
        
        # Look for recently created files in downloads directory
        downloaded_files = []
        for filename in os.listdir(downloads_dir):
            if filename.lower().endswith(('.mp4', '.webm', '.mkv', '.avi')):
                filepath = os.path.join(downloads_dir, filename)
                # Check if file was created recently (within last 5 minutes)
                if time.time() - os.path.getctime(filepath) < 300:
                    downloaded_files.append(filename)
        
        if downloaded_files:
            # Use the most recently created file
            downloaded_files.sort(key=lambda f: os.path.getctime(os.path.join(downloads_dir, f)), reverse=True)
            filename = downloaded_files[0]
            
            progress.update(
                status='completed',
                progress=100,
                message='Download completed successfully!',
                filename=filename
            )
        else:
            progress.update(
                status='error',
                message='Download completed but file not found',
                error='File not found after download'
            )
            
    except Exception as e:
        app.logger.error(f"Download error for {download_id}: {e}")
        with download_lock:
            progress = download_status.get(download_id)
            if progress:
                progress.update(
                    status='error',
                    message=f'Download failed: {str(e)}',
                    error=str(e)
                )

@app.route('/api/system-info')
def api_system_info():
    """API endpoint to get system information"""
    try:
        return jsonify({
            'ffmpeg_available': ffmpeg_available(),
            'python_version': sys.version,
            'downloads_dir': os.path.abspath('./downloads')
        })
    except Exception as e:
        app.logger.error(f"Error getting system info: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    app.logger.error(f"Internal error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

def initialize_app():
    """Initialize the application"""
    try:
        # Install requirements
        install_requirements()
        
        # Create necessary directories
        os.makedirs('downloads', exist_ok=True)
        os.makedirs('static/css', exist_ok=True)
        os.makedirs('static/js', exist_ok=True)
        os.makedirs('templates', exist_ok=True)
        
        app.logger.info("Application initialized successfully")
        
    except Exception as e:
        app.logger.error(f"Initialization error: {e}")

# Background task to clean old downloads
def cleanup_downloads_periodically():
    """Periodically clean up old download status entries"""
    while True:
        time.sleep(3600)  # Run every hour
        clean_old_downloads()

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_downloads_periodically)
cleanup_thread.daemon = True
cleanup_thread.start()

if __name__ == '__main__':
    # Initialize the application
    initialize_app()
    
    # Set up logging
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Check if we're in development mode
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    print("\n" + "="*60)
    print("🎬 YouTube Video Downloader - Web Interface")
    print("="*60)
    print("🌐 Server starting at: http://localhost:5000")
    print(f"📁 Downloads directory: {os.path.abspath('./downloads')}")
    print(f"🧰 FFmpeg available: {'Yes' if ffmpeg_available() else 'No'}")
    if not ffmpeg_available():
        print("⚠️  Warning: FFmpeg not found. Video trimming will not work.")
        print("   Install FFmpeg to enable trimming functionality.")
    print("="*60)
    print("Press Ctrl+C to stop the server")
    print("="*60)
    
    # Run the Flask app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=debug_mode,
        threaded=True
    )