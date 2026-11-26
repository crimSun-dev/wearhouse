// @vitest-environment jsdom
import {describe, expect, it, vi} from 'vitest';
import {stepWithin, installKeyboard} from '../src/focus/engine.ts';
import {onIntent} from '../src/focus/store.ts';

describe('rail movement', () => {
  it('moves left and right and leaves the rail at its ends', () => {
    expect(stepWithin('rail', 0, 5, 1, 'right')).toBe(1);
    expect(stepWithin('rail', 4, 5, 1, 'right')).toBeNull();
    expect(stepWithin('rail', 0, 5, 1, 'left')).toBeNull();
    expect(stepWithin('rail', 2, 5, 1, 'up')).toBeNull();
    expect(stepWithin('rail', 2, 5, 1, 'down')).toBeNull();
  });
});

describe('grid movement', () => {
  // 3 columns, 7 items:  0 1 2 / 3 4 5 / 6
  it('moves within rows and columns', () => {
    expect(stepWithin('grid', 0, 7, 3, 'right')).toBe(1);
    expect(stepWithin('grid', 2, 7, 3, 'right')).toBeNull();
    expect(stepWithin('grid', 3, 7, 3, 'left')).toBeNull();
    expect(stepWithin('grid', 4, 7, 3, 'up')).toBe(1);
    expect(stepWithin('grid', 1, 7, 3, 'up')).toBeNull();
    expect(stepWithin('grid', 1, 7, 3, 'down')).toBe(4);
  });
  it('drops into a short last row and leaves from it', () => {
    expect(stepWithin('grid', 5, 7, 3, 'down')).toBe(6);
    expect(stepWithin('grid', 6, 7, 3, 'down')).toBeNull();
    expect(stepWithin('grid', 6, 7, 3, 'right')).toBeNull();
  });
});

describe('keyboard intents', () => {
  it('maps Escape, /, [, ], M and Q to app intents and ignores typing', () => {
    const dispose = installKeyboard(() => true);
    const seen: string[] = [];
    const off = onIntent(i => seen.push(i));
    for (const key of ['Escape', '/', '[', ']', 'm', 'Q']) document.dispatchEvent(new KeyboardEvent('keydown', {key, bubbles: true}));
    expect(seen).toEqual(['back', 'search', 'tabPrev', 'tabNext', 'menu', 'quick']);
    const input = document.createElement('input');
    document.body.append(input);
    input.focus();
    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'm', bubbles: true}));
    expect(seen).toHaveLength(6);
    input.remove();
    off(); dispose();
  });
  it('has no gamepad code path', async () => {
    const spy = vi.fn();
    Object.defineProperty(navigator, 'getGamepads', {value: spy, configurable: true});
    const dispose = installKeyboard(() => true);
    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight', bubbles: true}));
    expect(spy).not.toHaveBeenCalled();
    dispose();
  });
});