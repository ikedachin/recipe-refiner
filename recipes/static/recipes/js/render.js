// Every user/LLM string enters the DOM through textContent, never HTML parsing.
export function element(tag, text = '', className = '') {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function listSection(title, items, className = '') {
  if (!items?.length) return null;
  const section = element('section', '', className);
  section.append(element('h3', title));
  const list = element('ul');
  items.forEach((item) => list.append(element('li', item)));
  section.append(list);
  return section;
}

export function renderConfirmation(confirmation) {
  const target = document.querySelector('#confirmation-content');
  target.replaceChildren(element('p', confirmation.message));
  [
    ['問題となる理由', confirmation.concerns],
    ['必要になる大きな変更', confirmation.required_changes],
    ['代替案', confirmation.alternatives],
  ].forEach(([title, items]) => {
    const section = listSection(title, items);
    if (section) target.append(section);
  });
}

export function renderResult(data, { recipeId, revisionId, llm, resultText, favorite = false }) {
  const target = document.querySelector('#result');
  const recipe = data.recipe;
  target.replaceChildren();
  target.className = 'result-card';
  const header = element('header', '', 'result-header');
  const titleBlock = element('div');
  titleBlock.append(element('div', 'REFINED FOR YOU', 'eyebrow'), element('h2', recipe.title));
  const meta = element('div', '', 'recipe-meta');
  meta.append(element('span', recipe.servings));
  if (recipe.estimated_time_minutes) meta.append(element('span', `約 ${recipe.estimated_time_minutes} 分`));
  titleBlock.append(meta);
  const actions = element('div', '', 'result-actions');
  const favoriteButton = element('button', favorite ? '★' : '☆', 'favorite-button');
  favoriteButton.type = 'button';
  favoriteButton.dataset.favoriteId = recipeId;
  favoriteButton.setAttribute('aria-pressed', String(favorite));
  favoriteButton.setAttribute('aria-label', 'お気に入りを切り替え');
  const copy = element('button', 'レシピをコピー', 'secondary-button');
  copy.type = 'button';
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(resultText);
      copy.textContent = 'コピーしました';
    } catch { copy.textContent = 'コピーできませんでした'; }
    setTimeout(() => { copy.textContent = 'レシピをコピー'; }, 2500);
  });
  actions.append(favoriteButton, copy);
  header.append(titleBlock, actions);
  const body = element('div', '', 'result-body');
  const ingredients = element('section');
  ingredients.append(element('h3', '材料'));
  const table = element('table', '', 'ingredients');
  table.setAttribute('aria-label', '材料と分量');
  const tbody = element('tbody');
  recipe.ingredients.forEach((item) => {
    const row = element('tr');
    const name = element('td', item.name);
    if (item.note) name.append(element('span', item.note, 'ingredient-note'));
    row.append(name, element('td', `${item.amount}${item.unit}`));
    tbody.append(row);
  });
  table.append(tbody);
  ingredients.append(table);
  const instructions = element('section');
  instructions.append(element('h3', '作り方'));
  const steps = element('ol', '', 'steps');
  recipe.steps.forEach((step) => steps.append(element('li', step.instruction)));
  instructions.append(steps);
  body.append(ingredients, instructions);
  const changes = element('section', '', 'changes-section');
  changes.append(element('h3', '今回変更した内容'));
  const grid = element('div', '', 'changes-grid');
  data.changes.forEach((change) => {
    const card = element('div', '', 'change-item');
    const line = element('p');
    line.append(element('span', change.before || '追加', 'change-before'), element('span', '→', 'change-arrow'), element('span', change.after || '削除', 'change-after'));
    card.append(line, element('p', `理由：${change.reason}`, 'change-reason'));
    grid.append(card);
  });
  if (!data.changes.length) grid.append(element('p', '変更点はありません。', 'muted'));
  changes.append(grid);
  target.append(header, body, changes);
  [
    ['補足', recipe.notes], ['推測・前提としたこと', data.assumptions], ['確認しておきたいこと', data.warnings],
  ].forEach(([title, items]) => {
    const section = listSection(title, items, 'notes-section');
    if (section) target.append(section);
  });
  const bottom = element('div', '', 'result-bottom');
  bottom.append(element('span', `履歴に保存済み · ${llm}`));
  const history = element('a', 'このレシピの履歴を見る →');
  history.href = `/recipes/${recipeId}/?revision=${revisionId}`;
  bottom.append(history);
  target.append(bottom);
  target.hidden = false;
  document.querySelector('#result-placeholder').hidden = true;
  document.querySelector('#result-status').textContent = '材料も、工程も、バランスよく。';
}
