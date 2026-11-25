// add-wearhouse-settings-security D5: the client password policy (checked before anything reaches the broker).
import assert from 'node:assert/strict';
import test from 'node:test';

import {checkPassword} from '../src/password.ts';

test('length bounds', () => {
  assert.equal(checkPassword('Ab1!xyz').ok, false);
  assert.match(checkPassword('Ab1!xyz').problems[0], /at least 10/);
  assert.equal(checkPassword('a'.repeat(5) + 'B'.repeat(124)).ok, false);
});

test('common passwords are refused, including trailing-digit variants', () => {
  for (const pw of ['password123', 'Password123', 'qwertyuiop', 'wearhouse123', 'iloveyou2024!']) {
    assert.equal(checkPassword(pw).ok, false, pw);
  }
});

test('email name and handle are refused', () => {
  assert.match(checkPassword('dravenchen-blue-sky', {email: 'dravenchen@example.com'}).problems.join(), /email name/);
  assert.match(checkPassword('My-stylehub-2026!', {handle: 'stylehub'}).problems.join(), /handle/);
});

test('repetitive passwords are refused', () => {
  assert.equal(checkPassword('aaaaaaaaaaaa').ok, false);
  assert.equal(checkPassword('abababababab').ok, false);
});

test('strength grows with length and variety', () => {
  assert.equal(checkPassword('kitesurfing').strength, 'weak');            // passes, but short and one class
  assert.equal(checkPassword('Kitesurfing-at-dawn').strength, 'strong');  // long with variety
  assert.equal(checkPassword('kitesurf1ng2').strength, 'fair');
  assert.equal(checkPassword('Kitesurfing-at-dawn').ok, true);
});
