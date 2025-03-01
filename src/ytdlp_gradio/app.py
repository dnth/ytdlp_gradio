import os
import gradio as gr
import yt_dlp
import re
import time

def is_vimeo_url(url):
    """Check if the URL is from Vimeo"""
    return re.search(r'vimeo\.com', url) is not None

def is_vimeo_showcase(url):
    """Check if the URL is a Vimeo showcase"""
    return re.search(r'vimeo\.com/showcase/', url) is not None

def is_playlist(url):
    """Check if the URL is a playlist (YouTube or Vimeo showcase)"""
    # YouTube playlist detection
    if re.search(r'youtube\.com/playlist', url) or re.search(r'youtube\.com/.*list=', url):
        return True
    # Vimeo showcase detection
    if is_vimeo_showcase(url):
        return True
    return False

def download_video(url, video_password=None, progress=gr.Progress()):
    """
    Download a video using yt-dlp
    
    Args:
        url: URL of the video to download
        video_password: Password for protected videos (e.g., Vimeo)
        progress: Gradio progress bar
        
    Returns:
        Path to the downloaded video file or error message
    """
    if not url:
        return "Please enter a URL"
    
    # Set default output directory
    output_dir = os.path.join(os.getcwd(), "downloads")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Always use bestvideo+bestaudio for best quality
    format_option = "bestvideo+bestaudio"
    
    # Track current video number for playlists
    current_video = {"num": 0, "total": 1, "title": ""}
    
    # Define progress hook
    def progress_hook(d):
        if d['status'] == 'downloading':
            filename = d.get('filename', '').split('/')[-1]
            
            # For playlists, show which video is being downloaded
            prefix = ""
            if is_playlist(url) and current_video["total"] > 1:
                prefix = f"Video {current_video['num']}/{current_video['total']}: "
                current_video["title"] = filename
            
            if d.get('total_bytes'):
                percentage = d['downloaded_bytes'] / d['total_bytes']
                progress(percentage, desc=f"{prefix}Downloading: {filename}")
            elif d.get('downloaded_bytes'):
                # For streams where total size is unknown
                progress(None, desc=f"{prefix}Downloading: {filename} ({d['downloaded_bytes'] / 1024 / 1024:.1f} MB)")
        elif d['status'] == 'finished':
            if is_playlist(url) and current_video["total"] > 1:
                progress(current_video['num'] / current_video['total'], 
                         desc=f"Video {current_video['num']}/{current_video['total']} complete, processing...")
                current_video["num"] += 1
            else:
                progress(1.0, desc="Download complete, processing file...")
    
    # Set options for yt-dlp
    ydl_opts = {
        'format': format_option,
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'quiet': False,
        'no_warnings': False,
        'progress_hooks': [progress_hook],
        'verbose': is_playlist(url),  # Enable verbose output for playlists
    }
    
    # Add video password if provided
    if video_password:
        ydl_opts['videopassword'] = video_password
    
    try:
        progress(0, desc="Starting download...")
        
        # For playlists, provide more detailed information
        if is_playlist(url):
            playlist_type = "Vimeo showcase" if is_vimeo_showcase(url) else "YouTube playlist"
            progress(0.01, desc=f"Processing {playlist_type} - this may take longer...")
            result_message = f"Downloading from {playlist_type}:\n\n"
        else:
            progress(0.01, desc="Extracting video information...")
            result_message = ""
            
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First extract info without downloading to get total count for playlists
            info_dict = ydl.extract_info(url, download=False)
            
            if 'entries' in info_dict and is_playlist(url):
                current_video["total"] = len(info_dict['entries'])
                current_video["num"] = 1
                progress(0.02, desc=f"Found {current_video['total']} videos in playlist. Starting downloads...")
            
            # Now do the actual download
            info = ydl.extract_info(url, download=True)
            
            # Get the downloaded file path
            if 'entries' in info:  # It's a playlist
                playlist_title = info.get('title', 'Unknown')
                entry_count = len(info['entries'])
                
                result_message += f"Playlist title: {playlist_title}\n"
                result_message += f"Number of videos: {entry_count}\n\n"
                
                for i, entry in enumerate(info['entries']):
                    if entry:  # Some entries might be None if download failed
                        file_path = os.path.join(output_dir, f"{entry['title']}.{entry['ext']}")
                        result_message += f"{i+1}. {entry['title']} - Downloaded to: {file_path}\n"
                    else:
                        result_message += f"{i+1}. [Download failed or skipped]\n"
            else:  # It's a single video
                file_path = os.path.join(output_dir, f"{info['title']}.{info['ext']}")
                result_message += f"Downloaded to: {file_path}"
            
            progress(1.0, desc="Download complete!")
            
            # Create a notification message
            if is_playlist(url) and 'entries' in info and len(info['entries']) > 1:
                notification_msg = f"Download complete! {len(info['entries'])} videos downloaded."
            else:
                notification_msg = "Download complete!"
                
            # Return both the result message and notification
            return result_message, gr.Success(notification_msg)
    except Exception as e:
        error_message = f"Error: {str(e)}"
        if is_playlist(url):
            error_message += "\n\nFor playlists, some videos might be unavailable or restricted."
            if is_vimeo_showcase(url):
                error_message += "\nFor Vimeo showcases, make sure you have the correct password if it's protected."
        return error_message, gr.Warning("Download failed. See details in the result box.")

# Create the Gradio interface
with gr.Blocks(title="Video Downloader") as app:
    gr.Markdown("# Video Downloader")
    gr.Markdown("Enter a video URL to download (always uses best video and audio quality)")
    
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
            
            download_button = gr.Button("Download")
        
        with gr.Column():
            output = gr.Textbox(label="Result", lines=10)  # Increased lines for more verbose output
    
    # Function to check URL and show password field if it's a Vimeo URL
    def check_url_type(url):
        if is_vimeo_url(url):
            return gr.update(visible=True)
        else:
            return gr.update(visible=False)
    
    # Update password field visibility when URL changes
    url_input.change(
        fn=check_url_type,
        inputs=url_input,
        outputs=password_input
    )
    
    # Download button
    download_button.click(
        fn=download_video,
        inputs=[url_input, password_input],
        outputs=[output]
    )

if __name__ == "__main__":
    app.launch(inbrowser=True) 