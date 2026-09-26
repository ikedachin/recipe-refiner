import { postJSON, showError } from './app.js';
import { renderConfirmation, renderResult } from './render.js';

const initial = JSON.parse(document.querySelector('#recipe-bootstrap').textContent);
const form = document.querySelector('#refine-form');
const original = document.querySelector('#original-text');
const request = document.querySelector('#request-text');
const submit = document.querySelector('#refine-button');
const confirmButton = document.querySelector('#confirm-button');
const editButton = document.querySelector('#edit-button');
const confirmationPanel = document.querySelector('#confirmation');
let recipeId = initial.recipe_id || null;
let revisionId = initial.revision_id || null;
let confirmationToken = null;
let busy = false;

function updateCounts() {
  document.querySelector('#original-count').textContent = original.value.length.toLocaleString();
  document.querySelector('#request-count').textContent = request.value.length.toLocaleString();
}
function discardConfirmation() {
  confirmationToken = null;
  confirmationPanel.hidden = true;
}
function setBusy(value) {
  busy = value;
  form.setAttribute('aria-busy', String(value));
  [submit, confirmButton, editButton, request, original, document.querySelector('#sample-button')].forEach((el) => {
    if (el) el.disabled = value;
  });
  document.querySelector('#loading').hidden = !value;
  submit.querySelector('span').textContent = value ? 'リファイン中…' : 'リファイン';
}
function showResult(result, text, label) {
  const favorite = document.querySelector(`[data-favorite-id="${recipeId}"]`)?.getAttribute('aria-pressed') === 'true';
  renderResult(result, { recipeId, revisionId, llm: label, resultText: text, favorite });
}
async function generate(confirmed = false) {
  if (busy) return;
  showError('');
  if (!confirmed && (!original.value.trim() || !request.value.trim())) {
    showError('元レシピと変更したい内容を入力してください。');
    return;
  }
  const token = confirmationToken;
  if (confirmed && !token) return;
  setBusy(true);
  try {
    const url = confirmed ? '/api/refine/confirm/' : revisionId
      ? `/api/refine/${revisionId}/` : recipeId ? `/api/recipes/${recipeId}/refine/` : '/api/refine/';
    const data = confirmed ? { confirmation_token: token } : {
      original_text: recipeId ? '' : original.value,
      request_text: request.value,
    };
    const result = await postJSON(url, data);
    if (result.status === 'needs_confirmation') {
      confirmationToken = result.confirmation_token;
      renderConfirmation(result.confirmation);
      confirmationPanel.hidden = false;
      confirmationPanel.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      discardConfirmation();
      document.querySelectorAll('.history-strip, .saved-generation-context').forEach((el) => { el.hidden = true; });
      recipeId = result.recipe_id;
      revisionId = result.revision_id;
      showResult(result, result.result_text, result.llm);
      original.value = result.result_text;
      original.readOnly = true;
      request.value = '';
      request.placeholder = 'さらに変えたいことがあれば、ここに入力してください。\n直前のリファイン結果をもとに、新しい履歴を作ります。';
      document.querySelector('#source-label').textContent = 'ベースレシピ';
      document.querySelector('#source-description').textContent = '直前の結果をもとに、さらにリファインできます。';
      document.querySelector('#source-hint').textContent = '生成結果は履歴に保存済みです';
      const sample = document.querySelector('#sample-button');
      if (sample) sample.hidden = true;
      // Reloading now opens the persisted recipe rather than losing the result.
      window.history.replaceState(null, '', result.history_url);
      updateCounts();
      document.querySelector('#result-section').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  } catch (error) { showError(error.message); }
  finally { setBusy(false); }
}
form.addEventListener('submit', (event) => { event.preventDefault(); generate(); });
confirmButton.addEventListener('click', () => generate(true));
editButton.addEventListener('click', () => { discardConfirmation(); request.focus(); });
[original, request].forEach((input) => input.addEventListener('input', () => { updateCounts(); discardConfirmation(); }));
document.querySelector('#sample-button')?.addEventListener('click', () => {
  if (original.value.trim() || request.value.trim()) {
    showError('入力済みの内容があります。サンプルを使うには入力欄を空にしてください。');
    return;
  }
  original.value = 'カレー 4人前\n\n材料\n玉ねぎ 2個\nにんじん 1本\nじゃがいも 2個\n牛肉 300g\nカレールー 4皿分\n水 600ml\n\n作り方\n1. 野菜を切る\n2. 牛肉を炒める\n3. 野菜を加える\n4. 水を加えて煮込む\n5. カレールーを加える';
  request.value = '玉ねぎがありません。\n牛肉を豚肉に変更してください。\n2人前にして、辛さを少し抑えたいです。';
  updateCounts();
  request.focus();
});
if (initial.result) showResult(initial.result, initial.result_text, initial.llm);
updateCounts();
