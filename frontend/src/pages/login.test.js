const fs = require('fs');
const path = require('path');

const readSource = (relativePath) =>
  fs.readFileSync(path.join(__dirname, relativePath), 'utf8');

test('login is a starlight scene without the RAPTOR acronym', () => {
  const login = readSource('./ModernLogin.js');
  const stars = readSource('./login/Starfield.js');
  expect(login).toContain('Starfield');
  expect(login).toContain('from \'motion/react\'');
  expect(login).toContain('Sign in');
  expect(login).toContain('/auth/sso/providers');
  expect(login).toContain('Sign in with');
  expect(login).not.toContain('Reconnaissance, Assessment, Penetration Testing');
  expect(login).not.toContain('raptorLoginGlow');
  expect(stars).toContain('raptorStarTwinkle');
  expect(stars).toContain('useReducedMotion');
  expect(stars).toContain('M8 0 L9.15 6.15');
  expect(stars).toContain('size: 0.02 + mulberry(i * 31 + 7) * 0.03');
  expect(stars).not.toContain('<circle');
  expect(login).toContain('setDarkMode');
  expect(login).toContain('palette.accentLine');
});
