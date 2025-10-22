// Lofi Mixer Studio - Client-side JavaScript

let currentJobId = null;
let pollInterval = null;
let streamPollInterval = null;
let youtubeEnabled = false;
let youtubeAuthenticated = false;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initializeForm();
    updateJobsList();

    // Check if we have a job parameter in URL
    const params = new URLSearchParams(window.location.search);
    const jobParam = params.get('job');
    if (jobParam) {
        currentJobId = jobParam;
        showProgressCard();
        startPolling();
    }

    // Poll jobs list periodically
    setInterval(updateJobsList, 3000);

    // Check YouTube authentication status
    checkYouTubeStatus();

    // Check for YouTube auth success
    if (params.get('youtube_auth') === 'success') {
        checkYouTubeStatus();
        alert('Successfully connected to YouTube!');
        // Remove the parameter from URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});

function initializeForm() {
    // Auto-fill basename with current date/time
    const now = new Date();
    const dateStr = now.toISOString().slice(0,16).replace('T','_').replace(/:/g,'');
    document.getElementById('basename').value = `lofi_mix_${dateStr}`;

    // File input handlers
    const songInput = document.getElementById('songInput');
    const imgInput = document.getElementById('imgInput');
    const vidInput = document.getElementById('vidInput');

    if (songInput) {
        songInput.addEventListener('change', function() {
            const files = this.files;
            const listDiv = document.getElementById('songList');
            if (files.length > 0) {
                const names = Array.from(files).map(f => f.name).join(', ');
                listDiv.textContent = `${files.length} file(s): ${names}`;
            } else {
                listDiv.textContent = '';
            }
        });
    }

    if (imgInput && vidInput) {
        imgInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                vidInput.value = '';
                updateBgPreview();
            }
        });

        vidInput.addEventListener('change', function() {
            if (this.files.length > 0) {
                imgInput.value = '';
                updateBgPreview();
            }
        });
    }
}

function updateBgPreview() {
    const imgInput = document.getElementById('imgInput');
    const vidInput = document.getElementById('vidInput');
    const preview = document.getElementById('bgPreview');

    if (imgInput.files.length > 0) {
        preview.textContent = `Image: ${imgInput.files[0].name}`;
    } else if (vidInput.files.length > 0) {
        preview.textContent = `Video: ${vidInput.files[0].name}`;
    } else {
        preview.textContent = '';
    }
}

function startBuild() {
    // Validate form
    const songInput = document.getElementById('songInput');
    const imgInput = document.getElementById('imgInput');
    const vidInput = document.getElementById('vidInput');

    if (!songInput.files || songInput.files.length < 2 || songInput.files.length > 10) {
        alert('Please select between 2 and 10 song files');
        return false;
    }

    if ((!imgInput.files || imgInput.files.length === 0) &&
        (!vidInput.files || vidInput.files.length === 0)) {
        alert('Please select either a background image or video');
        return false;
    }

    // Form will submit normally, then we'll get redirected with job param
    return true;
}

function showProgressCard() {
    document.getElementById('progressCard').style.display = 'block';
}

function startPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
    }

    pollInterval = setInterval(function() {
        if (currentJobId) {
            updateProgress(currentJobId);
        }
    }, 1000);

    // Immediate update
    updateProgress(currentJobId);
}

function updateProgress(jobId) {
    fetch(`/status/${jobId}`)
        .then(res => res.json())
        .then(data => {
            const stageEl = document.getElementById('stage');
            const barEl = document.getElementById('bar');
            const logBox = document.getElementById('logBox');
            const qposEl = document.getElementById('qpos');
            const etaEl = document.getElementById('eta');
            const downloadLink = document.getElementById('downloadLink');

            if (stageEl) stageEl.textContent = data.stage || 'Unknown';

            // Update queue position
            if (qposEl) {
                if (data.queue_pos > 0) {
                    qposEl.textContent = data.queue_pos;
                } else if (data.queue_pos === 0) {
                    qposEl.textContent = 'Running now';
                } else {
                    qposEl.textContent = 'Complete';
                }
            }

            // Calculate progress and ETA
            if (data.target && data.progress) {
                const match = data.progress.match(/time=(\d+):(\d+):(\d+)/);
                if (match) {
                    const hours = parseInt(match[1]);
                    const minutes = parseInt(match[2]);
                    const seconds = parseInt(match[3]);
                    const currentTime = hours * 3600 + minutes * 60 + seconds;
                    const percent = Math.min(100, (currentTime / data.target) * 100);

                    if (barEl) barEl.style.width = percent + '%';

                    if (percent > 0 && percent < 100) {
                        const remaining = data.target - currentTime;
                        const mins = Math.floor(remaining / 60);
                        const secs = remaining % 60;
                        if (etaEl) etaEl.textContent = `~${mins}m ${secs}s`;
                    }
                }
            }

            // Update log
            if (logBox && data.log) {
                const lastLines = data.log.slice(-20).join('\n');
                logBox.textContent = lastLines || 'Waiting...';
                logBox.scrollTop = logBox.scrollHeight;
            }

            // Handle completion
            if (data.done) {
                if (data.error) {
                    if (stageEl) stageEl.textContent = `Error: ${data.error}`;
                    if (barEl) barEl.style.width = '0%';
                    if (etaEl) etaEl.textContent = 'Failed';
                } else if (data.outfile) {
                    if (stageEl) stageEl.textContent = 'Complete!';
                    if (barEl) barEl.style.width = '100%';
                    if (etaEl) etaEl.textContent = 'Done';
                    if (downloadLink) {
                        downloadLink.href = `/download/${jobId}`;
                        downloadLink.style.display = 'inline-block';
                    }
                    // Show YouTube button if enabled
                    const youtubeBtn = document.getElementById('youtubeBtn');
                    if (youtubeBtn && youtubeEnabled) {
                        youtubeBtn.style.display = 'inline-block';
                    }
                }

                // Stop polling when done
                if (pollInterval) {
                    clearInterval(pollInterval);
                    pollInterval = null;
                }
            }
        })
        .catch(err => {
            console.error('Error polling status:', err);
        });
}

function updateJobsList() {
    fetch('/jobs')
        .then(res => res.json())
        .then(jobs => {
            const tbody = document.getElementById('jobsBody');
            if (!tbody) return;

            tbody.innerHTML = '';

            jobs.forEach(job => {
                const tr = document.createElement('tr');

                // Job ID (shortened)
                const tdId = document.createElement('td');
                tdId.textContent = job.id.slice(0, 8) + '...';
                tdId.style.fontFamily = 'monospace';
                tdId.style.fontSize = '11px';
                tr.appendChild(tdId);

                // Status
                const tdStatus = document.createElement('td');
                if (job.error) {
                    tdStatus.textContent = 'Error';
                    tdStatus.style.color = '#ef4444';
                } else if (job.done) {
                    tdStatus.textContent = 'Done';
                    tdStatus.style.color = '#22c55e';
                } else {
                    tdStatus.textContent = job.stage || 'Running';
                }
                tr.appendChild(tdStatus);

                // Queue position
                const tdQueue = document.createElement('td');
                if (job.queue_pos > 0) {
                    tdQueue.textContent = `#${job.queue_pos}`;
                } else if (job.queue_pos === 0) {
                    tdQueue.textContent = 'Active';
                    tdQueue.style.color = '#22c55e';
                } else {
                    tdQueue.textContent = '-';
                }
                tr.appendChild(tdQueue);

                // Progress
                const tdProgress = document.createElement('td');
                if (job.progress) {
                    const match = job.progress.match(/time=(\d+):(\d+):(\d+)/);
                    if (match) {
                        tdProgress.textContent = `${match[1]}:${match[2]}:${match[3]}`;
                        tdProgress.style.fontFamily = 'monospace';
                        tdProgress.style.fontSize = '11px';
                    } else {
                        tdProgress.textContent = '-';
                    }
                } else {
                    tdProgress.textContent = '-';
                }
                tr.appendChild(tdProgress);

                // Output
                const tdOutput = document.createElement('td');
                if (job.outfile && job.done && !job.error) {
                    const downloadBtn = document.createElement('a');
                    downloadBtn.href = `/download/${job.id}`;
                    downloadBtn.textContent = 'Download';
                    downloadBtn.className = 'btn';
                    downloadBtn.style.padding = '6px 12px';
                    downloadBtn.style.fontSize = '12px';
                    downloadBtn.style.textDecoration = 'none';
                    downloadBtn.style.display = 'inline-block';
                    tdOutput.appendChild(downloadBtn);
                } else {
                    tdOutput.textContent = '-';
                }
                tr.appendChild(tdOutput);

                // Actions
                const tdAction = document.createElement('td');
                if (!job.done) {
                    const cancelBtn = document.createElement('button');
                    cancelBtn.textContent = 'Cancel';
                    cancelBtn.className = 'btn';
                    cancelBtn.style.padding = '6px 12px';
                    cancelBtn.style.fontSize = '12px';
                    cancelBtn.onclick = () => cancelJob(job.id);
                    tdAction.appendChild(cancelBtn);
                } else {
                    tdAction.textContent = '-';
                }
                tr.appendChild(tdAction);

                tbody.appendChild(tr);
            });
        })
        .catch(err => {
            console.error('Error fetching jobs:', err);
        });
}

function cancelSelf() {
    if (currentJobId && confirm('Cancel this job?')) {
        cancelJob(currentJobId);
    }
}

function cancelJob(jobId) {
    fetch(`/cancel/${jobId}`, { method: 'POST' })
        .then(() => {
            updateJobsList();
            if (jobId === currentJobId) {
                if (pollInterval) {
                    clearInterval(pollInterval);
                    pollInterval = null;
                }
                document.getElementById('stage').textContent = 'Canceled';
            }
        })
        .catch(err => {
            console.error('Error canceling job:', err);
            alert('Failed to cancel job');
        });
}

// ===== YouTube Streaming Functions =====

function checkYouTubeStatus() {
    fetch('/youtube/status')
        .then(res => res.json())
        .then(data => {
            youtubeEnabled = data.enabled;
            youtubeAuthenticated = data.authenticated;
        })
        .catch(err => {
            console.error('Error checking YouTube status:', err);
        });
}

function authenticateYouTube() {
    window.location.href = '/youtube/auth';
}

function showYoutubeModal() {
    const modal = document.getElementById('youtubeModal');
    const authSection = document.getElementById('youtubeAuthSection');
    const setupSection = document.getElementById('youtubeStreamSetup');
    const activeSection = document.getElementById('youtubeStreamActive');

    modal.style.display = 'block';

    // Check if already streaming
    fetch(`/youtube/stream/${currentJobId}/status`)
        .then(res => res.json())
        .then(data => {
            if (data.active) {
                authSection.style.display = 'none';
                setupSection.style.display = 'none';
                activeSection.style.display = 'block';
                document.getElementById('watchUrl').href = data.watch_url;
                document.getElementById('watchUrl').textContent = data.watch_url;
                document.getElementById('streamStatus').textContent = data.status;
                startStreamPolling();
            } else if (youtubeAuthenticated) {
                authSection.style.display = 'none';
                setupSection.style.display = 'block';
                activeSection.style.display = 'none';
            } else {
                authSection.style.display = 'block';
                setupSection.style.display = 'none';
                activeSection.style.display = 'none';
            }
        })
        .catch(err => {
            console.error('Error checking stream status:', err);
        });
}

function hideYoutubeModal() {
    document.getElementById('youtubeModal').style.display = 'none';
    if (streamPollInterval) {
        clearInterval(streamPollInterval);
        streamPollInterval = null;
    }
}

function startYouTubeStream() {
    const title = document.getElementById('streamTitle').value || 'Lofi Mix Stream';
    const description = document.getElementById('streamDesc').value || 'Lofi music mix';
    const privacy = document.getElementById('streamPrivacy').value;

    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Creating broadcast...';

    fetch(`/youtube/stream/${currentJobId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description, privacy })
    })
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                alert('Error: ' + data.error);
                btn.disabled = false;
                btn.textContent = 'Start Streaming';
            } else {
                // Show active stream section
                document.getElementById('youtubeStreamSetup').style.display = 'none';
                document.getElementById('youtubeStreamActive').style.display = 'block';
                document.getElementById('watchUrl').href = data.watch_url;
                document.getElementById('watchUrl').textContent = data.watch_url;
                startStreamPolling();
            }
        })
        .catch(err => {
            console.error('Error starting stream:', err);
            alert('Failed to start stream');
            btn.disabled = false;
            btn.textContent = 'Start Streaming';
        });
}

function stopYouTubeStream() {
    if (!confirm('Stop the YouTube stream?')) return;

    fetch(`/youtube/stream/${currentJobId}/stop`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert('Stream stopped successfully');
                hideYoutubeModal();
            } else {
                alert('Failed to stop stream');
            }
        })
        .catch(err => {
            console.error('Error stopping stream:', err);
            alert('Failed to stop stream');
        });
}

function startStreamPolling() {
    if (streamPollInterval) {
        clearInterval(streamPollInterval);
    }

    streamPollInterval = setInterval(() => {
        fetch(`/youtube/stream/${currentJobId}/status`)
            .then(res => res.json())
            .then(data => {
                if (data.active) {
                    const statusEl = document.getElementById('streamStatus');
                    if (statusEl) {
                        statusEl.textContent = data.status || 'Unknown';
                    }
                } else {
                    // Stream no longer active
                    if (streamPollInterval) {
                        clearInterval(streamPollInterval);
                        streamPollInterval = null;
                    }
                }
            })
            .catch(err => {
                console.error('Error polling stream status:', err);
            });
    }, 2000);
}
