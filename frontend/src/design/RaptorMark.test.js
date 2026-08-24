const fs = require('fs');
const path = require('path');

const readSource = (relativePath) =>
  fs.readFileSync(path.join(__dirname, relativePath), 'utf8');

test('RaptorMark ships mark, wordmark, and lockup variants', () => {
  const source = readSource('./RaptorMark.js');
  expect(source).toContain("variant === 'wordmark'");
  expect(source).toContain("variant === 'lockup'");
  expect(source).toContain("variant === 'lockupPrint'");
  expect(source).toContain('markLight');
  expect(source).toContain('wordmarkLight');
  expect(source).toContain('lockupLight');
  expect(source).toContain('overflow: \'hidden\'');
  expect(source).toContain("position: 'absolute'");
  expect(source).toContain('minHeight: 0');
  expect(source).toContain('const SAFE = 0.04');
  expect(source).toContain('mark: 32');
  expect(source).toContain('wordmark: 16');
  expect(source).toContain('lockup: 192');
  expect(fs.existsSync(path.join(__dirname, '../brand/raptor-mark.png'))).toBe(true);
  expect(fs.existsSync(path.join(__dirname, '../brand/raptor-mark-light.png'))).toBe(true);
  expect(fs.existsSync(path.join(__dirname, '../brand/raptor-wordmark.png'))).toBe(true);
  expect(fs.existsSync(path.join(__dirname, '../brand/raptor-wordmark-light.png'))).toBe(true);
  expect(fs.existsSync(path.join(__dirname, '../brand/raptor-lockup.png'))).toBe(true);
  expect(fs.existsSync(path.join(__dirname, '../brand/raptor-lockup-light.png'))).toBe(true);
  const png = (name) => {
    const bytes = fs.readFileSync(path.join(__dirname, '../brand', name));
    expect(bytes.slice(0, 8)).toEqual(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
    expect(bytes.length).toBeGreaterThan(20_000);
  };
  png('raptor-mark-light.png');
  png('raptor-wordmark-light.png');
  png('raptor-lockup-light.png');
});
