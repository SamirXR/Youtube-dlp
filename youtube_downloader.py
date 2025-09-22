import os
import sys
import subprocess
import shutil
import tempfile
import re
from typing import List, Dict, Optional, Tuple

def ffmpeg_available() -> bool:
    """Return True if ffmpeg is available on PATH."""
    return shutil.which("ffmpeg") is not None


def install_requirements():
    """Install required packages if not already installed"""
    try:
        import yt_dlp  # noqa: F401
        print("✅ yt-dlp is already installed")
    except ImportError:
        print("📦 Installing yt-dlp...")
        try:
            subprocess.check_call([
                sys.executable,
                "-m",
                "pip",
                "install",
                "yt-dlp",
            ])
            print("✅ yt-dlp installed successfully")
        except subprocess.CalledProcessError:
            print(
                "❌ Failed to install yt-dlp. Please install it manually:"
                " pip install yt-dlp"
            )
            sys.exit(1)

    # Check ffmpeg availability (needed for merging separate audio/video)
    if ffmpeg_available():
        print("✅ ffmpeg found (required for merging audio + video)")
    else:
        print("⚠️ ffmpeg not found. High-quality formats often need merging.")
        print(
            "   Install ffmpeg for Windows: "
            "https://ffmpeg.org/download.html"
        )
        print(
            "   Or winget (Admin): "
            "winget install Gyan.FFmpeg"
        )


def get_video_info(url: str) -> Optional[Dict]:
    """Get video information and available formats"""
    try:
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception as e:
        print(f"❌ Error getting video info: {e}")
        return None


def format_filesize(bytes_size: Optional[int]) -> str:
    """Convert bytes to human readable format"""
    if bytes_size is None:
        return "Unknown"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"


def display_formats(formats: List[Dict]) -> List[Dict]:
    """Display available video formats and return filtered list"""
    print("\n" + "="*80)
    print("📹 AVAILABLE VIDEO FORMATS (Audio automatically included)")
    print("="*80)
    
    # Filter for video formats
    video_formats = []
    
    for fmt in formats:
        if fmt.get('vcodec') != 'none':  # Has video
            format_note = fmt.get('format_note', '')
            ext = fmt.get('ext', '')
            height = fmt.get('height')
            fps = fmt.get('fps')
            filesize = fmt.get('filesize')
            vcodec = fmt.get('vcodec', 'unknown')
            acodec = fmt.get('acodec', 'none')
            
            video_formats.append({
                'format_id': fmt['format_id'],
                'ext': ext,
                'height': height,
                'fps': fps,
                'filesize': filesize,
                'vcodec': vcodec,
                'acodec': acodec,
                'format_note': format_note,
                'quality': fmt.get('quality', 0)
            })
    
    # Sort by quality (height and fps) in descending order
    video_formats.sort(
        key=lambda x: (x['height'] or 0, x['fps'] or 0),
        reverse=True,
    )
    
    # Remove duplicates based on height and fps
    seen = set()
    unique_formats = []
    for fmt in video_formats:
        key = (fmt['height'], fmt['fps'], fmt['ext'])
        if key not in seen:
            seen.add(key)
            unique_formats.append(fmt)
    
    if not unique_formats:
        print("❌ No video formats found!")
        return []
    
    print(
        f"{'#':<3} {'Quality':<15} {'Format':<8} "
        f"{'FPS':<5} {'Codec':<12} {'Size':<15}"
    )
    print("-" * 80)
    
    for i, fmt in enumerate(unique_formats[:15], 1):  # Show top 15 formats
        quality = f"{fmt['height']}p" if fmt['height'] else "Unknown"
        fps = f"{fmt['fps']}" if fmt['fps'] else "?"
        size = format_filesize(fmt['filesize'])
        vcodec = fmt['vcodec'][:10] if fmt['vcodec'] else "unknown"
        
        print(
            f"{i:<3} {quality:<15} {fmt['ext']:<8} "
            f"{fps:<5} {vcodec:<12} {size:<15}"
        )
    
    print("\n� Note: Audio is automatically included with all downloads")
    
    return unique_formats[:15]


def get_user_choice(formats: List[Dict]) -> Optional[tuple]:
    """Get user's format choice"""
    while True:
        try:
            print(
                f"\n📝 Choose (1-{len(formats)}) or 'q' to quit: ",
                end="",
            )
            choice = input().strip().lower()
            
            if choice == 'q':
                return None
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(formats):
                selected_format = formats[choice_num - 1]
                return (selected_format['format_id'], selected_format['ext'])
            else:
                print(f"❌ Please enter a number between 1 and {len(formats)}")
        except ValueError:
            print("❌ Please enter a valid number or 'q' to quit")


def parse_time_to_seconds(time_str: str) -> Optional[int]:
    """Parse time string in format MM:SS or M:SS to seconds"""
    try:
        # Remove any whitespace
        time_str = time_str.strip()
        
        # Check for MM:SS format
        if re.match(r'^\d{1,2}:\d{2}$', time_str):
            parts = time_str.split(':')
            minutes = int(parts[0])
            seconds = int(parts[1])
            
            if seconds >= 60:
                print(f"❌ Invalid time format: seconds cannot be >= 60")
                return None
                
            return minutes * 60 + seconds
        else:
            print(f"❌ Invalid time format. Use MM:SS (e.g., 2:05, 15:30)")
            return None
    except ValueError:
        print(f"❌ Invalid time format. Use MM:SS (e.g., 2:05, 15:30)")
        return None


def seconds_to_time_str(seconds: int) -> str:
    """Convert seconds to MM:SS format"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def get_trim_times(video_duration: Optional[int] = None) -> Optional[Tuple[int, int]]:
    """Get start and end times for trimming from user input"""
    print("\n✂️ VIDEO TRIMMING")
    print("=" * 50)
    
    if video_duration:
        duration_str = seconds_to_time_str(video_duration)
        print(f"📹 Video duration: {duration_str}")
    
    print("📝 Enter times in MM:SS format (e.g., 2:05 for 2 minutes 5 seconds)")
    
    # Get start time
    while True:
        start_input = input("⏯️  Start time (MM:SS): ").strip()
        if not start_input:
            print("❌ Start time is required")
            continue
            
        start_seconds = parse_time_to_seconds(start_input)
        if start_seconds is None:
            continue
            
        if video_duration and start_seconds >= video_duration:
            print(f"❌ Start time cannot be >= video duration ({duration_str})")
            continue
            
        break
    
    # Get end time
    while True:
        end_input = input("⏹️  End time (MM:SS): ").strip()
        if not end_input:
            print("❌ End time is required")
            continue
            
        end_seconds = parse_time_to_seconds(end_input)
        if end_seconds is None:
            continue
            
        if end_seconds <= start_seconds:
            start_str = seconds_to_time_str(start_seconds)
            print(f"❌ End time must be after start time ({start_str})")
            continue
            
        if video_duration and end_seconds > video_duration:
            print(f"❌ End time cannot be > video duration ({duration_str})")
            continue
            
        break
    
    duration = end_seconds - start_seconds
    duration_str = seconds_to_time_str(duration)
    start_str = seconds_to_time_str(start_seconds)
    end_str = seconds_to_time_str(end_seconds)
    
    print(f"✅ Trim: {start_str} to {end_str} (duration: {duration_str})")
    
    return (start_seconds, end_seconds)


def trim_video(input_path: str, output_path: str, start_seconds: int, end_seconds: int) -> bool:
    """Trim video using ffmpeg"""
    if not ffmpeg_available():
        print("❌ ffmpeg is required for video trimming")
        return False
    
    try:
        duration = end_seconds - start_seconds
        
        # Build ffmpeg command
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-ss', str(start_seconds),
            '-t', str(duration),
            '-c', 'copy',  # Copy streams without re-encoding for speed
            '-avoid_negative_ts', 'make_zero',
            '-y',  # Overwrite output file if it exists
            output_path
        ]
        
        print(f"✂️ Trimming video...")
        print(f"📂 Input: {os.path.basename(input_path)}")
        print(f"📁 Output: {os.path.basename(output_path)}")
        
        # Run ffmpeg command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if result.returncode == 0:
            print("✅ Video trimmed successfully!")
            return True
        else:
            print(f"❌ ffmpeg error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error trimming video: {e}")
        return False

def download_video(
    url: str,
    format_id: str,
    output_path: str = "./downloads",
    preferred_ext: str = "mp4",
    trim_times: Optional[Tuple[int, int]] = None,
):
    """Download the video with selected format and ensure audio is included.
    
    If trim_times is provided, download to temp directory first, then trim.

    Strategy:
    - Always select the chosen video format id
        - Add best matching audio for selected container to avoid
            incompatible merges
    - Prefer no transcoding; rely on ffmpeg to mux
    - If ffmpeg is missing, warn and attempt a progressive fallback
    """
    try:
        import yt_dlp
        
        # Create output directory if it doesn't exist
        os.makedirs(output_path, exist_ok=True)
        
        # Determine if we need a temporary directory for trimming
        use_temp = trim_times is not None
        
        if use_temp:
            # Create temporary directory for initial download
            temp_dir = tempfile.mkdtemp(prefix="youtube_dl_")
            download_dir = temp_dir
            print(f"📁 Using temporary directory: {temp_dir}")
        else:
            download_dir = output_path
        
        # Determine selected format details (to know if it already has audio)
        selected_format = None
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
            info_probe = ydl.extract_info(url, download=False)
            for f in info_probe.get('formats', []) or []:
                if f.get('format_id') == format_id:
                    selected_format = f
                    break

        ext = (preferred_ext or "").lower()
        ffm = ffmpeg_available()

        if not ffm:
            # Without ffmpeg we cannot merge separate streams.
            # Prefer a progressive format (has both video and audio).
            if selected_format and selected_format.get('acodec') != 'none':
                format_selector = format_id
            else:
                if ext in ("mp4", "m4a", "mov"):
                    progressive = (
                        "best[ext=mp4][acodec!=none][vcodec!=none]/"
                        "best[acodec!=none][vcodec!=none]"
                    )
                elif ext in ("webm",):
                    progressive = (
                        "best[ext=webm][acodec!=none][vcodec!=none]/"
                        "best[acodec!=none][vcodec!=none]"
                    )
                else:
                    progressive = "best[acodec!=none][vcodec!=none]"
                format_selector = progressive
        else:
            # Build an audio selector that matches the selected container
            if ext in ("mp4", "m4a", "mov"):
                audio_selector = (
                    "bestaudio[ext=m4a]/"
                    "bestaudio[acodec*=mp4a]/"
                    "bestaudio[acodec=aac]/"
                    "bestaudio"
                )
            elif ext in ("webm",):
                audio_selector = (
                    "bestaudio[ext=webm]/"
                    "bestaudio[acodec=opus]/"
                    "bestaudio"
                )
            else:
                audio_selector = "bestaudio"

            # Prefer exact video format + best matching audio, with fallbacks
            format_selector = (
                f"({format_id}+{audio_selector})/" f"{format_id}/best"
            )
        
        # yt-dlp options
        ydl_opts: Dict = {
            'format': format_selector,
            'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
            'writeinfojson': False,
            'writesubtitles': False,
            'keepvideo': False,
            'audio_quality': 0,
            'prefer_ffmpeg': True,
        }
        # Only add merging and metadata when ffmpeg is available
        if ffm:
            ydl_opts['postprocessors'] = [
                {'key': 'FFmpegMetadata'},
            ]
            if ext in ("mp4", "webm", "mkv"):
                ydl_opts['merge_output_format'] = ext
        
        # Diagnostics
        print("\n🚀 Starting download...")
        print("📁 Output directory:", os.path.abspath(download_dir))
        print("🎵 Format selector:", format_selector)
        print("📦 Target container:", ext or "auto")
        print("🧰 ffmpeg:", "available" if ffm else "missing")

        # If ffmpeg is missing, warn about potential lack of audio at
        # high resolutions
        if not ffm:
            print(
                "⚠️ ffmpeg missing: high-quality formats may not merge audio."
            )
            print(
                "   You can still proceed; consider installing ffmpeg for"
                " best results."
            )
        
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        print("✅ Download completed successfully!")
        
        # Handle trimming if requested
        if use_temp and trim_times:
            try:
                # Find the downloaded file
                downloaded_files = [f for f in os.listdir(temp_dir) 
                                  if f.lower().endswith(('.mp4', '.webm', '.mkv', '.avi'))]
                
                if not downloaded_files:
                    print("❌ No video file found in temporary directory")
                    return
                
                # Use the first video file found
                temp_file = os.path.join(temp_dir, downloaded_files[0])
                
                # Create final filename
                base_name = os.path.splitext(downloaded_files[0])[0]
                start_time = seconds_to_time_str(trim_times[0]).replace(':', '')
                end_time = seconds_to_time_str(trim_times[1]).replace(':', '')
                final_name = f"{base_name}_trimmed_{start_time}-{end_time}.{ext}"
                final_path = os.path.join(output_path, final_name)
                
                # Trim the video
                if trim_video(temp_file, final_path, trim_times[0], trim_times[1]):
                    print(f"✅ Trimmed video saved as: {final_name}")
                else:
                    print("❌ Trimming failed, keeping original file")
                    # Copy original file to output directory
                    shutil.copy2(temp_file, os.path.join(output_path, downloaded_files[0]))
                    
            except Exception as e:
                print(f"❌ Error during trimming process: {e}")
            finally:
                # Clean up temporary directory
                try:
                    shutil.rmtree(temp_dir)
                    print("🧹 Temporary files cleaned up")
                except Exception as e:
                    print(f"⚠️ Warning: Could not clean up temp directory: {e}")
        
    except Exception as e:
        print(f"❌ Download failed: {e}")
        # Clean up temp directory if it exists
        if use_temp and 'temp_dir' in locals():
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass



def main():
    """Main function"""
    print("🎬 YouTube Video Downloader")
    print("=" * 50)
    
    # Install requirements
    install_requirements()
    
    # Get URL from user or use default
    default_url = "https://www.youtube.com/watch?v=Af2rvOlj9UU"
    print(f"\n🔗 Default URL: {default_url}")
    user_url = input(
        "Enter YouTube URL (or press Enter to use default): "
    ).strip()
    
    url = user_url if user_url else default_url
    print(f"📋 Using URL: {url}")
    
    # Get video information
    print("\n🔍 Fetching video information...")
    info = get_video_info(url)
    
    if not info:
        print("❌ Failed to get video information. Please check the URL.")
        return
    
    print(f"📺 Title: {info.get('title', 'Unknown')}")
    print(f"👤 Uploader: {info.get('uploader', 'Unknown')}")
    print(f"⏱️  Duration: {info.get('duration', 'Unknown')} seconds")
    
    # Get and display available formats
    formats = info.get('formats', [])
    if not formats:
        print("❌ No formats available for this video.")
        return
    
    available_formats = display_formats(formats)
    if not available_formats:
        return
    
    # Get user choice
    choice_result = get_user_choice(available_formats)
    if not choice_result:
        print("👋 Download cancelled by user.")
        return
    
    format_id, preferred_ext = choice_result
    
    # Ask if user wants to trim the video
    trim_times = None
    if ffmpeg_available():
        print("\n✂️ VIDEO TRIMMING OPTION")
        print("=" * 50)
        trim_choice = input("Do you want to trim the video? (y/N): ").strip().lower()
        
        if trim_choice in ['y', 'yes']:
            video_duration = info.get('duration')
            trim_times = get_trim_times(video_duration)
            
            if trim_times is None:
                print("❌ Invalid trim times. Downloading full video.")
        else:
            print("📹 Downloading full video")
    else:
        print("\n⚠️ Video trimming requires ffmpeg. Downloading full video.")
    
    # Download the video
    download_video(url, format_id, "./downloads", preferred_ext, trim_times)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Download interrupted by user.")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
