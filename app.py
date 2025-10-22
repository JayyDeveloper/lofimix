#!/usr/bin/env python3
import os, math, shutil, tempfile, uuid, subprocess, pathlib, threading, time, traceback, sys, json
from collections import deque
from flask import Flask, request, send_file, render_template_string, redirect, url_for, jsonify, send_from_directory, make_response, session

# YouTube API imports (optional - only loaded if credentials exist)
YOUTUBE_ENABLED = False
try:
    from google_auth_oauthlib.flow import Flow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    YOUTUBE_ENABLED = os.path.exists('youtube_config.json')
except ImportError:
    pass

app = Flask(__name__)
app.secret_key = "lofi-" + str(uuid.uuid4())
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB uploads

# --- simple error handler so 500s show in the terminal nicely ---
@app.errorhandler(Exception)
def on_error(e):
    print("\n=== Unhandled error ===", file=sys.stderr)
    traceback.print_exc()
    return ("Internal Server Error. Check terminal for traceback.", 500, {"Content-Type": "text/plain"})

JOBS = {}
QUEUE = deque()
RUNNING = None
STREAMS = {}  # Active YouTube streams: {job_id: {broadcast_id, stream_proc, status, ...}}
VIDEOS = {}  # Available videos for streaming: {video_id: {path, name, size, type, created_at}}

TMP_PREFIX = "lofi_"
TMP_BASE = pathlib.Path(tempfile.gettempdir())

def cleanup_old_tmp(days=2):
    cutoff = time.time() - days*86400
    for p in TMP_BASE.glob(f"{TMP_PREFIX}*"):
        try:
            if p.is_dir() and p.stat().st_mtime < cutoff:
                shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass
cleanup_old_tmp()

# ===== YouTube Live Streaming Functions =====
def get_youtube_credentials():
    """Get YouTube API credentials from session or None"""
    if not YOUTUBE_ENABLED or 'youtube_credentials' not in session:
        return None
    creds_data = session['youtube_credentials']
    creds = Credentials(**creds_data)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        session['youtube_credentials'] = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
    return creds

def create_youtube_broadcast(creds, title, description, privacy='unlisted'):
    """Create a YouTube live broadcast and return stream key and URL"""
    try:
        youtube = build('youtube', 'v3', credentials=creds)

        # Create broadcast
        broadcast_response = youtube.liveBroadcasts().insert(
            part='snippet,status,contentDetails',
            body={
                'snippet': {
                    'title': title,
                    'description': description,
                    'scheduledStartTime': time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
                },
                'status': {
                    'privacyStatus': privacy,
                    'selfDeclaredMadeForKids': False
                },
                'contentDetails': {
                    'enableAutoStart': True,
                    'enableAutoStop': True,
                    'enableDvr': True,
                    'enableContentEncryption': False,
                    'enableEmbed': True,
                    'recordFromStart': True
                }
            }
        ).execute()

        broadcast_id = broadcast_response['id']

        # Create stream
        stream_response = youtube.liveStreams().insert(
            part='snippet,cdn',
            body={
                'snippet': {
                    'title': f'Stream for {title}'
                },
                'cdn': {
                    'frameRate': 'variable',
                    'ingestionType': 'rtmp',
                    'resolution': 'variable'
                }
            }
        ).execute()

        stream_id = stream_response['id']
        stream_name = stream_response['cdn']['ingestionInfo']['streamName']
        rtmp_url = stream_response['cdn']['ingestionInfo']['ingestionAddress']

        # Bind broadcast to stream
        youtube.liveBroadcasts().bind(
            part='id',
            id=broadcast_id,
            streamId=stream_id
        ).execute()

        return {
            'broadcast_id': broadcast_id,
            'stream_id': stream_id,
            'rtmp_url': rtmp_url,
            'stream_key': stream_name,
            'watch_url': f'https://youtube.com/watch?v={broadcast_id}'
        }
    except Exception as e:
        print(f"YouTube broadcast creation error: {e}", file=sys.stderr)
        traceback.print_exc()
        return None

def start_youtube_stream(video_path, rtmp_url, stream_key, job_id):
    """Start FFmpeg RTMP stream to YouTube"""
    full_rtmp = f"{rtmp_url}/{stream_key}"

    cmd = [
        'ffmpeg',
        '-re',  # Read input at native frame rate
        '-stream_loop', '-1',  # Loop video indefinitely
        '-i', str(video_path),
        '-c:v', 'libx264',
        '-preset', 'veryfast',
        '-b:v', '3000k',
        '-maxrate', '3000k',
        '-bufsize', '6000k',
        '-pix_fmt', 'yuv420p',
        '-g', '60',  # Keyframe every 2 seconds at 30fps
        '-c:a', 'aac',
        '-b:a', '192k',
        '-ar', '44100',
        '-f', 'flv',
        full_rtmp
    ]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        STREAMS[job_id]['stream_proc'] = proc
        STREAMS[job_id]['status'] = 'streaming'

        # Monitor stream in background
        def monitor():
            for line in proc.stdout:
                if job_id in STREAMS:
                    STREAMS[job_id]['last_output'] = line.strip()
            proc.wait()
            if job_id in STREAMS:
                STREAMS[job_id]['status'] = 'stopped'
                STREAMS[job_id].pop('stream_proc', None)

        threading.Thread(target=monitor, daemon=True).start()
        return True
    except Exception as e:
        print(f"Stream start error: {e}", file=sys.stderr)
        return False

def stop_youtube_stream(job_id):
    """Stop an active YouTube stream"""
    if job_id not in STREAMS:
        return False

    stream_info = STREAMS[job_id]
    proc = stream_info.get('stream_proc')

    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    stream_info['status'] = 'stopped'
    stream_info.pop('stream_proc', None)
    return True

HTML = '''<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Lofi Mixer Studio - V4.3.5</title>
<style>
:root{--bg1:#0b0c10;--text:#e7e7ea;--muted:#a3a8b3;--card:rgba(255,255,255,0.06);--border:rgba(255,255,255,0.12);--input-bg:rgba(255,255,255,0.05);--input-hover:rgba(255,255,255,0.08)}
*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto;color:var(--text);background:#0b0c10}
.container{max-width:1160px;margin:0 auto;padding:28px 20px 80px}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;margin-bottom:16px;padding:14px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media (max-width:900px){.grid{grid-template-columns:1fr}}
.label{font-size:13px;color:#cad0db;margin-bottom:6px}
input[type="text"],input[type="number"],select,input[type="file"]{width:100%;border:1px solid var(--border);background:linear-gradient(180deg,var(--input-bg),rgba(255,255,255,0.03));color:var(--text);border-radius:12px;padding:12px 14px}
.small{font-size:12px;color:var(--muted)}
.btn{appearance:none;border:1px solid var(--border);border-radius:12px;padding:12px 16px;font-weight:700;color:var(--text);background:linear-gradient(180deg,rgba(255,255,255,.06),rgba(255,255,255,.03));cursor:pointer}
.btn-primary{color:#fff;border:0;background:linear-gradient(140deg,#7c3aed,#22c55e)}
.progress{border-radius:12px;overflow:hidden;border:1px solid var(--border);background:rgba(255,255,255,0.05)}
.bar{height:12px;width:0;background:#22c55e}
.table{width:100%;border-collapse:collapse}.table th,.table td{border-bottom:1px solid var(--border);padding:10px 8px;text-align:left;font-size:13px}
.right{display:flex;gap:8px;justify-content:flex-end}
</style>
</head>
<body>
<div class="container">

  <div class="card">
    <h2 style="margin:6px 0 12px 0;">Create video (queued) <span style="font-size:12px;color:#a3a8b3;">V4.3.5</span></h2>
    <form id="mixForm" action="{{ url_for('enqueue_job') }}" method="post" enctype="multipart/form-data" onsubmit="return startBuild()">
      <div class="grid">
        <div>
          <div class="label">Songs (MP3/M4A/WAV) - select 2 to 10</div>
          <input id="songInput" type="file" name="songs" accept=".mp3,.m4a,.wav" multiple required />
          <div id="songList" class="small"></div>
        </div>
        <div>
          <div class="label">Background</div>
          <div class="grid">
            <div>
              <div class="small">Static image (PNG/JPG)</div>
              <input id="imgInput" type="file" name="image_bg" accept=".png,.jpg,.jpeg" />
            </div>
            <div>
              <div class="small">Loop video (MP4)</div>
              <input id="vidInput" type="file" name="video_bg" accept=".mp4" />
              <div class="small">Pick either image OR video</div>
            </div>
          </div>
          <div id="bgPreview" class="small" style="margin-top:6px;"></div>
        </div>
      </div>

      <div class="grid" style="margin-top:12px;">
        <div>
          <div class="label">Crossfade (s)</div>
          <input type="number" name="crossfade" id="crossfade" value="5" min="0" max="30" step="1" required />
        </div>
        <div>
          <div class="label">Target length (minutes)</div>
          <input type="number" name="target_minutes" id="target_minutes" value="180" min="5" step="5" required />
        </div>
      </div>

      <div class="grid" style="margin-top:12px;">
        <div>
          <div class="label">Resolution</div>
          <select name="resolution" id="resolution">
            <option value="1920x1080" selected>1080p</option>
            <option value="1280x720">720p</option>
            <option value="3840x2160">4K</option>
          </select>
        </div>
        <div>
          <div class="label">Audio bitrate</div>
          <select name="abitrate" id="abitrate">
            <option value="192k" selected>192 kbps</option>
            <option value="256k">256 kbps</option>
            <option value="320k">320 kbps</option>
          </select>
        </div>
      </div>

      <div class="grid" style="margin-top:12px;">
        <div>
          <div class="label">Video preset (speed)</div>
          <select name="preset" id="preset">
            <option value="ultrafast" selected>ultrafast</option>
            <option value="veryfast">veryfast</option>
            <option value="faster">faster</option>
            <option value="fast">fast</option>
            <option value="medium">medium</option>
          </select>
        </div>
        <div>
          <div class="label">Output filename</div>
          <input type="text" name="basename" id="basename" value="" required />
          <div class="small">Auto-filled with date (editable).</div>
        </div>
      </div>

      <div style="margin-top:16px;">
        <h3 style="margin:0 0 8px;">Logo overlay</h3>
        <div class="grid">
          <div>
            <div class="label">PNG (transparent)</div>
            <input type="file" name="logo_png" id="logo_png" accept=".png" />
          </div>
          <div>
            <div class="label">Position</div>
            <select name="logo_pos" id="logo_pos">
              <option value="top-left" selected>Top-left</option>
              <option value="top-right">Top-right</option>
              <option value="bottom-left">Bottom-left</option>
              <option value="bottom-right">Bottom-right</option>
            </select>
          </div>
        </div>
        <div class="grid" style="margin-top:12px;">
          <div>
            <div class="label">Scale width (%)</div>
            <input type="number" name="logo_scale" id="logo_scale" value="18" min="5" max="60" step="1" />
          </div>
          <div>
            <div class="label">Opacity (%)</div>
            <input type="number" name="logo_opacity" id="logo_opacity" value="80" min="10" max="100" step="5" />
          </div>
        </div>
      </div>

      <div class="right" style="margin-top:18px;">
        <button type="reset" class="btn">Reset</button>
        <button type="submit" class="btn btn-primary" id="buildBtn">Queue Render</button>
      </div>
    </form>
  </div>

  <div id="progressCard" class="card" style="display:none;">
    <div>
      <div><b>Status:</b> <span id="stage" style="font-family:monospace">Queued...</span> - ETA: <span id="eta">-</span></div>
      <div class="progress" style="margin:8px 0 6px;"><div id="bar" class="bar" style="width:0%"></div></div>
      <div id="logBox" style="white-space:pre-wrap; max-height:220px; overflow:auto; font-family:monospace; font-size:12px; color:#cbd5e1">-</div>
      <div class="small">Queue position: <span id="qpos">-</span></div>
      <div class="right" style="margin-top:8px;">
        <button class="btn" onclick="cancelSelf()">Cancel</button>
        <a id="downloadLink" class="btn btn-primary" href="#" style="display:none;">Download</a>
        <button id="youtubeBtn" class="btn" style="display:none;background:linear-gradient(140deg,#ff0000,#cc0000);color:#fff;border:0" onclick="showYoutubeModal()">Go Live on YouTube</button>
      </div>
    </div>
  </div>

  <!-- YouTube Streaming Modal -->
  <div id="youtubeModal" class="card" style="display:none;">
    <h3 style="margin:0 0 12px">YouTube Live Streaming</h3>
    <div id="youtubeAuthSection">
      <p class="small">Authenticate with YouTube to start streaming</p>
      <button class="btn btn-primary" onclick="authenticateYouTube()">Connect YouTube Account</button>
    </div>
    <div id="youtubeStreamSetup" style="display:none;">
      <div style="margin-bottom:12px;">
        <div class="label">Stream Title</div>
        <input type="text" id="streamTitle" placeholder="My Lofi Stream" />
      </div>
      <div style="margin-bottom:12px;">
        <div class="label">Description</div>
        <input type="text" id="streamDesc" placeholder="Chill lofi beats to study/relax to" />
      </div>
      <div style="margin-bottom:12px;">
        <div class="label">Privacy</div>
        <select id="streamPrivacy">
          <option value="public">Public</option>
          <option value="unlisted" selected>Unlisted</option>
          <option value="private">Private</option>
        </select>
      </div>
      <div class="right" style="gap:8px;">
        <button class="btn" onclick="hideYoutubeModal()">Cancel</button>
        <button class="btn btn-primary" onclick="startYouTubeStream()">Start Streaming</button>
      </div>
    </div>
    <div id="youtubeStreamActive" style="display:none;">
      <div style="background:rgba(34,197,94,0.1);border:1px solid #22c55e;border-radius:8px;padding:12px;margin-bottom:12px;">
        <div style="color:#22c55e;font-weight:700;margin-bottom:6px;">Stream is LIVE!</div>
        <div class="small">Watch URL: <a id="watchUrl" href="#" target="_blank" style="color:#22c55e;">#</a></div>
        <div class="small" style="margin-top:4px;">Status: <span id="streamStatus">Starting...</span></div>
      </div>
      <div class="right">
        <button class="btn" style="background:#dc2626;color:#fff;" onclick="stopYouTubeStream()">Stop Stream</button>
        <button class="btn" onclick="hideYoutubeModal()">Close</button>
      </div>
    </div>
  </div>

  <!-- YouTube Live Streaming Section -->
  <div class="card">
    <h3 style="margin:0 0 12px;display:flex;align-items:center;gap:8px;">
      <span style="font-size:24px;">🔴</span> YouTube Live Streaming
    </h3>

    <div id="youtubeNotConfigured" style="display:none;">
      <div style="background:rgba(251,191,36,0.1);border:1px solid #fbbf24;border-radius:8px;padding:12px;margin-bottom:12px;">
        <div style="color:#fbbf24;font-weight:700;margin-bottom:4px;">⚠️ YouTube Not Configured</div>
        <div class="small">To enable YouTube streaming, follow the setup guide in README.md</div>
        <div class="small" style="margin-top:4px;">You'll need: Google Cloud Project + YouTube API credentials</div>
      </div>
    </div>

    <div id="youtubeConfigured" style="display:none;">
      <div id="youtubeNotAuthenticated" style="display:none;">
        <div style="background:rgba(59,130,246,0.1);border:1px solid #3b82f6;border-radius:8px;padding:12px;margin-bottom:12px;">
          <div style="color:#3b82f6;font-weight:700;margin-bottom:4px;">Connect Your YouTube Account</div>
          <div class="small" style="margin-bottom:8px;">Authenticate to start streaming your videos</div>
          <button class="btn btn-primary" onclick="authenticateYouTube()">Connect YouTube Account</button>
        </div>
      </div>

      <div id="youtubeAuthenticated" style="display:none;">
        <div style="background:rgba(34,197,94,0.1);border:1px solid #22c55e;border-radius:8px;padding:8px 12px;margin-bottom:12px;">
          <span style="color:#22c55e;">✓ YouTube Connected</span>
        </div>

        <!-- Upload Video for Streaming -->
        <div style="margin-bottom:16px;">
          <h4 style="margin:0 0 8px;">Upload Video to Stream</h4>
          <form id="uploadVideoForm" enctype="multipart/form-data" onsubmit="return uploadVideoForStreaming(event)">
            <div class="grid">
              <div>
                <input type="file" name="stream_video" id="streamVideoInput" accept=".mp4" required />
                <div class="small">Upload an MP4 file to stream on YouTube</div>
              </div>
              <div style="display:flex;align-items:flex-end;">
                <button type="submit" class="btn btn-primary" style="width:100%;">Upload Video</button>
              </div>
            </div>
          </form>
          <div id="uploadProgress" style="display:none;margin-top:8px;">
            <div class="small">Uploading...</div>
            <div class="progress"><div id="uploadBar" class="bar" style="width:0%"></div></div>
          </div>
        </div>

        <!-- Available Videos -->
        <div>
          <h4 style="margin:0 0 8px;">Available Videos for Streaming</h4>
          <table class="table">
            <thead>
              <tr>
                <th>Video</th>
                <th>Size</th>
                <th>Type</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody id="streamVideosBody">
              <tr><td colspan="4" class="small" style="text-align:center;color:var(--muted);">No videos available yet. Render or upload a video above.</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <div class="card">
    <div>
      <div style="display:flex;align-items:center;justify-content:space-between"><h3>Jobs</h3><span class="small">Single-concurrency encoder</span></div>
      <table class="table">
        <thead><tr><th>Job</th><th>Status</th><th>Queue</th><th>Progress</th><th>Output</th><th>Action</th></tr></thead>
        <tbody id="jobsBody"></tbody>
      </table>
    </div>
  </div>

</div>
<script src="/static/app.js"></script>
</body>
</html>'''

def push_log(job_id, line):
    j = JOBS[job_id]
    j.setdefault('log', []).append(line)
    if len(j['log']) > 2000:
        j['log'] = j['log'][-1000:]

def run_and_stream(cmd, job_id):
    j = JOBS[job_id]
    if j.get('canceled'):
        return -1
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    j['proc'] = proc
    for line in proc.stdout:
        j['progress'] = line.strip()
        push_log(job_id, line.rstrip('\n'))
        if j.get('canceled'):
            try: proc.terminate()
            except Exception: pass
            break
    rc = proc.wait()
    j.pop('proc', None)
    return rc

def build_overlay_filter(logo_path, pos, scale_pct, opacity_pct, target_res):
    try:
        W_target, H_target = target_res.split("x")
    except ValueError:
        W_target, H_target = "1920", "1080"
    x_expr, y_expr = "10", "10"
    if pos == "top-right": x_expr, y_expr = "W-w-10", "10"
    elif pos == "bottom-left": x_expr, y_expr = "10", "H-h-10"
    elif pos == "bottom-right": x_expr, y_expr = "W-w-10", "H-h-10"
    scale_expr = f"iw*{scale_pct}/100"
    alpha = max(0.1, min(1.0, float(opacity_pct) / 100.0))
    # Make final scale part of the complex graph to avoid -vf conflicts
    return (
        f"[1:v]format=rgba,scale=w={scale_expr}:h=-1,colorchannelmixer=aa={alpha}[l2];"
        f"[0:v][l2]overlay=x={x_expr}:y={y_expr}:format=auto,scale={W_target}:{H_target},setsar=1[vout]"
    )

def start_next_if_idle():
    global RUNNING
    if RUNNING is not None: return
    if not QUEUE: return
    job_id = QUEUE.popleft()
    j = JOBS.get(job_id)
    if not j or j.get('canceled'):
        start_next_if_idle(); return
    RUNNING = job_id
    j['stage'] = 'Starting...'
    threading.Thread(target=build_job, args=(job_id,), daemon=True).start()

def end_job(job_id):
    global RUNNING
    if RUNNING == job_id:
        RUNNING = None
    start_next_if_idle()

def build_job(job_id):
    j = JOBS[job_id]
    try:
        cfg = j['cfg']
        crossfade = int(cfg['crossfade'])
        target_minutes = int(cfg['target_minutes'])
        resolution = cfg['resolution']
        abitrate = cfg['abitrate']
        preset = cfg['preset']
        basename = cfg['basename']
        tmpdir = pathlib.Path(cfg['tmpdir'])
        song_paths = [pathlib.Path(p) for p in cfg['songs']]
        use_video_bg = cfg['use_video_bg']
        img_path = cfg['img_path']
        vid_path = cfg['vid_path']
        logo_png = cfg.get('logo_png')
        logo_pos = cfg.get('logo_pos','top-left')
        logo_scale = int(cfg.get('logo_scale','18'))
        logo_opacity = int(cfg.get('logo_opacity','80'))

        # Step 1: build crossfaded playlist
        j['stage'] = 'Step 1: Crossfading tracks...'
        inputs = []
        for p in song_paths:
            inputs += ['-i', str(p)]
        fc_parts, labels = [], []
        for i in range(len(song_paths)):
            si = f's{i}'
            fc_parts.append(f'[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[{si}]')
            labels.append(si)
        prev = labels[0]; idx = 1
        for i in range(1, len(labels)):
            curr = labels[i]; out = f'f{idx}'
            fc_parts.append(f'[{prev}][{curr}]acrossfade=d={crossfade}:c1=tri:c2=tri[{out}]')
            prev = out; idx += 1
        final = 'aout'
        fc_parts.append(f'[{prev}]anull[{final}]')
        playlist_path = tmpdir/'playlist.mp3'
        cmd_playlist = ['ffmpeg','-y'] + inputs + [
            '-filter_complex','; '.join(fc_parts),
            '-map',f'[{final}]','-ar','44100','-ac','2','-c:a','libmp3lame','-b:a',abitrate, str(playlist_path)
        ]
        rc = run_and_stream(cmd_playlist, job_id)
        if rc != 0: raise RuntimeError('FFmpeg crossfade failed')
        if j.get('canceled'): raise RuntimeError('Canceled')

        # Step 2: loop playlist to target length
        j['stage'] = 'Step 2: Looping playlist...'
        out = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1', str(playlist_path)], capture_output=True, text=True)
        try: playlist_sec = float(out.stdout.strip())
        except Exception: playlist_sec = 0.0
        if playlist_sec <= 0: raise RuntimeError('Could not measure playlist duration')
        target_sec = max(60, target_minutes * 60)
        j['target'] = target_sec
        loops = max(0, math.ceil(target_sec/playlist_sec) - 1)
        long_path = tmpdir/'long_playlist.mp3'
        if loops > 0:
            rc = run_and_stream(['ffmpeg','-y','-stream_loop',str(loops),'-i',str(playlist_path),'-c','copy',str(long_path)], job_id)
            if rc != 0: raise RuntimeError('FFmpeg audio loop failed')
        else:
            shutil.copyfile(playlist_path, long_path)
        if j.get('canceled'): raise RuntimeError('Canceled')

        # Step 3: render video
        j['stage'] = 'Step 3: Rendering video...'
        out_path = tmpdir/f'{basename}.mp4'

        if use_video_bg:
            if logo_png:
                filter_complex = build_overlay_filter(logo_png, logo_pos, logo_scale, logo_opacity, resolution)
                cmd = [
                    'ffmpeg','-y','-stream_loop','-1','-i',str(vid_path),
                    '-i',str(logo_png),'-i',str(long_path),
                    '-filter_complex', filter_complex,
                    '-map','[vout]','-map','2:a',
                    '-c:v','libx264','-preset',preset,
                    '-c:a','aac','-b:a',abitrate,
                    '-shortest','-pix_fmt','yuv420p',
                    str(out_path)
                ]
            else:
                cmd = [
                    'ffmpeg','-y','-stream_loop','-1','-i',str(vid_path),
                    '-i',str(long_path),
                    '-c:v','libx264','-preset',preset,
                    '-c:a','aac','-b:a',abitrate,
                    '-shortest','-pix_fmt','yuv420p',
                    '-vf', f'scale={resolution}',
                    str(out_path)
                ]
        else:
            if logo_png:
                filter_complex = build_overlay_filter(logo_png, logo_pos, logo_scale, logo_opacity, resolution)
                cmd = [
                    'ffmpeg','-y','-loop','1','-i',str(img_path),
                    '-i',str(logo_png),'-i',str(long_path),
                    '-filter_complex', filter_complex,
                    '-map','[vout]','-map','2:a',
                    '-c:v','libx264','-preset',preset,'-tune','stillimage',
                    '-c:a','aac','-b:a',abitrate,
                    '-shortest','-pix_fmt','yuv420p',
                    str(out_path)
                ]
            else:
                cmd = [
                    'ffmpeg','-y','-loop','1','-i',str(img_path),
                    '-i',str(long_path),
                    '-c:v','libx264','-preset',preset,'-tune','stillimage',
                    '-c:a','aac','-b:a',abitrate,
                    '-shortest','-pix_fmt','yuv420p',
                    '-vf', f'scale={resolution}',
                    str(out_path)
                ]

        rc = run_and_stream(cmd, job_id)
        if rc != 0: raise RuntimeError('FFmpeg video render failed')

        j['stage'] = 'Done'
        j['done'] = True
        j['outfile'] = str(out_path)

        # Add to available videos for streaming
        VIDEOS[job_id] = {
            'path': str(out_path),
            'name': pathlib.Path(out_path).name,
            'size': pathlib.Path(out_path).stat().st_size if pathlib.Path(out_path).exists() else 0,
            'type': 'rendered',
            'created_at': time.time()
        }
    except Exception as e:
        j['done'] = True
        j['error'] = str(e)
    finally:
        end_job(job_id)

@app.route('/', methods=['GET'])
def index():
    resp = make_response(render_template_string(HTML))
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# ---------- MISSING ROUTES (now added) ----------
@app.route('/enqueue', methods=['POST'])
def enqueue_job():
    job_id = uuid.uuid4().hex
    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix=f"{TMP_PREFIX}{job_id}_"))

    songs = request.files.getlist('songs')
    if not songs or len(songs) < 2:
        shutil.rmtree(tmpdir, ignore_errors=True)
        return redirect(url_for('index'))

    song_paths = []
    for i, f in enumerate(songs):
        ext = pathlib.Path(f.filename).suffix.lower()
        if ext not in ['.mp3','.m4a','.wav']:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return redirect(url_for('index'))
        p = tmpdir / f"song{i+1}{ext}"
        f.save(p)
        song_paths.append(str(p))

    img_path = None; vid_path = None; use_video_bg = False
    if 'video_bg' in request.files and request.files['video_bg'].filename:
        v = request.files['video_bg']
        if pathlib.Path(v.filename).suffix.lower() != '.mp4':
            shutil.rmtree(tmpdir, ignore_errors=True); return redirect(url_for('index'))
        vid_path = str(tmpdir/'loop.mp4'); v.save(vid_path); use_video_bg = True
    elif 'image_bg' in request.files and request.files['image_bg'].filename:
        img = request.files['image_bg']; ext = pathlib.Path(img.filename).suffix.lower()
        if ext not in ['.png','.jpg','.jpeg']:
            shutil.rmtree(tmpdir, ignore_errors=True); return redirect(url_for('index'))
        ip = tmpdir/f"image{ext}"; img.save(ip); img_path = str(ip)
    else:
        shutil.rmtree(tmpdir, ignore_errors=True); return redirect(url_for('index'))

    logo_png = None
    if 'logo_png' in request.files and request.files['logo_png'].filename:
        lg = request.files['logo_png']
        if pathlib.Path(lg.filename).suffix.lower() != '.png':
            shutil.rmtree(tmpdir, ignore_errors=True); return redirect(url_for('index'))
        lp = tmpdir/'logo.png'; lg.save(lp); logo_png = str(lp)

    cfg = {
        'crossfade': request.form.get('crossfade','5'),
        'target_minutes': request.form.get('target_minutes','180'),
        'resolution': request.form.get('resolution','1920x1080'),
        'abitrate': request.form.get('abitrate','192k'),
        'preset': request.form.get('preset','ultrafast'),
        'basename': (request.form.get('basename','lofi_mix') or 'lofi_mix').strip(),
        'tmpdir': str(tmpdir),
        'songs': song_paths,
        'use_video_bg': use_video_bg,
        'img_path': img_path,
        'vid_path': vid_path,
        'logo_png': logo_png,
        'logo_pos': request.form.get('logo_pos','top-left'),
        'logo_scale': request.form.get('logo_scale','18'),
        'logo_opacity': request.form.get('logo_opacity','80')
    }

    JOBS[job_id] = {'id':job_id,'stage':'Queued...','progress':'','log':[],'done':False,'error':None,'outfile':None,'target':None,'canceled':False,'cfg':cfg}
    QUEUE.append(job_id); start_next_if_idle()
    return redirect(url_for('index', **{'job': job_id}))

@app.route('/status/<job_id>', methods=['GET'])
def status(job_id):
    j = JOBS.get(job_id)
    if not j: return jsonify({'error':'not found'}),404
    try: qpos = list(QUEUE).index(job_id) + 1
    except ValueError: qpos = 0 if RUNNING == job_id else None
    return jsonify({
        'stage': j.get('stage',''),
        'progress': j.get('progress',''),
        'done': j.get('done',False),
        'error': j.get('error'),
        'outfile': True if j.get('outfile') else False,
        'target': j.get('target'),
        'canceled': j.get('canceled',False),
        'log': j.get('log',[]),
        'queue_pos': qpos
    })

@app.route('/jobs', methods=['GET'])
def jobs():
    rows = []
    for jid, j in JOBS.items():
        try: qpos = list(QUEUE).index(jid) + 1
        except ValueError: qpos = 0 if RUNNING == jid else None
        rows.append({'id':jid,'stage':j.get('stage',''),'progress':j.get('progress',''),'done':j.get('done',False),'error':j.get('error'),'outfile':True if j.get('outfile') else False,'queue_pos':qpos})
    def keyfun(r):
        if RUNNING == r['id']: return (0,0)
        if r['queue_pos']: return (1,r['queue_pos'])
        return (2,0)
    rows.sort(key=keyfun)
    return jsonify(rows)

@app.route('/cancel/<job_id>', methods=['POST'])
def cancel(job_id):
    j = JOBS.get(job_id)
    if not j: return 'not found',404
    j['canceled'] = True
    try: QUEUE.remove(job_id)
    except ValueError: pass
    if RUNNING == job_id:
        proc = j.get('proc')
        if proc:
            try: proc.terminate()
            except Exception: pass
    return 'ok'

@app.route('/download/<job_id>', methods=['GET'])
def download(job_id):
    j = JOBS.get(job_id)
    if not j or not j.get('outfile'): return 'Not ready',404
    return send_file(j['outfile'], as_attachment=True, download_name=pathlib.Path(j['outfile']).name)

# ===== YouTube Streaming Routes =====
@app.route('/youtube/auth', methods=['GET'])
def youtube_auth():
    """Initiate YouTube OAuth flow"""
    if not YOUTUBE_ENABLED:
        return jsonify({'error': 'YouTube integration not configured'}), 400

    flow = Flow.from_client_secrets_file(
        'youtube_config.json',
        scopes=['https://www.googleapis.com/auth/youtube.force-ssl'],
        redirect_uri=url_for('youtube_callback', _external=True)
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )

    session['oauth_state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback', methods=['GET'])
def youtube_callback():
    """Handle YouTube OAuth callback"""
    if not YOUTUBE_ENABLED:
        return 'YouTube integration not configured', 400

    state = session.get('oauth_state')
    flow = Flow.from_client_secrets_file(
        'youtube_config.json',
        scopes=['https://www.googleapis.com/auth/youtube.force-ssl'],
        state=state,
        redirect_uri=url_for('youtube_callback', _external=True)
    )

    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials

    session['youtube_credentials'] = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }

    return redirect(url_for('index') + '?youtube_auth=success')

@app.route('/youtube/status', methods=['GET'])
def youtube_status():
    """Check if YouTube is authenticated"""
    creds = get_youtube_credentials()
    return jsonify({
        'enabled': YOUTUBE_ENABLED,
        'authenticated': creds is not None
    })

@app.route('/youtube/stream/start', methods=['POST'])
def create_stream_new():
    """Create a YouTube broadcast and start streaming (new endpoint for video_id)"""
    if not YOUTUBE_ENABLED:
        return jsonify({'error': 'YouTube integration not configured'}), 400

    creds = get_youtube_credentials()
    if not creds:
        return jsonify({'error': 'Not authenticated. Please authenticate first.'}), 401

    data = request.get_json() or {}
    video_id = data.get('video_id')

    if not video_id or video_id not in VIDEOS:
        return jsonify({'error': 'Video not found'}), 404

    video_info = VIDEOS[video_id]
    video_path = video_info['path']

    if not pathlib.Path(video_path).exists():
        return jsonify({'error': 'Video file not found'}), 404

    if video_id in STREAMS and STREAMS[video_id].get('status') == 'streaming':
        return jsonify({'error': 'Stream already active for this video'}), 400

    # Get stream parameters
    title = data.get('title', f"Lofi Mix - {time.strftime('%Y-%m-%d %H:%M')}")
    description = data.get('description', 'Lofi music mix created with Lofi Mixer Studio')
    privacy = data.get('privacy', 'unlisted')

    # Create YouTube broadcast
    broadcast_info = create_youtube_broadcast(creds, title, description, privacy)
    if not broadcast_info:
        return jsonify({'error': 'Failed to create YouTube broadcast'}), 500

    # Store stream info
    STREAMS[video_id] = {
        'broadcast_id': broadcast_info['broadcast_id'],
        'stream_id': broadcast_info['stream_id'],
        'watch_url': broadcast_info['watch_url'],
        'status': 'starting',
        'started_at': time.time(),
        'video_name': video_info['name']
    }

    # Start streaming in background
    success = start_youtube_stream(
        video_path,
        broadcast_info['rtmp_url'],
        broadcast_info['stream_key'],
        video_id
    )

    if not success:
        STREAMS.pop(video_id, None)
        return jsonify({'error': 'Failed to start stream'}), 500

    return jsonify({
        'success': True,
        'watch_url': broadcast_info['watch_url'],
        'broadcast_id': broadcast_info['broadcast_id'],
        'video_id': video_id
    })

@app.route('/youtube/stream/<job_id>', methods=['POST'])
def create_stream(job_id):
    """Create a YouTube broadcast and start streaming (legacy endpoint for job_id)"""
    if not YOUTUBE_ENABLED:
        return jsonify({'error': 'YouTube integration not configured'}), 400

    creds = get_youtube_credentials()
    if not creds:
        return jsonify({'error': 'Not authenticated. Please authenticate first.'}), 401

    j = JOBS.get(job_id)
    if not j or not j.get('outfile'):
        return jsonify({'error': 'Video not ready'}), 404

    if job_id in STREAMS and STREAMS[job_id].get('status') == 'streaming':
        return jsonify({'error': 'Stream already active'}), 400

    # Get stream parameters
    data = request.get_json() or {}
    title = data.get('title', f"Lofi Mix - {time.strftime('%Y-%m-%d %H:%M')}")
    description = data.get('description', 'Lofi music mix created with Lofi Mixer Studio')
    privacy = data.get('privacy', 'unlisted')

    # Create YouTube broadcast
    broadcast_info = create_youtube_broadcast(creds, title, description, privacy)
    if not broadcast_info:
        return jsonify({'error': 'Failed to create YouTube broadcast'}), 500

    # Store stream info
    STREAMS[job_id] = {
        'broadcast_id': broadcast_info['broadcast_id'],
        'stream_id': broadcast_info['stream_id'],
        'watch_url': broadcast_info['watch_url'],
        'status': 'starting',
        'started_at': time.time()
    }

    # Start streaming in background
    success = start_youtube_stream(
        j['outfile'],
        broadcast_info['rtmp_url'],
        broadcast_info['stream_key'],
        job_id
    )

    if not success:
        STREAMS.pop(job_id, None)
        return jsonify({'error': 'Failed to start stream'}), 500

    return jsonify({
        'success': True,
        'watch_url': broadcast_info['watch_url'],
        'broadcast_id': broadcast_info['broadcast_id']
    })

@app.route('/youtube/stream/<job_id>/stop', methods=['POST'])
def stop_stream(job_id):
    """Stop an active YouTube stream"""
    if job_id not in STREAMS:
        return jsonify({'error': 'No active stream'}), 404

    success = stop_youtube_stream(job_id)
    return jsonify({'success': success})

@app.route('/youtube/stream/<job_id>/status', methods=['GET'])
def stream_status(job_id):
    """Get stream status"""
    if job_id not in STREAMS:
        return jsonify({'active': False})

    stream_info = STREAMS[job_id]
    return jsonify({
        'active': True,
        'status': stream_info.get('status'),
        'watch_url': stream_info.get('watch_url'),
        'started_at': stream_info.get('started_at'),
        'last_output': stream_info.get('last_output', '')
    })

@app.route('/videos/upload', methods=['POST'])
def upload_video():
    """Upload a video file for streaming"""
    if 'stream_video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400

    video_file = request.files['stream_video']
    if not video_file.filename:
        return jsonify({'error': 'No video selected'}), 400

    if not video_file.filename.lower().endswith('.mp4'):
        return jsonify({'error': 'Only MP4 files are supported'}), 400

    # Create uploads directory if it doesn't exist
    uploads_dir = pathlib.Path('uploads')
    uploads_dir.mkdir(exist_ok=True)

    # Generate unique ID and save file
    video_id = uuid.uuid4().hex
    filename = f"{video_id}_{video_file.filename}"
    filepath = uploads_dir / filename

    video_file.save(str(filepath))

    # Add to videos catalog
    VIDEOS[video_id] = {
        'path': str(filepath),
        'name': video_file.filename,
        'size': filepath.stat().st_size,
        'type': 'uploaded',
        'created_at': time.time()
    }

    return jsonify({
        'success': True,
        'video_id': video_id,
        'name': video_file.filename
    })

@app.route('/videos/list', methods=['GET'])
def list_videos():
    """List all available videos for streaming"""
    videos_list = []
    for vid_id, vid_info in VIDEOS.items():
        # Check if file still exists
        if pathlib.Path(vid_info['path']).exists():
            videos_list.append({
                'id': vid_id,
                'name': vid_info['name'],
                'size': vid_info['size'],
                'type': vid_info['type'],
                'created_at': vid_info['created_at']
            })

    # Sort by creation time, newest first
    videos_list.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify(videos_list)

@app.route('/videos/<video_id>', methods=['DELETE'])
def delete_video(video_id):
    """Delete an uploaded video"""
    if video_id not in VIDEOS:
        return jsonify({'error': 'Video not found'}), 404

    video_info = VIDEOS[video_id]

    # Only allow deleting uploaded videos, not rendered ones
    if video_info['type'] == 'uploaded':
        try:
            pathlib.Path(video_info['path']).unlink(missing_ok=True)
            del VIDEOS[video_id]
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    else:
        return jsonify({'error': 'Cannot delete rendered videos'}), 400

# ----------------- server -----------------
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5050)
