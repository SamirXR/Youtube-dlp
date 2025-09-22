// Application State
let currentVideoInfo = null;
let selectedFormat = null;
let isTrimmingEnabled = false;

// DOM Elements
const urlForm = document.getElementById('url-form');
const videoUrlInput = document.getElementById('video-url');
const fetchBtn = document.getElementById('fetch-btn');
const loading = document.getElementById('loading');
const videoInfoSection = document.getElementById('video-info-section');
const formatSection = document.getElementById('format-section');
const trimmingSection = document.getElementById('trimming-section');
const downloadSection = document.getElementById('download-section');
const formatsGrid = document.getElementById('formats-grid');
const enableTrimmingCheckbox = document.getElementById('enable-trimming');
const trimInputs = document.getElementById('trim-inputs');
const startTimeInput = document.getElementById('start-time');
const endTimeInput = document.getElementById('end-time');
const trimDurationSpan = document.getElementById('trim-duration');
const downloadBtn = document.getElementById('download-btn');
const downloadProgress = document.getElementById('download-progress');
const downloadResult = document.getElementById('download-result');
const errorModal = document.getElementById('error-modal');
const errorMessage = document.getElementById('error-message');
const closeErrorModal = document.getElementById('close-error-modal');
const errorOkBtn = document.getElementById('error-ok-btn');
const downloadAnotherBtn = document.getElementById('download-another');

// Utility Functions
function showError(message) {
    errorMessage.textContent = message;
    errorModal.classList.remove('hidden');
}

function hideError() {
    errorModal.classList.add('hidden');
}

function showSection(section) {
    section.classList.remove('hidden');
    section.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function hideSection(section) {
    section.classList.add('hidden');
}

function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return 'Unknown';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
}

function formatDuration(seconds) {
    if (!seconds) return 'Unknown';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function parseTimeToSeconds(timeStr) {
    if (!timeStr || !timeStr.match(/^\d{1,2}:\d{2}$/)) {
        return null;
    }
    
    const [minutes, seconds] = timeStr.split(':').map(Number);
    if (seconds >= 60) return null;
    
    return minutes * 60 + seconds;
}

function secondsToTimeStr(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

function updateTrimDuration() {
    const startSeconds = parseTimeToSeconds(startTimeInput.value);
    const endSeconds = parseTimeToSeconds(endTimeInput.value);
    
    if (startSeconds !== null && endSeconds !== null && endSeconds > startSeconds) {
        const duration = endSeconds - startSeconds;
        trimDurationSpan.textContent = `Clip duration: ${secondsToTimeStr(duration)}`;
        trimDurationSpan.className = 'text-success';
    } else {
        trimDurationSpan.textContent = 'Clip duration: Invalid times';
        trimDurationSpan.className = 'text-error';
    }
}

function validateTrimTimes() {
    if (!isTrimmingEnabled) return true;
    
    const startSeconds = parseTimeToSeconds(startTimeInput.value);
    const endSeconds = parseTimeToSeconds(endTimeInput.value);
    
    if (startSeconds === null) {
        showError('Invalid start time format. Use MM:SS (e.g., 2:05)');
        return false;
    }
    
    if (endSeconds === null) {
        showError('Invalid end time format. Use MM:SS (e.g., 2:35)');
        return false;
    }
    
    if (endSeconds <= startSeconds) {
        showError('End time must be after start time');
        return false;
    }
    
    if (currentVideoInfo && currentVideoInfo.duration) {
        if (startSeconds >= currentVideoInfo.duration) {
            showError('Start time cannot be greater than video duration');
            return false;
        }
        
        if (endSeconds > currentVideoInfo.duration) {
            showError('End time cannot be greater than video duration');
            return false;
        }
    }
    
    return true;
}

// API Functions
async function fetchVideoInfo(url) {
    try {
        const response = await fetch('/api/video-info', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url }),
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to fetch video information');
        }
        
        return await response.json();
    } catch (error) {
        throw new Error(`Failed to fetch video info: ${error.message}`);
    }
}

async function downloadVideo(url, formatId, trimTimes = null) {
    try {
        const payload = {
            url: url,
            format_id: formatId,
            trim_times: trimTimes
        };
        
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload),
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Download failed');
        }
        
        const result = await response.json();
        return { success: true, message: 'Download completed successfully!' };
    } catch (error) {
        throw new Error(`Download failed: ${error.message}`);
    }
}

// UI Functions
function displayVideoInfo(videoInfo) {
    currentVideoInfo = videoInfo;
    
    // Update thumbnail
    const thumbnail = document.getElementById('video-thumbnail');
    thumbnail.src = videoInfo.thumbnail || '/static/images/default-thumbnail.jpg';
    thumbnail.alt = videoInfo.title || 'Video thumbnail';
    
    // Update duration badge
    const durationBadge = document.getElementById('duration-badge');
    durationBadge.textContent = formatDuration(videoInfo.duration);
    
    // Update video details
    document.getElementById('video-title').textContent = videoInfo.title || 'Unknown Title';
    document.getElementById('video-uploader').textContent = videoInfo.uploader || 'Unknown Uploader';
    document.getElementById('video-duration').textContent = formatDuration(videoInfo.duration);
    
    // Update view count if available
    const viewsElement = document.getElementById('video-views');
    if (videoInfo.view_count) {
        viewsElement.textContent = new Intl.NumberFormat().format(videoInfo.view_count);
    } else {
        viewsElement.textContent = 'N/A';
    }
    
    showSection(videoInfoSection);
}

function displayFormats(formats) {
    formatsGrid.innerHTML = '';
    
    // Filter and sort formats
    const videoFormats = formats
        .filter(fmt => fmt.vcodec && fmt.vcodec !== 'none')
        .sort((a, b) => (b.height || 0) - (a.height || 0))
        .slice(0, 12); // Show top 12 formats
    
    videoFormats.forEach((format, index) => {
        const formatCard = document.createElement('div');
        formatCard.className = 'format-card';
        formatCard.dataset.formatId = format.format_id;
        formatCard.dataset.ext = format.ext;
        
        const quality = format.height ? `${format.height}p` : 'Unknown';
        const fps = format.fps ? `${format.fps}fps` : '';
        const codec = format.vcodec ? format.vcodec.split('.')[0] : 'Unknown';
        const size = formatFileSize(format.filesize);
        
        formatCard.innerHTML = `
            <div class="format-header">
                <div class="format-quality">${quality}</div>
                <div class="format-size">${size}</div>
            </div>
            <div class="format-details">
                <span>${format.ext?.toUpperCase()}</span>
                <span>${fps}</span>
                <span>${codec}</span>
            </div>
        `;
        
        formatCard.addEventListener('click', () => selectFormat(formatCard, format));
        formatsGrid.appendChild(formatCard);
    });
    
    showSection(formatSection);
}

function selectFormat(formatCard, format) {
    // Remove previous selection
    document.querySelectorAll('.format-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Select current format
    formatCard.classList.add('selected');
    selectedFormat = format;
    
    // Show trimming and download sections
    showSection(trimmingSection);
    showSection(downloadSection);
}

function updateProgressBar(percentage, text) {
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const progressPercentage = document.getElementById('progress-percentage');
    
    progressFill.style.width = `${percentage}%`;
    progressText.textContent = text;
    progressPercentage.textContent = `${Math.round(percentage)}%`;
}

function showDownloadProgress() {
    downloadBtn.disabled = true;
    downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Downloading...';
    showSection(downloadProgress);
    updateProgressBar(0, 'Preparing download...');
}

function hideDownloadProgress() {
    downloadBtn.disabled = false;
    downloadBtn.innerHTML = '<i class="fas fa-download"></i> Start Download';
    hideSection(downloadProgress);
}

function showDownloadResult(success, message, filename = null) {
    if (success) {
        const resultMessage = document.getElementById('result-message');
        if (filename) {
            resultMessage.textContent = `${message} File: ${filename}`;
        } else {
            resultMessage.textContent = message;
        }
        showSection(downloadResult);
    } else {
        showError(message);
    }
}

// Event Listeners
urlForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const url = videoUrlInput.value.trim();
    if (!url) {
        showError('Please enter a valid YouTube URL');
        return;
    }
    
    // Reset UI state
    hideSection(videoInfoSection);
    hideSection(formatSection);
    hideSection(trimmingSection);
    hideSection(downloadSection);
    hideSection(downloadResult);
    selectedFormat = null;
    currentVideoInfo = null;
    
    try {
        // Show loading state
        fetchBtn.disabled = true;
        fetchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Fetching...';
        loading.classList.remove('hidden');
        
        // Fetch video information
        const videoInfo = await fetchVideoInfo(url);
        
        // Display video info and formats
        displayVideoInfo(videoInfo);
        displayFormats(videoInfo.formats || []);
        
    } catch (error) {
        showError(error.message);
    } finally {
        // Reset button state
        fetchBtn.disabled = false;
        fetchBtn.innerHTML = '<i class="fas fa-search"></i> Fetch Video Info';
        loading.classList.add('hidden');
    }
});

enableTrimmingCheckbox.addEventListener('change', (e) => {
    isTrimmingEnabled = e.target.checked;
    
    if (isTrimmingEnabled) {
        showSection(trimInputs);
    } else {
        hideSection(trimInputs);
    }
});

startTimeInput.addEventListener('input', updateTrimDuration);
endTimeInput.addEventListener('input', updateTrimDuration);

downloadBtn.addEventListener('click', async () => {
    if (!selectedFormat) {
        showError('Please select a video format first');
        return;
    }
    
    if (!validateTrimTimes()) {
        return;
    }
    
    try {
        showDownloadProgress();
        
        // Prepare trim times if enabled
        let trimTimes = null;
        if (isTrimmingEnabled) {
            const startSeconds = parseTimeToSeconds(startTimeInput.value);
            const endSeconds = parseTimeToSeconds(endTimeInput.value);
            trimTimes = [startSeconds, endSeconds];
        }
        
        // Simulate progress updates
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress > 90) progress = 90;
            
            let statusText = 'Downloading...';
            if (progress > 30 && isTrimmingEnabled) {
                statusText = 'Processing video...';
            }
            if (progress > 60 && isTrimmingEnabled) {
                statusText = 'Trimming video...';
            }
            
            updateProgressBar(progress, statusText);
        }, 500);
        
        // Start download
        const result = await downloadVideo(
            videoUrlInput.value.trim(),
            selectedFormat.format_id,
            trimTimes
        );
        
        // Complete progress
        clearInterval(progressInterval);
        updateProgressBar(100, 'Download complete!');
        
        setTimeout(() => {
            hideDownloadProgress();
            showDownloadResult(true, result.message, result.filename);
        }, 1000);
        
    } catch (error) {
        hideDownloadProgress();
        showError(error.message);
    }
});

downloadAnotherBtn.addEventListener('click', () => {
    // Reset form
    videoUrlInput.value = '';
    hideSection(videoInfoSection);
    hideSection(formatSection);
    hideSection(trimmingSection);
    hideSection(downloadSection);
    hideSection(downloadResult);
    
    // Reset trimming
    enableTrimmingCheckbox.checked = false;
    isTrimmingEnabled = false;
    hideSection(trimInputs);
    startTimeInput.value = '';
    endTimeInput.value = '';
    
    // Reset state
    selectedFormat = null;
    currentVideoInfo = null;
    
    // Focus URL input
    videoUrlInput.focus();
});

// Error modal event listeners
closeErrorModal.addEventListener('click', hideError);
errorOkBtn.addEventListener('click', hideError);
errorModal.addEventListener('click', (e) => {
    if (e.target === errorModal) {
        hideError();
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Close modal with Escape key
    if (e.key === 'Escape' && !errorModal.classList.contains('hidden')) {
        hideError();
    }
    
    // Submit form with Enter key when URL input is focused
    if (e.key === 'Enter' && document.activeElement === videoUrlInput) {
        e.preventDefault();
        urlForm.dispatchEvent(new Event('submit'));
    }
});

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    // Focus URL input on page load
    videoUrlInput.focus();
    
    // Set default URL for testing
    const defaultUrl = 'https://www.youtube.com/watch?v=Af2rvOlj9UU';
    videoUrlInput.value = defaultUrl;
    
    console.log('YouTube Downloader App initialized');
});

// Service Worker registration (for PWA capabilities)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js')
            .then((registration) => {
                console.log('SW registered: ', registration);
            })
            .catch((registrationError) => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}