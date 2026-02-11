let currentData = null;
let dnaChart = null;
let audioPlayer = null;
let isPlaying = false;

document.addEventListener('DOMContentLoaded', () => {
    // Audio Player Init
    audioPlayer = document.getElementById('audio-player');
    const playBtn = document.getElementById('play-pause-btn');
    const seekSlider = document.getElementById('seek-slider');
    const volumeSlider = document.getElementById('volume-slider');

    // Play/Pause
    playBtn.addEventListener('click', togglePlay);

    // Seek
    audioPlayer.addEventListener('timeupdate', updateProgress);
    seekSlider.addEventListener('input', (e) => {
        const time = (audioPlayer.duration * e.target.value) / 100;
        audioPlayer.currentTime = time;
    });

    // Volume
    volumeSlider.addEventListener('input', (e) => {
        audioPlayer.volume = e.target.value;
    });

    // Audio Meta
    audioPlayer.addEventListener('loadedmetadata', () => {
        const d = formatTime(audioPlayer.duration);
        document.getElementById('duration-time').textContent = d;
        // Only update metadata text if it was previously "UNKNOWN" or just to be safe/consistent
        document.getElementById('metadata-display').textContent = "PROCESSED • " + d;
    });

    // Clerk Logic for Welcome
    initClerkWelcome();

    // Initialize History
    loadHistory();
});

// --- CLERK WELCOME ---
async function initClerkWelcome() {
    if (window.Clerk) {
        await window.Clerk.load();
        if (window.Clerk.user) {
            // Update Welcome Text
            if (document.getElementById('username-display')) {
                document.getElementById('username-display').textContent = window.Clerk.user.firstName || window.Clerk.user.username || "Creator";
            }

            // Update Avatar
            const avatarContainer = document.getElementById('user-avatar');
            if (avatarContainer && window.Clerk.user.imageUrl) {
                avatarContainer.innerHTML = ''; // Clear existing
                const img = document.createElement('img');
                img.src = window.Clerk.user.imageUrl;
                img.className = "w-full h-full object-cover";
                avatarContainer.appendChild(img);
            }

            // Show guide if first time (using local storage)
            const hasSeenGuide = localStorage.getItem('hasSeenGuide_v2');
            if (!hasSeenGuide) {
                document.getElementById('guide-modal').classList.remove('hidden');
            }
        }
    }
}

function closeGuide() {
    document.getElementById('guide-modal').classList.add('hidden');
    localStorage.setItem('hasSeenGuide_v2', 'true');
}


// --- MAIN UPLOAD FLOW ---

function triggerUpload() {
    document.getElementById('fileInput').click();
}

function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) uploadFile(file);
}

function handleDrop(event) {
    event.preventDefault();
    const file = event.dataTransfer.files[0];
    if (file) uploadFile(file);
}

function handleDragOver(event) { event.preventDefault(); }
function handleDragLeave(event) { event.preventDefault(); }

function uploadFile(file) {
    const statusDiv = document.getElementById('upload-status');
    const uploadBtn = document.getElementById('upload-btn');

    statusDiv.classList.remove('hidden');
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<span class="material-symbols-outlined animate-spin">sync</span> AI Processing...';

    const formData = new FormData();
    formData.append('audio', file);

    fetch('/upload', { method: 'POST', body: formData })
        .then(r => r.json())
        .then(data => {
            if (data.error) throw new Error(data.error);

            // Use the unified render function
            renderDashboard(data);

            loadHistory(); // Refresh history list
        })
        .catch(e => {
            alert("Upload Failed: " + e.message);
            resetUploadState();
        })
        .finally(() => {
            document.body.style.cursor = 'default';
        });
}

function resetUploadState() {
    const statusDiv = document.getElementById('upload-status');
    const uploadBtn = document.getElementById('upload-btn');
    statusDiv.classList.add('hidden');
    uploadBtn.innerHTML = `Start Transcribing`;
    uploadBtn.disabled = false;
}

function renderDashboard(data) {
    currentData = data; // Global current state

    // 1. Toggle Sections
    document.getElementById('upload-section').classList.add('hidden');
    const dashboard = document.getElementById('dashboard-section');
    dashboard.classList.remove('hidden');
    setTimeout(() => dashboard.classList.remove('opacity-0'), 50);

    // 2. Populate Data
    document.getElementById('filename-display').textContent = data.filename || "Audio File";
    document.getElementById('metadata-display').textContent = `Processed • ${data.duration ? data.duration.toFixed(2) + 's' : 'Unknown Duration'}`;

    document.getElementById('transcript-content').textContent = data.transcript || "No transcript available.";

    // Summary
    const summaryText = data.summary || "No summary available.";
    document.getElementById('summary-content').textContent = summaryText;

    // Metrics
    document.getElementById('insight-word-count').textContent = data.word_count || 0;
    const conf = data.confidence_score ? (data.confidence_score * 100).toFixed(1) : 95.0;
    document.getElementById('insight-confidence').textContent = conf + "%";

    // Bullets (Key Highlights)
    const bulletsList = document.getElementById('insight-bullets');
    bulletsList.innerHTML = '';
    if (data.key_points && Array.isArray(data.key_points)) {
        data.key_points.forEach(point => {
            const li = document.createElement('li');
            li.className = 'text-xs text-slate-300 flex items-start gap-2 leading-relaxed';
            li.innerHTML = `<span class="text-[#00f2ff] mt-1">•</span> ${point}`;
            bulletsList.appendChild(li);
        });
    }

    // Keywords
    const keywordsContainer = document.getElementById('keywords-container');
    keywordsContainer.innerHTML = '';
    if (data.keywords && Array.isArray(data.keywords)) {
        data.keywords.forEach(kw => {
            const span = document.createElement('span');
            span.className = 'px-2 py-1 bg-white/5 rounded-md text-[10px] font-bold uppercase tracking-widest text-[#bc13fe] border border-white/5';
            span.textContent = kw;
            keywordsContainer.appendChild(span);
        });
    }

    // 3. Setup Audio
    const audioPlayer = document.getElementById('audio-player');

    // Determine Audio Source
    // If history item lacks audio_url, construct it from filename
    let audioSrc = data.audio_url;
    if (!audioSrc && data.filename) {
        audioSrc = '/uploads/' + data.filename;
    }

    // Reset Player
    audioPlayer.pause();
    document.getElementById('play-pause-btn').innerHTML = '<span class="material-symbols-outlined font-black text-2xl">play_arrow</span>';
    document.getElementById('progress-bar').style.width = '0%';
    document.getElementById('seek-slider').value = 0;

    if (audioSrc) {
        audioPlayer.src = audioSrc;
        audioPlayer.load();
    }

    // Update Player UI Headers
    document.getElementById('filename-display').textContent = data.filename || 'Audio File';

    // Duration Logic
    // If we have stored duration, use it immediately
    if (data.duration) {
        document.getElementById('duration-time').textContent = formatTime(data.duration);
        document.getElementById('metadata-display').textContent = "PROCESSED • " + formatTime(data.duration);
    } else {
        document.getElementById('duration-time').textContent = "--:--";
        document.getElementById('metadata-display').textContent = "PROCESSED • UNKNOWN DURATION";
    }

    // 4. Render Chart
    if (data.sonic_dna) {
        renderRadarChart(data.sonic_dna);
    }
}


// --- CHART.JS ---
function renderRadarChart(dna) {
    const ctx = document.getElementById('dnaChart').getContext('2d');

    // Destroy previous if exists
    if (dnaChart) dnaChart.destroy();

    const energy = dna ? dna.energy : 50;
    const pace = dna ? dna.pace : 50;
    // Normalized pace: say max is 250wpm. 
    // Just for viz, let's cap at 100 for the chart scale
    const paceNorm = Math.min((pace / 200) * 100, 100);
    const clarity = dna ? dna.clarity : 50;

    dnaChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Energy', 'Pace', 'Clarity'],
            datasets: [{
                label: 'Sonic Profile',
                data: [energy, paceNorm, clarity],
                backgroundColor: 'rgba(188, 19, 254, 0.2)', // Purple transparent
                borderColor: '#bc13fe',
                pointBackgroundColor: '#00f2ff',
                pointBorderColor: '#fff',
                pointHoverBackgroundColor: '#fff',
                pointHoverBorderColor: '#00f2ff',
                borderWidth: 2
            }]
        },
        options: {
            scales: {
                r: {
                    angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    pointLabels: {
                        color: '#94a3b8',
                        font: { size: 10, family: 'Space Grotesk' }
                    },
                    ticks: { display: false, max: 100, min: 0 }
                }
            },
            plugins: {
                legend: { display: false }
            },
            maintainAspectRatio: false
        }
    });
}


// --- AUDIO CONTROLS ---

function togglePlay() {
    if (audioPlayer.paused) {
        audioPlayer.play();
        document.getElementById('play-pause-btn').innerHTML = '<span class="material-symbols-outlined text-3xl font-black">pause</span>';
    } else {
        audioPlayer.pause();
        document.getElementById('play-pause-btn').innerHTML = '<span class="material-symbols-outlined text-3xl font-black">play_arrow</span>';
    }
}

function skip(seconds) {
    audioPlayer.currentTime += seconds;
}

function updateProgress() {
    const { duration, currentTime } = audioPlayer;
    if (isNaN(duration)) return;

    const percent = (currentTime / duration) * 100;
    document.getElementById('progress-bar').style.width = `${percent}%`;
    document.getElementById('seek-slider').value = percent;
    document.getElementById('current-time').textContent = formatTime(currentTime);
}

function formatTime(s) {
    const min = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${min}:${sec < 10 ? '0' + sec : sec}`;
}


// --- UTILS ---

function copyToClipboard(elementId) {
    const text = document.getElementById(elementId).textContent;
    navigator.clipboard.writeText(text).then(() => {
        alert("Copied to clipboard!");
    });
}

function translateContent(lang) {
    if (!currentData) return;

    document.body.style.cursor = 'wait';

    // Get current text content to translate (in case it was edited, or just use currentData)
    // Using currentData ensures we translate the original valid text, 
    // but if we want to translate what's on screen (which might be already translated), 
    // we should use the DOM. However, repeatedly translating translations is bad. 
    // Let's stick to translating the original source for better quality, 
    // OR translate the current DOM if we want to support editing.
    // User request implies "The translation button...". 
    // Let's send the text from the DOM to be safe, or currentData.

    fetch('/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            transcript: currentData.transcript,
            summary: currentData.summary,
            target_lang: lang
        })
    })
        .then(r => r.json())
        .then(data => {
            if (data.translated_transcript) {
                document.getElementById('transcript-content').textContent = data.translated_transcript;
            }
            if (data.translated_summary) {
                document.getElementById('summary-content').textContent = data.translated_summary;
            }

            if (!data.error) {
                alert('Translation completed for Transcript and Summary.');
            } else {
                alert('Translation error: ' + data.error);
            }
        })
        .catch(err => {
            alert('Translation failed: ' + err);
        })
        .finally(() => {
            document.body.style.cursor = 'default';
        });
}

function loadHistory() {
    const container = document.getElementById('history-container');
    fetch('/history')
        .then(r => r.json())
        .then(files => {
            historyData = files; // Store globally
            container.innerHTML = '';
            if (files.length === 0) {
                container.innerHTML = '<p class="text-slate-500 text-xs text-center italic">No recent uploads found.</p>';
                return;
            }
            files.forEach(item => {
                const fileName = item.filename || item;
                // Use a safe onclick handler
                const div = document.createElement('div');
                div.className = 'flex items-center justify-between p-3 hover:bg-white/5 rounded-xl cursor-pointer group transition-colors border-b border-white/5 last:border-0';
                div.innerHTML = `
                <div class="flex items-center gap-3" onclick="loadFromHistory('${fileName}')">
                    <div class="w-8 h-8 rounded-lg bg-[#bc13fe]/20 flex items-center justify-center">
                        <span class="material-symbols-outlined text-[#bc13fe] text-xs">graphic_eq</span>
                    </div>
                    <span class="text-sm font-bold text-slate-300 group-hover:text-white">${fileName}</span>
                </div>
                 <div class="flex gap-2">
                    <button class="text-xs text-[#00f2ff] hover:underline" onclick="loadFromHistory('${fileName}')">Load</button>
                    <button onclick="deleteFile('${fileName}', event)" class="text-slate-500 hover:text-red-500">
                        <span class="material-symbols-outlined text-sm">delete</span>
                    </button>
                </div>
            `;
                container.appendChild(div);
            });
        });
}

function loadFromHistory(filename) {
    const item = historyData.find(f => (f.filename || f) === filename);
    if (item) {
        renderDashboard(item);
        // Scroll to dashboard
        document.getElementById('dashboard-section').scrollIntoView({ behavior: 'smooth' });
    } else {
        alert("File data not found in local history.");
    }
}

function deleteFile(filename, event) {
    if (event) event.stopPropagation();
    if (!confirm('Delete ' + filename + '?')) return;
    fetch('/delete/' + filename, { method: 'DELETE' }).then(loadHistory);
}

function toggleHistory() {
    const h = document.getElementById('history-container');
    h.classList.toggle('hidden');
}

function downloadPDF() {
    if (!currentData) return;
    // same logic as before...
    fetch('/download_pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: currentData.filename || 'Transcript',
            transcript: document.getElementById('transcript-content').textContent,
            summary: document.getElementById('summary-content').textContent
        })
    })
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = (currentData.filename || 'transcript') + "_report.pdf";
            document.body.appendChild(a);
            a.click();
        });
}
