const test = require('node:test');
const assert = require('node:assert');
const { processHooks } = require('./hook_guardian');

test('processHooks', async (t) => {
  await t.test('should filter out inactive hooks', () => {
    const hooks = [
      { id: 1, active: true },
      { id: 2, active: false },
      { id: 3, active: true }
    ];
    const result = processHooks(hooks);
    assert.strictEqual(result.length, 2);
    assert.strictEqual(result[0].id, 1);
    assert.strictEqual(result[1].id, 3);
  });

  await t.test('should add processedAt ISO string and status ready', () => {
    const hooks = [
      { id: 1, active: true }
    ];
    const result = processHooks(hooks);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].status, 'ready');
    assert.ok(result[0].processedAt);

    // Verify it's a valid ISO string
    const date = new Date(result[0].processedAt);
    assert.ok(!isNaN(date.getTime()), 'processedAt should be a valid date string');
    assert.strictEqual(date.toISOString(), result[0].processedAt);
  });

  await t.test('should handle empty array', () => {
    const hooks = [];
    const result = processHooks(hooks);
    assert.deepStrictEqual(result, []);
  });

  await t.test('should handle hooks without active property as inactive by default in filter', () => {
    const hooks = [
      { id: 1 },
      { id: 2, active: true }
    ];
    const result = processHooks(hooks);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].id, 2);
  });
});
