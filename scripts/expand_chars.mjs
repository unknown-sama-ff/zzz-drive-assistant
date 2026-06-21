import { readFileSync, writeFileSync } from 'fs';

const scraped = JSON.parse(readFileSync('D:/Desktop/zzz-disc-scorer/scripts/scraped_chars.json', 'utf-8'));
const chars   = JSON.parse(readFileSync('D:/Desktop/zzz-disc-scorer/data/characters.json', 'utf-8'));

// ── Normalizers (same as update_chars.mjs) ───────────────────────────────────
const NO_PERCENT = ['异常精通', '异常掌控', '冲击力', '穿透值', '穿透率'];

function normMain(s) {
  if (NO_PERCENT.includes(s)) return s;
  if (s === '穿透率') return '穿透率%';
  if (s.endsWith('%')) return s;
  return s + '%';
}

function normSub(s) {
  if (s === '攻击力百分比') return '攻击力%';
  if (s === '生命值百分比') return '生命值%';
  if (s === '防御力百分比') return '防御力%';
  if (s === '攻击力') return '攻击力数值';
  if (s === '生命值') return '生命值数值';
  if (s === '防御力') return '防御力数值';
  if (NO_PERCENT.includes(s)) return s;
  if (s.endsWith('%')) return s;
  return s + '%';
}

// ── Element inference from slot-5 main stats ─────────────────────────────────
const ELEMENT_MAP = {
  '冰属性伤害加成': '冰',
  '火属性伤害加成': '火',
  '电属性伤害加成': '电',
  '以太伤害加成':   '以太',
  '物理伤害加成':   '物理',
  '风属性伤害加成': '风',
};

function inferElement(slot5Stats) {
  for (const s of (slot5Stats || [])) {
    if (ELEMENT_MAP[s]) return ELEMENT_MAP[s];
  }
  return '未知';
}

// ── Extract name from notes when name field is empty ─────────────────────────
function extractNameFromNotes(notes) {
  if (!notes) return '';
  // notes starts with "名字 名字 养成材料计算…", grab first token
  const first = notes.split(/\s/)[0];
  return first || '';
}

// ── Parse recommended sets from notes ────────────────────────────────────────
function parseSets(notes) {
  if (!notes) return [];
  // Pattern: 驱动盘推荐 <set1> 4件套 <set2> 2件套
  const m = notes.match(/驱动盘推荐\s+(\S+)\s+4件套(?:\s+(\S+)\s+2件套)?/);
  if (!m) return [];
  return [m[1], m[2]].filter(Boolean);
}

function buildSetNotes(sets) {
  if (!sets.length) return '';
  if (sets.length === 1) return sets[0] + '4件套';
  return sets[0] + '4件套+' + sets[1] + '2件套';
}

// ── Build lookup from scraped data ───────────────────────────────────────────
const scrapedByName = new Map();
for (const entry of scraped) {
  const name = entry.name || extractNameFromNotes(entry.notes || '');
  if (name) scrapedByName.set(name, { ...entry, name });
}

console.log(`Scraped entries resolved: ${scrapedByName.size}`);

// ── Existing characters lookup ────────────────────────────────────────────────
const existingByName = new Map();
for (const c of chars.characters) existingByName.set(c.name, c);

// Alias: "11号" in characters.json → "「11号」" in scraped
const ALIASES = { '11号': '「11号」' };

// ── Update existing 12 chars ──────────────────────────────────────────────────
let updated = 0;
for (const char of chars.characters) {
  const scrapedName = ALIASES[char.name] || char.name;
  const entry = scrapedByName.get(scrapedName);
  if (!entry) { console.log(`[SKIP] ${char.name} — not in scraped`); continue; }

  const ms = entry.mainStats || {};
  char.main_stats = {
    '4': (ms[4] || ms['4'] || []).map(normMain),
    '5': (ms[5] || ms['5'] || []).map(normMain),
    '6': (ms[6] || ms['6'] || []).map(normMain),
  };
  char.priority_substats = (entry.substats || []).map(normSub);

  // Update sets only if currently empty
  if (!char.recommended_sets || char.recommended_sets.length === 0) {
    const sets = parseSets(entry.notes);
    if (sets.length) {
      char.recommended_sets = sets;
      char.set_notes = buildSetNotes(sets);
    }
  }

  console.log(`[OK]  ${char.name} | sets: ${char.recommended_sets?.join('+')} | 4:${JSON.stringify(char.main_stats['4'])}`);
  updated++;
}

// ── Add new chars ─────────────────────────────────────────────────────────────
let added = 0;
for (const [name, entry] of scrapedByName) {
  // Skip if already exists (including alias mapping)
  const existsAs = existingByName.has(name) ||
    [...existingByName.keys()].some(k => (ALIASES[k] || k) === name);
  if (existsAs) continue;

  const ms = entry.mainStats || {};
  const slot5 = (ms[5] || ms['5'] || []);
  const sets   = parseSets(entry.notes);
  const main_stats = {
    '4': (ms[4] || ms['4'] || []).map(normMain),
    '5': slot5.map(normMain),
    '6': (ms[6] || ms['6'] || []).map(normMain),
  };

  const newChar = {
    id: name,
    name,
    tier: 'TBD',
    role: '未知',
    element: inferElement(slot5),
    recommended_sets: sets,
    set_notes: buildSetNotes(sets),
    main_stats,
    priority_substats: (entry.substats || []).map(normSub),
    substat_notes: '',
    positioning: '',
  };

  chars.characters.push(newChar);
  existingByName.set(name, newChar);
  console.log(`[NEW] ${name} | elem:${newChar.element} | sets:${sets.join('+')} | 4:${JSON.stringify(main_stats['4'])}`);
  added++;
}

// ── Update sets array ─────────────────────────────────────────────────────────
const allSets = new Set(chars.sets || []);
for (const char of chars.characters) {
  for (const s of (char.recommended_sets || [])) {
    if (s) allSets.add(s);
  }
}
chars.sets = [...allSets].sort();

// ── Write back ────────────────────────────────────────────────────────────────
writeFileSync('D:/Desktop/zzz-disc-scorer/data/characters.json', JSON.stringify(chars, null, 2), 'utf-8');
console.log(`\nDone. Updated: ${updated}, Added: ${added}, Total: ${chars.characters.length}, Sets: ${chars.sets.length}`);
