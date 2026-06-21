const PAGE_WS = 'ws://localhost:9222/devtools/page/77B699B856C4BBF8D854C8C449E73AEB';

function cdpClient(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let id = 1; const pending = new Map();
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
    ws.addEventListener('message', (e) => {
      const m = JSON.parse(e.data);
      if (m.id && pending.has(m.id)) {
        const { res, rej } = pending.get(m.id);
        pending.delete(m.id);
        if (m.error) rej(new Error(m.error.message));
        else res(m.result);
      }
    });
    ws.addEventListener('error', e => reject(e));
  });
}

async function evaluate(cdp, expr) {
  const r = await cdp.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result.value;
}

// Build the probe expression with unicode escapes so no Chinese chars in JS source
function buildProbeExpr() {
  // CJK range: 一-鿿
  return `(function(){
    var all = document.querySelectorAll('*');
    var found = [];
    var cjk = /[\\u4e00-\\u9fff]/;
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (el.children.length === 0) {
        var t = el.textContent.trim();
        if (t.length >= 2 && t.length <= 6 && cjk.test(t)) {
          found.push(el.className + ' :: ' + t);
        }
      }
    }
    return found.slice(0, 40).join('\\n');
  })()`;
}

async function main() {
  const cdp = await cdpClient(PAGE_WS);
  await new Promise(r => setTimeout(r, 800));

  const result = await evaluate(cdp, buildProbeExpr());
  console.log(result);
  cdp.close();
}

main().catch(e => { console.error(e.message); process.exit(1); });
