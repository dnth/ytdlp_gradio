import os
import gradio as gr
import yt_dlp
import re
import time

def is_vimeo_url(url):
    """Check if the URL is from Vimeo"""
    return re.search(r'vimeo\.com', url) is not None

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
    
    # Progress tracking variables
    progress_stats = {"downloaded_bytes": 0, "total_bytes": 0, "status": ""}
    
    # Define progress hook
    def progress_hook(d):
        if d['status'] == 'downloading':
            if d.get('total_bytes'):
                progress_stats['total_bytes'] = d['total_bytes']
                progress_stats['downloaded_bytes'] = d['downloaded_bytes']
                percentage = d['downloaded_bytes'] / d['total_bytes']
                progress(percentage, desc=f"Downloading: {d.get('filename', '').split('/')[-1]}")
            elif d.get('downloaded_bytes'):
                # For streams where total size is unknown
                progress_stats['downloaded_bytes'] = d['downloaded_bytes']
                # Show progress but can't calculate percentage
                progress(None, desc=f"Downloading: {d.get('filename', '').split('/')[-1]} ({d['downloaded_bytes'] / 1024 / 1024:.1f} MB)")
        elif d['status'] == 'finished':
            progress(1.0, desc="Download complete, processing file...")
        progress_stats['status'] = d['status']
    
    # Set options for yt-dlp
    ydl_opts = {
        'format': format_option,
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'quiet': False,
        'no_warnings': False,
        'progress_hooks': [progress_hook],
    }
    
    # Add video password if provided
    if video_password:
        ydl_opts['videopassword'] = video_password
    
    try:
        progress(0, desc="Starting download...")
        # Download the video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            progress(0.01, desc="Extracting video information...")
            info = ydl.extract_info(url, download=True)
            # Get the downloaded file path
            if 'entries' in info:  # It's a playlist
                file_path = os.path.join(output_dir, f"{info['entries'][0]['title']}.{info['entries'][0]['ext']}")
            else:  # It's a single video
                file_path = os.path.join(output_dir, f"{info['title']}.{info['ext']}")
            
            progress(1.0, desc="Download complete!")
            return file_path
    except Exception as e:
        return f"Error: {str(e)}"

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
            output = gr.Textbox(label="Result", lines=5)
    
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
        outputs=output
    )

if __name__ == "__main__":
    app.launch() 