const messages = document.getElementById('messages');
const composer = document.getElementById('composer');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const modal = document.getElementById('modal');
const modalImg = document.getElementById('modal-img');
const modalDownload = document.getElementById('modal-download');
const modalOpenNew = document.getElementById('modal-open-new');

function showModal(imageUrl, downloadUrl) {
  modalImg.src = imageUrl;
  modalDownload.href = downloadUrl || imageUrl;
  modalOpenNew.href = imageUrl;
  modal.classList.add('show');
  modal.setAttribute('aria-hidden', 'false');
}

function hideModal() {
  modal.classList.remove('show');
  modal.setAttribute('aria-hidden', 'true');
  modalImg.src = '';
}

function addBubble(text, role) {
  const div = document.createElement('div');
  div.className = `bubble ${role}`;
  div.textContent = text;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return div;
}

function addAssistantCard(parent, data) {
  if (!data || !data.image_url) return;

  const card = document.createElement('div');
  card.className = 'card';

  const previewLink = document.createElement('a');
  previewLink.href = data.image_url;
  previewLink.addEventListener('click', (e) => {
    e.preventDefault();
    showModal(data.image_url, data.download_url);
  });

  const img = document.createElement('img');
  img.className = 'preview';
  img.alt = 'Circuit diagram preview';
  img.src = data.image_url;
  previewLink.appendChild(img);

  const actions = document.createElement('div');
  actions.className = 'card-actions';

  const open = document.createElement('button');
  open.type = 'button';
  open.className = 'btn btn-primary';
  open.textContent = 'View Fullscreen';
  open.addEventListener('click', () => showModal(data.image_url, data.download_url));

  const download = document.createElement('a');
  download.href = data.download_url || data.image_url;
  download.setAttribute('download', 'circuit.svg');
  download.className = 'btn';
  download.textContent = 'Download SVG';

  actions.appendChild(open);
  actions.appendChild(download);

  card.appendChild(previewLink);
  card.appendChild(actions);

  const details = document.createElement('div');
  details.className = 'circuit-details';
  
  let detailsHtml = '';
  
  if (data.inputs && Object.keys(data.inputs).length > 0) {
    detailsHtml += `<div class="params-section">
      <div class="params-title">Inputs</div>
      <div class="params-grid">`;
    for (const [key, val] of Object.entries(data.inputs)) {
      detailsHtml += `<div class="param-row">
        <span class="param-key">${key}</span>
        <span class="param-val">${Number(val).toLocaleString(undefined, { maximumFractionDigits: 4 })}</span>
      </div>`;
    }
    detailsHtml += `</div></div>`;
  }
  
  if (data.outputs && Object.keys(data.outputs).length > 0) {
    detailsHtml += `<div class="params-section">
      <div class="params-title">Outputs</div>
      <div class="params-grid">`;
    for (const [key, val] of Object.entries(data.outputs)) {
      detailsHtml += `<div class="param-row">
        <span class="param-key">${key}</span>
        <span class="param-val highlight">${Number(val).toLocaleString(undefined, { maximumFractionDigits: 4 })}</span>
      </div>`;
    }
    detailsHtml += `</div></div>`;
  }
  
  details.innerHTML = detailsHtml;

  if (detailsHtml) {
    card.appendChild(details);
  }

  parent.appendChild(card);
  messages.scrollTop = messages.scrollHeight;
}

async function sendMessage(text) {
  sendBtn.disabled = true;
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });

    const data = await res.json();
    if (!res.ok) {
      const errText = data?.detail || 'Request failed';
      addBubble(errText, 'assistant');
      return;
    }

    const bubble = addBubble(data.reply || '(no reply)', 'assistant');
    addAssistantCard(bubble, data);
  } catch (e) {
    addBubble(String(e), 'assistant');
  } finally {
    sendBtn.disabled = false;
  }
}

composer.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  addBubble(text, 'user');
  input.value = '';
  await sendMessage(text);
});

modal.addEventListener('click', (e) => {
  if (e.target.dataset.close) {
    hideModal();
  }
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && modal.classList.contains('show')) {
    hideModal();
  }
});

addBubble('Tell me a circuit and any parameters you know. Example: priority encoder D3=0 D2=0 D1=0 D0=1', 'assistant');
