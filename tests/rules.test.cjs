const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Exercise the actual engine shipped to browsers, without a duplicate rules implementation.
const html = fs.readFileSync(path.join(__dirname, '../game/index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const engine = script.slice(0, script.indexOf('// This section connects'));
const E = vm.runInNewContext(engine + '\nRummy;', { performance });
const id = (color, number, copy = 0) => (color * 13 + number - 1) * 2 + copy;
const row = (name, tiles) => ({ id: name, tiles, choice: null });

test('deck has 106 unique physical tiles and two jokers', () => {
  assert.equal(E.tiles.length, 106);
  assert.equal(new Set(E.tiles.map(t => t.id)).size, 106);
  assert.equal(E.tiles.filter(t => t.type === 52).length, 2);
  assert.equal(E.rackPoints([id(0, 13), 104]), 43);
});

test('groups require equal numbers and different colors', () => {
  assert.ok(E.forms([id(0, 8), id(1, 8), id(2, 8)]).length);
  assert.equal(E.forms([id(0, 8), id(0, 8, 1), id(2, 8)]).length, 0);
  assert.equal(E.forms([id(0, 8), id(1, 9), id(2, 8)]).length, 0);
});

test('runs require consecutive numbers of one color and cannot wrap', () => {
  assert.ok(E.forms([id(1, 4), id(1, 5), id(1, 6)]).length);
  assert.equal(E.forms([id(1, 12), id(1, 13), id(1, 1)]).length, 0);
  assert.equal(E.forms([id(1, 4), id(1, 5), id(2, 6)]).length, 0);
  assert.equal(E.forms([id(1, 4), id(1, 6)]).length, 0);
});

test('jokers fill gaps and contribute their represented opening value', () => {
  const forms = E.forms([id(0, 9), 104, id(0, 11)]);
  assert.equal(forms.length, 1);
  assert.equal(forms[0].faces[104].number, 10);
  assert.equal(forms[0].points, 30);
});

test('opening requires at least 30 points', () => {
  for (const [number, expected] of [[9, false], [10, true]]) {
    const rack = [id(0, number), id(1, number), id(2, number)];
    assert.equal(E.audit({ rack, table: [] }, { rack: [], table: [row('a', rack)] }, false).ok, expected);
  }
});

test('audit rejects duplicated tiles and taking old table tiles into the rack', () => {
  const tiles = [id(0, 10), id(1, 10), id(2, 10)];
  const original = { rack: [id(3, 10)], table: [row('a', tiles)] };
  assert.equal(E.audit(original, { rack: [], table: [row('a', [...tiles, tiles[0]])] }, true).ok, false);
  assert.equal(E.audit(original, { rack: [tiles[0]], table: [row('a', [tiles[1], tiles[2], id(3, 10)])] }, true).ok, false);
});

test('table extensions are allowed only after opening', () => {
  const table = [row('a', [id(0, 10), id(1, 10), id(2, 10)])];
  const rack = [id(3, 10)];
  const draft = { rack: [], table: [row('a', [...table[0].tiles, ...rack])] };
  assert.equal(E.audit({ rack, table }, draft, false).ok, false);
  assert.equal(E.audit({ rack, table }, draft, true).ok, true);
});

test('solver returns audited opening and extension moves', () => {
  const rack = [id(0, 10), id(1, 10), id(2, 10), id(0, 1)];
  const plan = E.solve(rack, [], false);
  assert.ok(plan);
  assert.equal(E.audit({ rack, table: [] }, plan, false).ok, true);
  const extra = [id(3, 10)];
  const extension = E.solve(extra, plan.table, true);
  assert.ok(extension);
  assert.equal(extension.rack.length, 0);
  assert.equal(E.audit({ rack: extra, table: plan.table }, extension, true).ok, true);
});
