const fileInput = document.querySelector('#file-input');
const dropZone = document.querySelector('#drop-zone');
const fileCard = document.querySelector('#file-card');
const fileName = document.querySelector('#file-name');
const fileSize = document.querySelector('#file-size');
const fileBadge = document.querySelector('#file-badge');
const removeFile = document.querySelector('#remove-file');
const sourceFormat = document.querySelector('#source-format');
const targetFormat = document.querySelector('#target-format');
const swapButton = document.querySelector('#swap-button');
const convertButton = document.querySelector('#convert-button');
const mainFile = document.querySelector('#main-file');
const message = document.querySelector('#message');
const engineState = document.querySelector('#engine-state');

let selectedFile = null;
let engineReady = false;

const formatByExtension = {
  docx: 'docx',
  md: 'markdown',
  markdown: 'markdown',
  tex: 'latex',
  latex: 'latex',
};

function extensionOf(name) {
  const pieces = name.toLowerCase().split('.');
  return pieces.length > 1 ? pieces.pop() : '';
}

function humanSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function showMessage(text, isError = false) {
  message.textContent = text;
  message.classList.toggle('error', isError);
  message.hidden = !text;
}

function updateButton() {
  const sameFormat = sourceFormat.value !== 'auto' && sourceFormat.value === targetFormat.value;
  convertButton.disabled = !selectedFile || !engineReady || sameFormat;
  if (sameFormat) showMessage('输入与输出格式相同，请选择另一个输出格式。', true);
  else if (message.textContent.includes('输入与输出格式相同')) showMessage('');
}

function chooseDifferentTarget(source) {
  if (source === targetFormat.value) {
    targetFormat.value = source === 'docx' ? 'markdown' : 'docx';
  }
}

function setFile(file) {
  if (!file) return;
  const extension = extensionOf(file.name);
  const allowed = ['docx', 'md', 'markdown', 'tex', 'latex', 'zip'];
  if (!allowed.includes(extension)) {
    showMessage('请选择 DOCX、MD、TEX 或 ZIP 文件。', true);
    return;
  }
  if (file.size > 50 * 1024 * 1024) {
    showMessage('文件超过 50 MB 上传限制。', true);
    return;
  }
  selectedFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = humanSize(file.size);
  fileBadge.textContent = extension.toUpperCase();
  dropZone.hidden = true;
  fileCard.hidden = false;
  showMessage('');
  if (formatByExtension[extension]) {
    sourceFormat.value = formatByExtension[extension];
    chooseDifferentTarget(sourceFormat.value);
  } else {
    sourceFormat.value = 'auto';
  }
  updateButton();
}

function clearFile() {
  selectedFile = null;
  fileInput.value = '';
  dropZone.hidden = false;
  fileCard.hidden = true;
  showMessage('');
  updateButton();
}

dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => setFile(fileInput.files[0]));
removeFile.addEventListener('click', clearFile);

['dragenter', 'dragover'].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add('dragging');
  });
});

['dragleave', 'drop'].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove('dragging');
  });
});

dropZone.addEventListener('drop', (event) => setFile(event.dataTransfer.files[0]));

swapButton.addEventListener('click', () => {
  if (sourceFormat.value === 'auto') {
    sourceFormat.value = targetFormat.value;
    targetFormat.value = sourceFormat.value === 'docx' ? 'markdown' : 'docx';
  } else {
    const previousSource = sourceFormat.value;
    sourceFormat.value = targetFormat.value;
    targetFormat.value = previousSource;
  }
  updateButton();
});

sourceFormat.addEventListener('change', () => {
  chooseDifferentTarget(sourceFormat.value);
  updateButton();
});
targetFormat.addEventListener('change', updateButton);

function filenameFromDisposition(header) {
  if (!header) return null;
  const encoded = header.match(/filename\*=utf-8''([^;]+)/i);
  if (encoded) return decodeURIComponent(encoded[1]);
  const plain = header.match(/filename="?([^";]+)"?/i);
  return plain ? plain[1] : null;
}

convertButton.addEventListener('click', async () => {
  if (!selectedFile) return;
  convertButton.disabled = true;
  convertButton.classList.add('loading');
  convertButton.querySelector('.button-label').textContent = '正在转换…';
  showMessage('正在解析文档结构、公式与资源，请稍候。');

  const form = new FormData();
  form.append('file', selectedFile);
  form.append('source_format', sourceFormat.value);
  form.append('target_format', targetFormat.value);
  if (mainFile.value.trim()) form.append('main_file', mainFile.value.trim());

  try {
    const response = await fetch('/api/convert', { method: 'POST', body: form });
    if (!response.ok) {
      let detail = `转换失败（HTTP ${response.status}）`;
      try {
        const payload = await response.json();
        detail = payload.detail || detail;
      } catch (_) { /* The server may return plain text. */ }
      throw new Error(detail);
    }
    const blob = await response.blob();
    const downloadName = filenameFromDisposition(response.headers.get('content-disposition')) || `converted.${targetFormat.value}`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = downloadName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10_000);

    let successText = `转换完成，已下载 ${downloadName}`;
    const warningHeader = response.headers.get('x-document-bridge-warnings');
    if (warningHeader) {
      try {
        const warnings = JSON.parse(warningHeader);
        if (warnings.length) successText += `。提示：${warnings.join('；')}`;
      } catch (_) { /* Ignore malformed optional warning headers. */ }
    }
    showMessage(successText);
  } catch (error) {
    showMessage(error.message || '转换失败，请检查文档后重试。', true);
  } finally {
    convertButton.classList.remove('loading');
    convertButton.querySelector('.button-label').textContent = '开始转换';
    updateButton();
  }
});

async function checkEngine() {
  try {
    const response = await fetch('/api/status');
    const status = await response.json();
    engineReady = Boolean(status.ready);
    engineState.classList.toggle('ready', engineReady);
    engineState.classList.toggle('error', !engineReady);
    engineState.querySelector('span:last-child').textContent = engineReady ? `${status.engine} · 就绪` : status.engine;
    if (!engineReady) showMessage(status.engine, true);
  } catch (_) {
    engineReady = false;
    engineState.classList.add('error');
    engineState.querySelector('span:last-child').textContent = '转换引擎不可用';
  }
  updateButton();
}

checkEngine();

