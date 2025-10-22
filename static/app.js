// Lofi Mixer Studio - Client-side JavaScript

let currentJobId = null;
let pollInterval = null;

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
