# YouTube Downloader with yt-dlp and Gradio

A simple web interface for downloading YouTube videos using yt-dlp.

## Features

- Download videos from YouTube and other supported platforms
- Select video quality/format
- Specify custom output directory
- Simple and intuitive user interface

## Installation

### Using pixi

If you have [pixi](https://pixi.sh/) installed:

```bash
pixi install
```

### Manual installation

1. Make sure you have Python 3.10 or newer installed
2. Install the required packages:

```bash
pip install yt-dlp gradio
```

## Usage

### Using pixi

```bash
pixi run start
```

### Manual start

```bash
python -m ytdlp_gradio.app
```

This will start a local web server, and you can access the interface by opening the provided URL in your browser (typically http://127.0.0.1:7860).

## How to Use

1. Enter a YouTube URL in the input field
2. Select the desired format from the dropdown menu
3. Optionally, specify an output directory (if left empty, files will be saved to a temporary directory)
4. Click the "Download" button
5. The path to the downloaded file will be displayed in the result box

## Supported Formats

- `best`: Best quality (video+audio)
- `bestvideo+bestaudio`: Best video and best audio
- `bestvideo`: Best video only
- `bestaudio`: Best audio only
- `worst`: Worst quality (smallest file size)

## License

MIT 