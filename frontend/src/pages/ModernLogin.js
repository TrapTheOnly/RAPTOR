import axios from 'axios';
import { Alert, IconButton } from '@mui/material';
import { Brightness4, Brightness7, Visibility, VisibilityOff } from '@mui/icons-material';
import { motion } from 'motion/react';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button, Field, Text } from '../design/primitives';
import { panelVariants } from '../design/motion';
import { alpha, FONTS, SPACE, TYPE } from '../design/tokens';
import { usePalette } from '../design/usePalette';
import Starfield from './login/Starfield';

const MIN_PASSWORD_LENGTH = 12;
const MAX_PASSWORD_LENGTH = 64;
const COMMON_PASSWORDS = new Set([
  'password', 'password1', '123456', '12345678', '123456789',
  'qwerty', 'qwerty123', 'letmein', 'welcome', 'admin',
  'admin123', 'iloveyou', 'monkey', 'dragon', 'football',
  'abc123', '111111', 'trustno1', 'sunshine', 'princess',
  'login', 'qwertyuiop', 'passw0rd', 'master', 'shadow'
]);

const CARD_RADIUS = 18;

const SSO_ERROR_MESSAGES = {
  not_allowlisted: 'This account is not allowed to sign in to RAPTOR.',
  invalid_state: 'Sign-in could not be completed. Try again.',
  idp_unavailable: 'The identity provider is unavailable.',
  access_denied: 'Sign-in was cancelled or denied.',
  unsupported: 'That sign-in method is not supported.'
};

const ModernLogin = ({
  setLoggedIn,
  setGlobalUsername,
  setGlobalUserRole,
  setGlobalUserPermissions,
  setPasswordResetRequired,
  passwordResetRequired = false,
  resetUsername = '',
  resetUserType = null,
  setResetUserType = () => {},
  darkMode = true,
  setDarkMode
}) => {
  const palette = usePalette();
  const [searchParams] = useSearchParams();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [ssoProviders, setSsoProviders] = useState([]);
  const [showPassword, setShowPassword] = useState(false);
  const [resetMode, setResetMode] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [resetError, setResetError] = useState('');
  const [resetLoading, setResetLoading] = useState(false);

  useEffect(() => {
    setResetMode(passwordResetRequired);
  }, [passwordResetRequired]);

  useEffect(() => {
    const code = searchParams.get('sso_error');
    if (code) {
      setError(SSO_ERROR_MESSAGES[code] || 'Sign-in failed. Try again.');
    }
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    axios
      .get('/auth/sso/providers')
      .then((response) => {
        if (!cancelled) setSsoProviders(response.data?.providers || []);
      })
      .catch(() => {
        if (!cancelled) setSsoProviders([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (resetMode && resetUsername) {
      setUsername(resetUsername);
    }
  }, [resetMode, resetUsername]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await axios.post('/login', {
        username,
        password
      });

      if (response.status === 200) {
        if (response.data.status === 'password_reset_required') {
          setResetMode(true);
          setPasswordResetRequired(true);
          setResetUserType(response.data.user_type || null);
          setError('');
        } else if (response.data.status === 'logged_in') {
          setLoggedIn(true);
          setPasswordResetRequired(false);
          setResetUserType(null);
          setGlobalUsername(username);
          setGlobalUserRole(response.data.user_type);
          setGlobalUserPermissions(response.data.permissions || []);
        }
      }
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Invalid username or password');
      } else {
        setError('Login failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const validatePassword = (value) => {
    if (!value) return 'Password is required.';
    if (value.length < MIN_PASSWORD_LENGTH) {
      return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
    }
    if (value.length > MAX_PASSWORD_LENGTH) {
      return `Password must be at most ${MAX_PASSWORD_LENGTH} characters.`;
    }
    if (COMMON_PASSWORDS.has(value.trim().toLowerCase())) {
      return 'Password is too common.';
    }
    if (username && value.toLowerCase().includes(username.toLowerCase())) {
      return 'Password must not contain the username.';
    }
    return '';
  };

  const handleResetSubmit = async (event) => {
    event.preventDefault();
    setResetError('');
    const validationError = validatePassword(newPassword);
    if (validationError) {
      setResetError(validationError);
      return;
    }
    if (newPassword !== confirmPassword) {
      setResetError('Passwords do not match.');
      return;
    }

    setResetLoading(true);
    try {
      const endpoint = resetUserType === 'admin' ? '/admin-reset-password' : '/user-reset-password';
      const response = await axios.post(endpoint, {
        new_password: newPassword
      });
      if (response.status === 200 && response.data.status === 'logged_in') {
        setLoggedIn(true);
        setPasswordResetRequired(false);
        setResetUserType(null);
        setGlobalUsername(response.data.username || username);
        setGlobalUserRole(response.data.user_type || 'user');
        setGlobalUserPermissions(response.data.permissions || []);
      }
    } catch (err) {
      setResetError(err.response?.data?.error || 'Password reset failed. Please try again.');
    } finally {
      setResetLoading(false);
    }
  };

  const eye = (
    <IconButton
      onClick={() => setShowPassword((open) => !open)}
      edge="end"
      aria-label={showPassword ? 'Hide password' : 'Show password'}
      sx={{ color: palette.textSecondary }}
    >
      {showPassword ? <VisibilityOff /> : <Visibility />}
    </IconButton>
  );

  const isDark = palette.mode === 'dark';
  const glow = alpha(palette.accent, isDark ? 0.32 : 0.22);

  return (
    <div
      style={{
        minHeight: '100vh',
        position: 'relative',
        overflow: 'hidden',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: SPACE.x24,
        background: palette.canvas
      }}
    >
      <Starfield color={palette.text} accent={palette.accent} />
      <div
        aria-hidden
        style={{
          position: 'absolute',
          inset: 0,
          background: isDark
            ? `radial-gradient(ellipse at 50% 42%, ${alpha(palette.accent, 0.08)} 0%, transparent 42%)`
            : `radial-gradient(ellipse at 50% 42%, ${alpha(palette.accent, 0.1)} 0%, transparent 46%)`,
          pointerEvents: 'none'
        }}
      />

      {typeof setDarkMode === 'function' ? (
        <IconButton
          onClick={() => setDarkMode(!darkMode)}
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          sx={{
            position: 'absolute',
            top: 16,
            right: 16,
            zIndex: 1,
            color: palette.textSecondary,
            border: `1px solid ${palette.lineStrong}`,
            borderRadius: '10px'
          }}
        >
          {darkMode ? <Brightness7 fontSize="small" /> : <Brightness4 fontSize="small" />}
        </IconButton>
      ) : null}

      <motion.div
        variants={panelVariants}
        initial="initial"
        animate="animate"
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: 400,
          padding: '36px 32px 32px',
          borderRadius: CARD_RADIUS,
          background: isDark ? 'rgba(14, 16, 19, 0.78)' : 'rgba(255, 255, 255, 0.86)',
          border: `1px solid ${palette.lineStrong}`,
          boxShadow: `0 0 0 1px ${palette.accentLine}, 0 18px 64px ${glow}`,
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)'
        }}
      >
        <Text
          as="h1"
          style={{
            ...TYPE.h1,
            fontFamily: FONTS.sans,
            fontWeight: 700,
            fontSize: 28,
            letterSpacing: '0.18em',
            color: palette.text,
            textAlign: 'center',
            margin: `0 0 ${SPACE.x32}px`
          }}
        >
          RAPTOR
        </Text>

        {resetMode ? (
          <form onSubmit={handleResetSubmit} style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x16 }}>
            {resetError ? <Alert severity="error">{resetError}</Alert> : null}
            <Field label="Username" value={username} disabled autoComplete="username" />
            <Field
              label="New password"
              type={showPassword ? 'text' : 'password'}
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              required
              autoComplete="new-password"
              trailing={eye}
            />
            <Field
              label="Confirm new password"
              type={showPassword ? 'text' : 'password'}
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
              autoComplete="new-password"
            />
            <Text as="p" variant="meta" tone="secondary" style={{ margin: 0 }}>
              At least {MIN_PASSWORD_LENGTH} characters, not a common password, and must not contain the username.
            </Text>
            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={resetLoading || !newPassword || !confirmPassword}
              style={{ minHeight: 44, borderRadius: 12 }}
            >
              {resetLoading ? 'Updating password…' : 'Reset password'}
            </Button>
          </form>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x16 }}>
            {error ? <Alert severity="error">{error}</Alert> : null}
            <Field
              label="Username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              autoComplete="username"
              autoFocus
            />
            <Field
              label="Password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
              autoComplete="current-password"
              trailing={eye}
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={loading || !username || !password}
              style={{ minHeight: 44, borderRadius: 12 }}
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </Button>
            {ssoProviders.length > 0 ? (
              <>
                <Text as="p" variant="micro" tone="tertiary" style={{ margin: `${SPACE.x8}px 0 0`, textAlign: 'center' }}>
                  or
                </Text>
                {ssoProviders.map((provider) => (
                  <Button
                    key={provider.alias}
                    type="button"
                    variant="outlined"
                    fullWidth
                    onClick={() => {
                      window.location.assign(`/auth/sso/${encodeURIComponent(provider.alias)}/start`);
                    }}
                    style={{ minHeight: 44, borderRadius: 12 }}
                  >
                    Sign in with {provider.display_name || provider.alias}
                  </Button>
                ))}
              </>
            ) : null}
          </form>
        )}
      </motion.div>
    </div>
  );
};

export default ModernLogin;
