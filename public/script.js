const form = document.getElementById('upload-form');
const statusEl = document.getElementById('status');
const resultEl = document.getElementById('result');
const chatCard = document.getElementById('chat-card');
const chatForm = document.getElementById('chat-form');
const chatStatusEl = document.getElementById('chat-status');
const chatAnswerEl = document.getElementById('chat-answer');

form.addEventListener('submit', async event => {
  event.preventDefault();
  const fileInput = document.getElementById('pdfFile');
  const questionMode = document.getElementById('questionMode').value;
  const questionCount = document.getElementById('questionCount').value;
  const questionStyle = document.getElementById('questionStyle').value;

  if (!fileInput.files.length) {
    statusEl.textContent = 'Please choose a PDF file first.';
    return;
  }

  statusEl.textContent = 'Uploading PDF and generating questions...';
  resultEl.style.display = 'none';
  resultEl.textContent = '';
  chatCard.style.display = 'none';
  chatAnswerEl.style.display = 'none';
  chatAnswerEl.textContent = '';
  chatStatusEl.textContent = '';

  const formData = new FormData();
  formData.append('pdfFile', fileInput.files[0]);
  formData.append('questionMode', questionMode);
  formData.append('questionCount', questionCount);
  formData.append('questionStyle', questionStyle);

  try {
    const response = await fetch('/upload', {
      method: 'POST',
      body: formData,
    });

    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text || 'Upload failed' };
    }

    if (!response.ok) {
      throw new Error(data.error || 'Upload failed');
    }

    statusEl.textContent = 'Questions generated successfully. You can now ask follow-up questions about the document.';
    resultEl.style.display = 'block';
    resultEl.innerHTML = '';

    data.qa.forEach((item, index) => {
      const headerEl = document.createElement('div');
      headerEl.className = 'question';
      headerEl.textContent = `${index + 1}. ${item.question}`;

      const metaText = item.section || item.topic || '';
      if (metaText) {
        const metaEl = document.createElement('div');
        metaEl.className = 'meta';
        metaEl.textContent = metaText;
        resultEl.appendChild(metaEl);
      }

      const answerEl = document.createElement('div');
      answerEl.className = 'answer';
      answerEl.textContent = item.answer;

      resultEl.appendChild(headerEl);
      resultEl.appendChild(answerEl);
    });

    chatCard.style.display = 'block';
  } catch (err) {
    statusEl.textContent = 'Error: ' + err.message;
  }
});

chatForm.addEventListener('submit', async event => {
  event.preventDefault();
  const questionInput = document.getElementById('chatQuestion');
  const question = questionInput.value.trim();

  if (!question) {
    chatStatusEl.textContent = 'Please type a question.';
    return;
  }

  chatStatusEl.textContent = 'Finding answers in the document...';
  chatAnswerEl.style.display = 'none';
  chatAnswerEl.textContent = '';

  try {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ question }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || 'Chat request failed');
    }

    chatStatusEl.textContent = 'Answer generated from the document.';
    chatAnswerEl.style.display = 'block';
    chatAnswerEl.textContent = data.answer;
  } catch (err) {
    chatStatusEl.textContent = 'Error: ' + err.message;
  }
});
