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

test('run joining handles an out-of-order chain without changing the input or tile IDs', () => {
  const table = [row('end', [8,9,10].map(n=>id(1,n))),
    row('start', [1,2,3].map(n=>id(1,n))), row('middle', [4,5,6,7].map(n=>id(1,n)))];
  const snapshot = JSON.stringify(table);
  const merged = E.mergeRuns(table);
  assert.equal(merged.length, 1);
  assert.equal(E.form(merged[0]).key, 'r1:1:10');
  assert.equal(JSON.stringify(table), snapshot);
  assert.ok(E.same(E.flat(table), E.flat(merged)));
  assert.equal(new Set(E.flat(merged)).size, 10);
  assert.equal(JSON.stringify(E.mergeRuns(merged)), JSON.stringify(merged));
});

test('run joining keeps gaps, different colors, overlapping copies, groups, and drafts separate', () => {
  const table = [row('a', [1,2,3].map(n=>id(0,n))),
    row('gap', [5,6,7].map(n=>id(0,n))),
    row('overlap', [1,2,3].map(n=>id(0,n,1))),
    row('blue', [4,5,6].map(n=>id(1,n))),
    row('group', [id(0,9),id(1,9),id(2,9)]), row('draft',[id(0,4)])];
  assert.equal(E.mergeRuns(table).length, table.length);
});

test('a locked old run cannot contribute points toward the opening', () => {
  const old = row('old',[1,2,3].map(n=>id(0,n)));
  const rack = [4,5,6].map(n=>id(0,n));
  const opening = [old,row('new',rack)];
  const merged = E.mergeRuns(opening, ['old']);
  assert.equal(merged.length, 2);
  assert.equal(E.audit({rack,table:[old]}, {rack:[],table:merged}, false).ok, false);
  assert.equal(E.mergeRuns(opening).length, 1);
});

test('a joker keeps its chosen face when touching runs join', () => {
  const a = { ...row('a',[id(1,4),104,id(1,6)]), choice:'r1:4:3' };
  const b = row('b',[7,8,9].map(n=>id(1,n)));
  const merged = E.mergeRuns([a,b]);
  assert.equal(merged.length, 1);
  assert.equal(E.form(merged[0]).faces[104].number, 5);
  assert.equal(E.form(merged[0]).key, 'r1:4:6');
  const c = {...row('c',[id(0,1),105,id(0,3)]),choice:'r0:1:3'};
  const d = {...row('d',[id(0,4),104,id(0,6)]),choice:'r0:4:3'};
  // The engine orders jokers by ID; avoid a join that would swap the selected faces.
  assert.equal(E.mergeRuns([c,d]).length, 2);
});

test('joining supports the full 1–13 run and never wraps 13 back to 1', () => {
  const table = [row('a',[1,2,3].map(n=>id(2,n))),
    row('b',[4,5,6,7].map(n=>id(2,n))), row('c',[8,9,10,11,12,13].map(n=>id(2,n)))];
  assert.equal(E.form(E.mergeRuns(table)[0]).key, 'r2:1:13');
  assert.equal(E.mergeRuns([table[0],row('end',[11,12,13].map(n=>id(2,n)))]).length, 2);
});
