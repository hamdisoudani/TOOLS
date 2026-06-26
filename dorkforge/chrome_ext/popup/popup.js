// DorkForge Harvester - Popup logic

const $ = (id) => document.getElementById(id);

async function refreshState() {
  chrome.runtime.sendMessage({ type: 'GET_STATE' }, (resp) => {
    if (!resp || !resp.ok) return;
    const s = resp.state;
    $('urlCount').textContent = s.total_extracted || 0;
    $('jobsDone').textContent = s.total_dorks_processed || 0;
    let status = 'idle';
    if (s.running && !s.paused) status = 'running';
    else if (s.paused) status = 'paused';
    $('runningStatus').textContent = status;
    const sb = $('statusBox');
    sb.className = 'status ' + (s.running && !s.paused ? 'running' : s.paused ? 'paused' : '');
    let txt = '';
    if (s.current_dork) txt = `Current: ${s.current_dork.slice(0, 80)}`;
    else if (s.session_start) txt = `Idle. Session: ${new Date(s.session_start).toLocaleTimeString()}`;
    else txt = 'Ready.';
    if (s.last_error) txt += `\nLast error: ${s.last_error}`;
    sb.textContent = txt;
  });
}

async function refreshQueueCount() {
  chrome.runtime.sendMessage({ type: 'GET_QUEUE' }, (resp) => {
    if (resp && resp.ok) {
      $('urlCount').textContent = resp.queue.length;
    }
  });
}

$('startBtn').onclick = () => {
  const raw = $('dorks').value.trim();
  if (!raw) {
    alert('Paste at least one dork.');
    return;
  }
  const dorks = raw.split('\n').map((l) => l.trim()).filter(Boolean);
  const engine = $('engine').value;
  chrome.runtime.sendMessage({ type: 'ENQUEUE_DORKS', dorks, engine }, (resp) => {
    if (resp && resp.ok) {
      $('statusBox').textContent = `Queued ${resp.jobs_queued} jobs. Watch background tabs pop up.`;
    }
  });
};

$('pauseBtn').onclick = () => chrome.runtime.sendMessage({ type: 'PAUSE_HARVEST' });
$('resumeBtn').onclick = () => chrome.runtime.sendMessage({ type: 'RESUME_HARVEST' });
$('clearBtn').onclick = () => {
  if (confirm('Clear all harvested URLs?')) {
    chrome.runtime.sendMessage({ type: 'CLEAR_QUEUE' }, refreshQueueCount);
  }
};

$('exportTxt').onclick = () => triggerExport('sqldumper');
$('exportCsv').onclick = () => triggerExport('csv');
$('exportJson').onclick = () => triggerExport('json');

function triggerExport(format) {
  chrome.runtime.sendMessage({ type: 'EXPORT_URLS', payload: { format } }, (resp) => {
    if (resp && resp.ok) {
      $('statusBox').textContent = `Exported ${resp.count} URLs → ${resp.filename}`;
    }
  });
}

// Refresh on popup open + every 2s
refreshState();
refreshQueueCount();
setInterval(() => { refreshState(); refreshQueueCount(); }, 2000);

// Preset dorks button
document.addEventListener('DOMContentLoaded', () => {
  // Add preset dorks dropdown later
});