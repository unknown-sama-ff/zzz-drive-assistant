import { readFileSync, writeFileSync } from 'fs';

const scraped = JSON.parse(readFileSync('D:/Desktop/zzz-disc-scorer/scripts/scraped_chars.json', 'utf-8'));
const chars = JSON.parse(readFileSync('D:/Desktop/zzz-disc-scorer/data/characters.json', 'utf-8'));

// Normalize main stat names (scraped page omits %)
function normMain(s) {
  const noPercent = ['异常精通', '异常掌控', '冲击力', '穿透值'];
  if (noPercent.includes(s)) return s;
  if (s.endsWith('%')) return s;
  return s + '%';
}

// Normalize substat names
function normSub(s) {
  if (s === '攻击力百分比') return '攻击力%';
  if (s === '生命值百分比') return '生命值%';
  if (s === '防御力百分比') return '防御力%';
  if (s === '异常精通') return '异常精通';
  if (s === '异常掌控') return '异常掌控';
  if (s === '冲击力') return '冲击力';
  if (s === '穿透值') return '穿透值';
  // bare nouns without 百分比 are numeric values
  if (s === '攻击力') return '攻击力数值';
  if (s === '生命值') return '生命值数值';
  if (s === '防御力') return '防御力数值';
  if (s.endsWith('%')) return s;
  return s + '%';
}

// Build lookup: name → scraped entry
const lookup = new Map();
for (const entry of scraped) {
  if (entry.name) lookup.set(entry.name, entry);
}

// Also handle alternate names
const aliases = {
  '11号': '「11号」',
};

let updated = 0;
for (const char of chars.characters) {
  const scrapedName = aliases[char.name] || char.name;
  const entry = lookup.get(scrapedName) || lookup.get(char.name);
  if (!entry) {
    console.log(`[SKIP] ${char.name} — not found in scraped data`);
    continue;
  }

  const ms = entry.mainStats;
  char.main_stats = {
    '4': ms[4].map(normMain),
    '5': ms[5].map(normMain),
    '6': ms[6].map(normMain),
  };
  char.priority_substats = entry.substats.map(normSub);

  console.log(`[OK] ${char.name}`);
  console.log(`     4: ${JSON.stringify(char.main_stats['4'])}`);
  console.log(`     5: ${JSON.stringify(char.main_stats['5'])}`);
  console.log(`     6: ${JSON.stringify(char.main_stats['6'])}`);
  console.log(`     subs: ${JSON.stringify(char.priority_substats)}`);
  updated++;
}

writeFileSync('D:/Desktop/zzz-disc-scorer/data/characters.json', JSON.stringify(chars, null, 2), 'utf-8');
console.log(`\nUpdated ${updated}/${chars.characters.length} characters.`);
