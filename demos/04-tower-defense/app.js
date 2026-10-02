'use strict';
const { Game, PATH, position, onRoad } = TowerEngine;
let game = new Game();
let pointer = null;
const canvas = $('#game');
const ctx = canvas.getContext('2d');
function point(event) {
  const bounds = canvas.getBoundingClientRect();
  return [(event.clientX - bounds.left) * 900 / bounds.width, (event.clientY - bounds.top) * 500 / bounds.height];
}
canvas.addEventListener('pointermove', event => { pointer = point(event); });
canvas.addEventListener('pointerleave', () => { pointer = null; });
canvas.addEventListener('click', event => {
  const [x, y] = point(event);
  $('#status').textContent = game.build(x, y, $('#tower').value);
  render();
});
$('#next').addEventListener('click', () => {
  if (game.next()) $('#status').textContent = `第 ${game.wave} 波进行中。`;
});
$('#pause').addEventListener('click', () => {
  game.paused = !game.paused;
  $('#pause').textContent = game.paused ? '继续' : '暂停';
});
$('#reset').addEventListener('click', () => {
  game = new Game();
  $('#pause').textContent = '暂停';
  $('#status').textContent = '先点击空地建塔，再开始第一波。';
  render();
});
function polygon(x, y, radius, sides, fill) {
  ctx.beginPath();
  for (let index = 0; index < sides; index++) {
    const angle = index * Math.PI * 2 / sides + Math.PI / 8;
    const px = x + Math.cos(angle) * radius, py = y + Math.sin(angle) * radius;
    if (index) ctx.lineTo(px, py); else ctx.moveTo(px, py);
  }
  ctx.closePath(); ctx.fillStyle = fill; ctx.fill();
}
function render() {
  ctx.fillStyle = '#202c3b'; ctx.fillRect(0, 0, 900, 500);
  ctx.fillStyle = '#344051';
  for (let x = 20; x < 900; x += 40) for (let y = 20; y < 500; y += 40) ctx.fillRect(x, y, 1, 1);
  ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  ctx.beginPath(); PATH.forEach(([x, y], index) => index ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.strokeStyle = '#53616d'; ctx.lineWidth = 54; ctx.stroke();
  ctx.strokeStyle = '#45515e'; ctx.lineWidth = 46; ctx.stroke();
  ctx.strokeStyle = '#73808a'; ctx.lineWidth = 1; ctx.setLineDash([6, 16]); ctx.stroke(); ctx.setLineDash([]);
  ctx.fillStyle = '#344c60'; ctx.fillRect(846, 365, 49, 68);
  ctx.strokeStyle = '#83a8c1'; ctx.lineWidth = 2; ctx.strokeRect(846, 365, 49, 68);
  ctx.fillStyle = '#d7e4ed'; ctx.font = '12px sans-serif'; ctx.fillText('基地', 857, 404);
  ctx.fillStyle = '#acbbc9'; ctx.fillText('入口', 14, 79);
  for (const tower of game.towers) {
    const frost = tower.type === 'frost';
    polygon(tower.x, tower.y + 3, 21, 8, '#17212e');
    polygon(tower.x, tower.y, 19, 8, '#546270');
    polygon(tower.x, tower.y, 14, 8, frost ? '#80bad2' : '#dec89c');
    ctx.fillStyle = '#334252'; ctx.fillRect(tower.x - 4, tower.y - 22, 8, 23);
    ctx.fillStyle = frost ? '#b9e0ed' : '#eee3c7'; ctx.fillRect(tower.x - 3, tower.y - 25, 6, 8);
  }
  for (const enemy of game.enemies) {
    const [x, y] = position(enemy.d);
    polygon(x, y + 2, 12, 6, '#182330');
    polygon(x, y, 10, 6, enemy.slow > 0 ? '#94c4d8' : '#c98569');
    ctx.fillStyle = '#273442'; ctx.fillRect(x - 15, y - 20, 30, 4);
    ctx.fillStyle = '#e3ba91'; ctx.fillRect(x - 15, y - 20, 30 * Math.max(0, enemy.hp / enemy.max), 4);
  }
  for (const effect of game.effects) {
    ctx.strokeStyle = effect.type === 'frost' ? '#99d4f0' : '#e9d3a6'; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(...effect.a); ctx.lineTo(...effect.b); ctx.stroke();
  }
  if (pointer && !['won', 'lost'].includes(game.state)) {
    const [x, y] = pointer, frost = $('#tower').value === 'frost';
    const valid = game.gold >= (frost ? 70 : 50) && x >= 22 && x <= 878 && y >= 22 && y <= 478
      && !onRoad(x, y) && !game.towers.some(t => Math.hypot(t.x - x, t.y - y) < 43);
    ctx.beginPath(); ctx.arc(x, y, frost ? 135 : 155, 0, Math.PI * 2);
    ctx.fillStyle = valid ? '#91bcd610' : '#dd8c8210'; ctx.fill();
    ctx.strokeStyle = valid ? '#8daecb80' : '#ce857980'; ctx.lineWidth = 1; ctx.stroke();
    polygon(x, y, 13, 8, valid ? '#a8c4d7' : '#c08b81');
  }
  if (game.paused || ['won', 'lost'].includes(game.state)) {
    ctx.fillStyle = '#142030d9'; ctx.fillRect(0, 0, 900, 500);
    ctx.textAlign = 'center'; ctx.fillStyle = '#edf2f6'; ctx.font = '600 34px sans-serif';
    ctx.fillText(game.state === 'won' ? '防守成功' : game.state === 'lost' ? '基地失守' : '已暂停', 450, 237);
    ctx.fillStyle = '#acbbca'; ctx.font = '15px sans-serif';
    ctx.fillText(game.state === 'won' ? '五波敌人已全部结束' : game.state === 'lost' ? '点击重开，再试一次' : '点击继续恢复游戏', 450, 275);
    ctx.textAlign = 'left';
  }
  $('#life').textContent = game.life;
  $('#gold').textContent = game.gold;
  $('#wave').textContent = `${game.wave} / 5`;
  $('#kills').textContent = game.kills;
  $('#next').disabled = game.state !== 'ready' || game.paused;
  $('#next').textContent = ['won', 'lost'].includes(game.state) ? '本局结束' : game.state === 'running' ? `第 ${game.wave} 波进行中` : game.wave === 0 ? '开始第一波' : game.wave === 5 ? '本局结束' : `开始第 ${game.wave + 1} 波`;
  $('#pause').disabled = ['won', 'lost'].includes(game.state);
  if (game.state === 'won') $('#status').textContent = '防守成功。可以点击重开开始新的一局。';
  if (game.state === 'lost') $('#status').textContent = '基地耐久归零。可以点击重开调整布局。';
}
let last = performance.now(), accumulated = 0;
function frame(now) {
  accumulated += Math.min((now - last) / 1000, .15); last = now;
  while (accumulated >= 1 / 60) { game.step(1 / 60); accumulated -= 1 / 60; }
  render(); requestAnimationFrame(frame);
}
render();
requestAnimationFrame(frame);
