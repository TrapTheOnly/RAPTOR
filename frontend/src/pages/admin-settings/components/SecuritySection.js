import React from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  InputAdornment,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import {
  Password as PasswordIcon,
  Security as SecurityIcon,
  VpnKey as VpnKeyIcon
} from '@mui/icons-material';
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH } from '../constants';
import SectionHeader from './SectionHeader';

const SecuritySection = ({
  loading,
  currentPassword,
  setCurrentPassword,
  newPassword,
  setNewPassword,
  retypePassword,
  setRetypePassword,
  onChangePassword
}) => (
  <Card>
    <CardContent>
      <SectionHeader icon={SecurityIcon} title="Security Settings" />

      <Stack spacing={2}>
        <TextField
          label="Current Password"
          type="password"
          variant="outlined"
          fullWidth
          value={currentPassword}
          onChange={(event) => setCurrentPassword(event.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <VpnKeyIcon />
              </InputAdornment>
            )
          }}
        />
        <TextField
          label="New Password"
          type="password"
          variant="outlined"
          fullWidth
          value={newPassword}
          onChange={(event) => setNewPassword(event.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <PasswordIcon />
              </InputAdornment>
            )
          }}
        />
        <TextField
          label="Confirm New Password"
          type="password"
          variant="outlined"
          fullWidth
          value={retypePassword}
          onChange={(event) => setRetypePassword(event.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <PasswordIcon />
              </InputAdornment>
            )
          }}
        />
        <Box>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
            NIST password requirements:
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            - At least {MIN_PASSWORD_LENGTH} characters (max {MAX_PASSWORD_LENGTH})
          </Typography>
          <Typography variant="caption" color="text.secondary" display="block">
            - Not a common password
          </Typography>
        </Box>
        <Button
          variant="contained"
          size="large"
          startIcon={<SecurityIcon />}
          onClick={onChangePassword}
          disabled={loading}
          sx={{ mt: 2 }}
        >
          Update Password
        </Button>
      </Stack>
    </CardContent>
  </Card>
);

export default SecuritySection;
