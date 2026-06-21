import { writeFileSync } from 'fs';

const PAGE_WS = 'ws://localhost:9222/devtools/page/77B699B856C4BBF8D854C8C449E73AEB';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function cdpClient(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let id = 1;
    const pending = new Map();
    ws.addEventListener('open', () => resolve({
      send(method, params = {}) {
        return new Promise((res, rej) => {
          const msgId = id++;
          pending.set(msgId, { res, rej });
          ws.send(JSON.stringify({ id: msgId, method, params }));
        });
      },
      close() { ws.close(); }
    }));
    ws.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && pending.has(msg.id)) {
        const { res, rej } = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) rej(new Error(msg.error.message));
        else res(msg.result);
      }
    });
    ws.addEventListener('error', (e) => reject(e));
  });
}

async function evaluate(cdp, expr) {
  const r = await cdp.send('Runtime.evaluate', {
    expression: expr,
    returnByValue: true,
    awaitPromise: true,
  });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
}

// Extract raw page text — parsing happens in Node.js to avoid Chinese chars in CDP JS
async function extractPageText(cdp) {
  return evaluate(cdp, `document.body.innerText`);
}

async function extractCharName(cdp) {
  return evaluate(cdp, `(function() {
    var els = document.querySelectorAll('*');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      var cls = String(el.className || '');
      if (cls.indexOf('text-14') !== -1 && cls.indexOf('lh-20') !== -1 && cls.indexOf('absolute') === -1) {
        var t = el.textContent.trim();
        if (t.length >= 2 && t.length <= 6) return t;
      }
    }
    return '';
  })()`);
}

// Parse drive disc main stats and substats from page text
function parseCharData(name, text) {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);

  // Find 驱动盘推荐 section
  let discStart = -1, substatStart = -1, attrStart = -1;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i] === '驱动盘推荐' && discStart === -1) discStart = i;
    if (lines[i] === '副属性推荐' && substatStart === -1) substatStart = i;
    if (lines[i] === '属性推荐' && attrStart === -1) attrStart = i;
  }

  // Parse slots 4, 5, 6 main stats
  const mainStats = { 4: [], 5: [], 6: [] };
  if (discStart !== -1) {
    const end = substatStart !== -1 ? substatStart : discStart + 30;
    const section = lines.slice(discStart, end);
    let currentSlot = null;
    let afterMainAttr = false;
    for (const line of section) {
      if (/^[456]$/.test(line)) {
        currentSlot = parseInt(line);
        afterMainAttr = false;
      } else if (line === '主属性') {
        afterMainAttr = true;
      } else if (afterMainAttr && currentSlot && [4,5,6].includes(currentSlot)) {
        // Stop at next section marker
        if (/^[123456]$/.test(line) || line === '副属性推荐') break;
        mainStats[currentSlot].push(line);
      }
    }
  }

  // Parse priority substats
  const substats = [];
  if (substatStart !== -1) {
    const end = attrStart !== -1 ? attrStart : substatStart + 20;
    const section = lines.slice(substatStart + 1, end);
    for (const line of section) {
      if (line === '属性推荐' || line === '音擎推荐') break;
      if (line.length > 0 && line.length < 20) substats.push(line);
    }
  }

  // Parse supplementary notes (补充建议 section)
  let notes = '';
  const notesIdx = lines.findIndex(l => l === '补充建议');
  if (notesIdx !== -1) {
    const noteLines = [];
    for (let i = notesIdx + 1; i < Math.min(notesIdx + 20, lines.length); i++) {
      if (lines[i].startsWith('http') || lines[i].length > 300) break;
      noteLines.push(lines[i]);
    }
    notes = noteLines.join(' ').slice(0, 400);
  }

  return { name, mainStats, substats, notes };
}

async function main() {
  const cdp = await cdpClient(PAGE_WS);
  await sleep(1500);

  const agentCount = await evaluate(cdp, `document.querySelectorAll('.agent-item').length`);
  console.log(`Found ${agentCount} agent items`);

  const results = [];

  for (let i = 0; i < agentCount; i++) {
    // Click the agent item
    await evaluate(cdp, `(function(){ var items = document.querySelectorAll('.agent-item'); if(items[${i}]) items[${i}].click(); })()`);
    await sleep(2000);

    const name = await extractCharName(cdp);
    const text = await extractPageText(cdp);
    const data = parseCharData(name, text);

    console.log(`[${i+1}/${agentCount}] ${data.name}`);
    console.log(`  slot4: ${JSON.stringify(data.mainStats[4])}`);
    console.log(`  slot5: ${JSON.stringify(data.mainStats[5])}`);
    console.log(`  slot6: ${JSON.stringify(data.mainStats[6])}`);
    console.log(`  subs:  ${JSON.stringify(data.substats)}`);

    results.push(data);
  }

  writeFileSync('D:/Desktop/zzz-disc-scorer/scripts/scraped_chars.json', JSON.stringify(results, null, 2), 'utf-8');
  console.log('\nSaved to scripts/scraped_chars.json');
  cdp.close();
}

main().catch(e => { console.error(e.message || e); process.exit(1); });
