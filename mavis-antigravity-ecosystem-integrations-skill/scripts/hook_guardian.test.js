const test = require('node:test');
const assert = require('node:assert');
const { processHooks } = require('./hook_guardian');

test('processHooks', async (t) => {
    await t.test('handles empty input array', () => {
        const result = processHooks([]);
        assert.deepStrictEqual(result, []);
    });

    await t.test('keeps all hooks if all are active', () => {
        const input = [
            { id: 1, active: true },
            { id: 2, active: true, name: 'test' }
        ];
        const result = processHooks(input);

        assert.strictEqual(result.length, 2);
        assert.strictEqual(result[0].id, 1);
        assert.strictEqual(result[1].name, 'test');
    });

    await t.test('filters out inactive hooks', () => {
        const input = [
            { id: 1, active: true },
            { id: 2, active: false },
            { id: 3, active: true }
        ];
        const result = processHooks(input);

        assert.strictEqual(result.length, 2);
        assert.strictEqual(result[0].id, 1);
        assert.strictEqual(result[1].id, 3);
    });

    await t.test('adds processedAt valid ISO string and status: "ready" to each hook', () => {
        const input = [
            { id: 'abc', active: true, payload: 'data' }
        ];
        const result = processHooks(input);

        assert.strictEqual(result.length, 1);
        assert.strictEqual(result[0].id, 'abc');
        assert.strictEqual(result[0].payload, 'data');
        assert.strictEqual(result[0].status, 'ready');

        // verify processedAt is a valid date string
        const date = new Date(result[0].processedAt);
        assert.ok(!isNaN(date.getTime()), 'processedAt should be a valid ISO string');
    });
    await t.test('does not mutate original hook objects', () => {
        const input = [{ id: 1, active: true, status: 'pending' }];
        const result = processHooks(input);
        assert.strictEqual(input[0].status, 'pending');
        assert.strictEqual(result[0].status, 'ready');
    });

    await t.test('treats missing active property as inactive', () => {
        const input = [{ id: 1 }, { id: 2, active: true }];
        const result = processHooks(input);
        assert.strictEqual(result.length, 1);
        assert.strictEqual(result[0].id, 2);
    });
});
