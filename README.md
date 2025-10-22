# Lofi Mixer Studio v4.3.5

A Flask-based web application for creating lofi music mix videos with customizable backgrounds, crossfades, and logo overlays.

## Features

- **Audio Mixing**: Crossfade 2-10 songs into a seamless playlist
- **Flexible Backgrounds**: Use static images or looping videos
- **Logo Overlay**: Add transparent PNG logos with customizable position, scale, and opacity
- **Queue System**: Single-concurrency job queue for efficient resource usage
- **Real-time Progress**: Live progress tracking with ETA estimates
- **Multiple Output Options**: Support for 720p, 1080p, and 4K resolutions

## Requirements

### System Dependencies

- **Python 3.7+**
- **FFmpeg**: Required for audio/video processing
- **FFprobe**: Required for media file analysis (usually bundled with FFmpeg)

### Python Dependencies

- Flask

## Installation

### 1. Install System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3 python3-pip ffmpeg
```

**macOS (using Homebrew):**
```bash
brew install python ffmpeg
```

**Windows:**
- Download Python from [python.org](https://www.python.org/downloads/)
- Download FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html)
- Add FFmpeg to your system PATH

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install flask
```

### 3. Verify FFmpeg Installation

```bash
ffmpeg -version
ffprobe -version
```

Both commands should display version information without errors.

## Usage

### Starting the Server

```bash
python3 app.py
```

The application will start on `http://127.0.0.1:5050`

### Creating a Video Mix

1. **Open your browser** and navigate to `http://127.0.0.1:5050`

2. **Upload Songs**: Select 2-10 audio files (MP3, M4A, or WAV)

3. **Choose Background**:
   - Upload a static image (PNG/JPG), OR
   - Upload a looping video (MP4)

4. **Configure Settings**:
   - **Crossfade**: Duration in seconds for smooth transitions between songs
   - **Target Length**: Desired video duration in minutes (playlist will loop)
   - **Resolution**: Output video resolution (720p, 1080p, or 4K)
   - **Audio Bitrate**: Audio quality (192k, 256k, or 320k)
   - **Video Preset**: Encoding speed (ultrafast = faster but larger files)
   - **Output Filename**: Custom name for your video file

5. **Logo Overlay (Optional)**:
   - Upload a transparent PNG logo
   - Choose position (top-left, top-right, bottom-left, bottom-right)
   - Adjust scale (% of video width)
   - Set opacity (10-100%)

6. **Click "Queue Render"** to start the job

7. **Monitor Progress**:
   - View real-time encoding progress
   - Check queue position
   - See estimated time remaining

8. **Download**: Once complete, click the download button to get your video

## Configuration

### File Size Limits

The application supports uploads up to **2GB** (configured in `app.py:8`):

```python
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB
```

### Temporary File Cleanup

Old temporary files (2+ days old) are automatically cleaned on startup. Modify the cleanup period in `app.py:24`:

```python
def cleanup_old_tmp(days=2):  # Change 'days' value as needed
```

### Server Settings

Change the host/port in `app.py:511`:

```python
app.run(debug=True, host='127.0.0.1', port=5050)
```

**Production Note**: Set `debug=False` for production deployments.

## Job Queue System

The application uses a **single-concurrency queue** to prevent resource exhaustion:

- Only one video renders at a time
- Additional jobs wait in queue
- Queue position is displayed in real-time
- Jobs can be canceled at any time

## Troubleshooting

### "Internal Server Error"

**Check terminal output** for detailed error messages. Common issues:

- FFmpeg/FFprobe not installed or not in PATH
- Insufficient disk space
- Invalid input files

### "FFmpeg crossfade failed"

- Ensure all song files are valid audio files
- Check that files aren't corrupted
- Verify FFmpeg is properly installed

### Video Encoding is Slow

- Use faster preset (ultrafast or veryfast)
- Reduce resolution (720p instead of 1080p/4K)
- Use video backgrounds sparingly (static images encode faster)

### "Not enough disk space"

Video rendering requires significant temporary storage:

- **Estimated space needed**: 2-5x the final video size
- Check `/tmp` directory space (Linux/macOS)
- Temporary files are stored in system temp directory

### Port Already in Use

If port 5050 is occupied:

1. Change the port in `app.py:511`
2. Or kill the process using port 5050:
   ```bash
   # Linux/macOS
   lsof -ti:5050 | xargs kill -9
   ```

## Technical Details

### Processing Pipeline

1. **Crossfade**: Songs are crossfaded using FFmpeg's `acrossfade` filter
2. **Loop**: Crossfaded playlist is looped to reach target duration
3. **Video Render**: Background + audio are combined with optional logo overlay
4. **Output**: Final MP4 with H.264 video and AAC audio

### File Formats

**Supported Input:**
- Audio: MP3, M4A, WAV
- Image: PNG, JPG, JPEG
- Video: MP4
- Logo: PNG (with transparency)

**Output:**
- Format: MP4
- Video Codec: H.264 (libx264)
- Audio Codec: AAC
- Pixel Format: YUV420P (widely compatible)

## Development

### Project Structure

```
lofimix/
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── static/
│   └── app.js         # Client-side JavaScript
└── README.md          # This file
```

### Running in Debug Mode

Debug mode is enabled by default (`debug=True` in `app.py`):

- Auto-reloads on code changes
- Displays detailed error pages
- **Do not use in production**

## Security Notes

- Application runs on localhost by default (127.0.0.1)
- No authentication system (suitable for local use only)
- For production deployment, consider adding:
  - User authentication
  - Rate limiting
  - Input sanitization
  - HTTPS/TLS
  - Proper process management (gunicorn, uwsgi)

## License

This project is provided as-is without warranty. Use at your own risk.

## Support

For issues and feature requests, please check:
- Terminal output for error messages
- FFmpeg installation and version
- Available disk space
- Input file validity
