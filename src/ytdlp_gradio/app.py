import os
import gradio as gr
import yt_dlp
import re
import platform
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any, Callable

# URL Utilities
def is_vimeo_url(url: str) -> bool:
    """Check if the URL is from Vimeo"""
    return re.search(r'vimeo\.com', url) is not None

def is_vimeo_showcase(url: str) -> bool:
    """Check if the URL is a Vimeo showcase"""
    return re.search(r'vimeo\.com/showcase/', url) is not None

def is_playlist(url: str) -> bool:
    """Check if the URL is a playlist (YouTube or Vimeo showcase)"""
    # YouTube playlist detection
    if re.search(r'youtube\.com/playlist', url) or re.search(r'youtube\.com/.*list=', url):
        return True
    # Vimeo showcase detection
    return is_vimeo_showcase(url)

# Download Configuration
@dataclass
class DownloadConfig:
    url: str
    video_password: Optional[str] = None
    audio_only: bool = False
    output_dir: str = os.path.join(os.getcwd(), "downloads")
    
    def __post_init__(self):
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Set format based on audio_only flag
        if self.audio_only:
            self.format_option = "bestaudio"
            
            # Use m4a on Windows, mp3 on other platforms
            is_windows = platform.system().lower() == "windows"
            if is_windows:
                self.file_extension = "m4a"
                self.preferred_codec = "m4a"
            else:
                self.file_extension = "mp3"
                self.preferred_codec = "mp3"
                
            self.post_processors = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': self.preferred_codec,
                'preferredquality': '192',
            }]
        else:
            self.format_option = "bestvideo+bestaudio"
            self.file_extension = "mp4"
            self.post_processors = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }]
    
    def get_ydl_opts(self, progress_hook: Callable) -> Dict:
        """Generate yt-dlp options dictionary"""
        ydl_opts = {
            'format': self.format_option,
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [progress_hook],
            'verbose': is_playlist(self.url),  # Enable verbose output for playlists
            'ignoreerrors': True,  # Skip private or unavailable videos in playlists
            'postprocessors': self.post_processors,
            'merge_output_format': 'mp4' if not self.audio_only else None,  # Ensure merged formats are mp4
        }
        
        # Add video password if provided
        if self.video_password:
            ydl_opts['videopassword'] = self.video_password
            
        return ydl_opts
    
    def update_to_m4a(self):
        """Update config to use M4A format instead of MP3"""
        if self.audio_only:
            self.post_processors[0]['preferredcodec'] = 'm4a'
            self.file_extension = "m4a"
            self.preferred_codec = "m4a"

# Download Manager
class DownloadManager:
    def __init__(self, config: DownloadConfig, progress: gr.Progress):
        self.config = config
        self.progress = progress
        self.current_video = {"num": 0, "total": 1, "title": ""}
        
    def progress_hook(self, d: Dict) -> None:
        """Progress hook for yt-dlp"""
        if d['status'] == 'downloading':
            filename = d.get('filename', '').split('/')[-1]
            
            # For playlists, show which video is being downloaded
            prefix = ""
            if is_playlist(self.config.url) and self.current_video["total"] > 1:
                prefix = f"Video {self.current_video['num']}/{self.current_video['total']}: "
                self.current_video["title"] = filename
            
            if d.get('total_bytes'):
                percentage = d['downloaded_bytes'] / d['total_bytes']
                # For playlists, scale the percentage to the current video's portion of the total
                if is_playlist(self.config.url) and self.current_video["total"] > 1:
                    # Calculate overall progress: completed videos + current video progress
                    overall_percentage = ((self.current_video["num"] - 1) + percentage) / self.current_video["total"]
                    self.progress(overall_percentage, desc=f"{prefix}Downloading: {filename}")
                else:
                    self.progress(percentage, desc=f"{prefix}Downloading: {filename}")
            elif d.get('downloaded_bytes'):
                # For streams where total size is unknown
                if is_playlist(self.config.url) and self.current_video["total"] > 1:
                    # For unknown size, estimate progress based on downloaded bytes
                    # Use a small increment to show activity
                    overall_percentage = (self.current_video["num"] - 1) / self.current_video["total"]
                    # Add a small fraction to show progress within current video
                    overall_percentage += 0.5 / self.current_video["total"]
                    self.progress(overall_percentage, desc=f"{prefix}Downloading: {filename} ({d['downloaded_bytes'] / 1024 / 1024:.1f} MB)")
                else:
                    self.progress(None, desc=f"{prefix}Downloading: {filename} ({d['downloaded_bytes'] / 1024 / 1024:.1f} MB)")
        elif d['status'] == 'finished':
            if is_playlist(self.config.url) and self.current_video["total"] > 1:
                self.progress(self.current_video['num'] / self.current_video['total'], 
                         desc=f"Video {self.current_video['num']}/{self.current_video['total']} complete, processing...")
                self.current_video["num"] += 1
            else:
                self.progress(1.0, desc="Download complete, processing file...")
    
    def download(self) -> Tuple[str, Any]:
        """Execute the download process and return results"""
        if not self.config.url:
            return "Please enter a URL", None
        
        try:
            self.progress(0, desc="Starting download...")
            
            # For playlists, provide more detailed information
            if is_playlist(self.config.url):
                playlist_type = "Vimeo showcase" if is_vimeo_showcase(self.config.url) else "YouTube playlist"
                self.progress(0.01, desc=f"Processing {playlist_type} - this may take longer...")
                result_message = f"Downloading from {playlist_type} ({('audio only' if self.config.audio_only else 'video')}:\n\n"
            else:
                self.progress(0.01, desc="Extracting video information...")
                result_message = ""
                
            # Try to download with current config
            try:
                info, result_message = self._perform_download()
            except Exception as e:
                # Check for audio conversion failure
                error_str = str(e).lower()
                if self.config.audio_only and ("mp3" in error_str or "audio conversion failed" in error_str or 
                                  "encoder not found" in error_str or "postprocessor" in error_str):
                    self.progress(0.1, desc="MP3 conversion failed, trying M4A format instead...")
                    # Update options to use m4a
                    self.config.update_to_m4a()
                    info, result_message = self._perform_download()
                    result_message += "\nNote: Using M4A format instead of MP3 for better compatibility"
                else:
                    # Re-raise the exception if it's not related to mp3 conversion
                    raise
            
            self.progress(1.0, desc="Download complete!")
            
            # Create a notification message
            notification_msg = self._create_notification(info)
                
            # Return both the result message and notification
            return result_message, gr.Success(notification_msg)
        except Exception as e:
            error_message = f"Error: {str(e)}"
            if is_playlist(self.config.url):
                error_message += "\n\nFor playlists, some videos might be unavailable or restricted."
                if is_vimeo_showcase(self.config.url):
                    error_message += "\nFor Vimeo showcases, make sure you have the correct password if it's protected."
            return error_message, gr.Warning("Download failed. See details in the result box.")
    
    def _perform_download(self) -> Tuple[Dict, str]:
        """Execute the actual download with yt-dlp"""
        ydl_opts = self.config.get_ydl_opts(self.progress_hook)
        result_message = ""
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First extract info without downloading to get total count for playlists
            info_dict = ydl.extract_info(self.config.url, download=False)
            
            if 'entries' in info_dict and is_playlist(self.config.url):
                # Filter out None entries (private/unavailable videos)
                available_entries = [entry for entry in info_dict['entries'] if entry is not None]
                self.current_video["total"] = len(available_entries)
                self.current_video["num"] = 1
                self.progress(0.02, desc=f"Found {self.current_video['total']} available videos in playlist. Starting downloads...")
            
            # Now do the actual download
            info = ydl.extract_info(self.config.url, download=True)
            
            # Process the results
            if 'entries' in info:  # It's a playlist
                result_message += self._format_playlist_result(info)
            else:  # It's a single video
                result_message += self._format_single_video_result(info)
                
        return info, result_message
    
    def _format_playlist_result(self, info: Dict) -> str:
        """Format the result message for a playlist download"""
        playlist_title = info.get('title', 'Unknown')
        
        # Count only non-None entries (available videos)
        available_entries = [entry for entry in info['entries'] if entry is not None]
        entry_count = len(available_entries)
        total_entries = len(info['entries'])
        skipped_count = total_entries - entry_count
        
        result = f"Playlist title: {playlist_title}\n"
        result += f"Number of {'audio tracks' if self.config.audio_only else 'videos'}: {entry_count} (downloaded) / {total_entries} (total)\n"
        if skipped_count > 0:
            result += f"Skipped {skipped_count} private or unavailable items\n"
        result += "\n"
        
        for i, entry in enumerate(info['entries']):
            if entry:  # Some entries might be None if download failed or video is private
                file_path = os.path.join(self.config.output_dir, f"{entry['title']}.{self.config.file_extension}")
                result += f"{i+1}. {entry['title']} - Downloaded to: {file_path}\n"
            else:
                result += f"{i+1}. [Private or unavailable item - skipped]\n"
                
        return result
    
    def _format_single_video_result(self, info: Dict) -> str:
        """Format the result message for a single video download"""
        file_path = os.path.join(self.config.output_dir, f"{info['title']}.{self.config.file_extension}")
        return f"Downloaded to: {file_path}"
    
    def _create_notification(self, info: Dict) -> str:
        """Create a notification message based on download results"""
        if is_playlist(self.config.url) and 'entries' in info:
            available_entries = [entry for entry in info['entries'] if entry is not None]
            entry_count = len(available_entries)
            total_entries = len(info['entries'])
            skipped_count = total_entries - entry_count
            
            if skipped_count > 0:
                return f"Download complete! {entry_count} {'audio tracks' if self.config.audio_only else 'videos'} downloaded, {skipped_count} skipped."
            else:
                return f"Download complete! {entry_count} {'audio tracks' if self.config.audio_only else 'videos'} downloaded."
        else:
            return "Download complete!"

def download_video(url, video_password=None, audio_only=False, progress=gr.Progress()):
    """
    Download a video using yt-dlp
    
    Args:
        url: URL of the video to download
        video_password: Password for protected videos (e.g., Vimeo)
        audio_only: Whether to download only the audio
        progress: Gradio progress bar
        
    Returns:
        Path to the downloaded video file or error message
    """
    config = DownloadConfig(url=url, video_password=video_password, audio_only=audio_only)
    manager = DownloadManager(config, progress)
    return manager.download()

# Create the Gradio interface
with gr.Blocks(title="Video Downloader") as app:
    gr.Markdown("# Video Downloader")
    gr.Markdown("Enter a video URL to download (uses best quality by default)")
    
    with gr.Row():
        with gr.Column():
            url_input = gr.Textbox(label="Video URL", placeholder="https://www.youtube.com/watch?v=... or https://vimeo.com/...")
            
            # Password input that will be shown conditionally for Vimeo videos
            password_input = gr.Textbox(
                label="Video Password (for protected Vimeo videos)",
                placeholder="Enter password if required",
                type="password",
                visible=False
            )
            
            # Audio only checkbox
            audio_only_checkbox = gr.Checkbox(label="Download audio only (MP3/M4A)", value=False)
            
            download_button = gr.Button("Download", variant="primary", interactive=False)
        
        with gr.Column():
            output = gr.Textbox(label="Status", lines=10)  # Increased lines for more verbose output
    
    # Function to check URL and show password field if it's a Vimeo URL
    def check_url_type(url):
        # Check if URL is empty to control download button state
        button_state = len(url.strip()) > 0
        
        # Check if it's a Vimeo URL to control password field visibility
        password_visible = is_vimeo_url(url)
        
        return gr.update(visible=password_visible), gr.update(interactive=button_state)
    
    # Update password field visibility and button state when URL changes
    url_input.change(
        fn=check_url_type,
        inputs=url_input,
        outputs=[password_input, download_button]
    )
    
    # Download button
    download_button.click(
        fn=download_video,
        inputs=[url_input, password_input, audio_only_checkbox],
        outputs=[output]
    )

if __name__ == "__main__":
    app.launch(inbrowser=True) 