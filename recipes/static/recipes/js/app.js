export function showError(message) {
  const box = document.querySelector('#global-error');
  box.textContent = message;
  box.hidden = !message;
  if (message) box.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

export async function postJSON(url, data = {}) {
  const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify(data),
    });
  } catch {
    throw new Error('通信に失敗しました。サーバーの起動状態を確認してください。');
  }
  let result;
  try { result = await response.json(); }
  catch { throw new Error('サーバーの応答を読み取れませんでした。再読み込みしてお試しください。'); }
  if (!response.ok) throw new Error(result.error || '処理を完了できませんでした。');
  return result;
}

// Delegation also handles favorite buttons created in generation results.
document.addEventListener('click', async (event) => {
  const button = event.target.closest('[data-favorite-id]');
  if (!button || button.disabled) return;
  button.disabled = true;
  try {
    const result = await postJSON(`/api/recipes/${button.dataset.favoriteId}/favorite/`);
    document.querySelectorAll(`[data-favorite-id="${button.dataset.favoriteId}"]`).forEach((item) => {
      item.setAttribute('aria-pressed', String(result.is_favorite));
      item.textContent = result.is_favorite ? '★' : '☆';
    });
    showError('');
  } catch (error) { showError(error.message); }
  finally { button.disabled = false; }
});
