import React, { useEffect, useState } from 'react';
import { Alert } from '@mui/material';
import { Button, Combo, Mono, Panel } from '../../../design/primitives';

const ShareHostDialog = ({ open, host, apps, onClose, onShare }) => {
  const [target, setTarget] = useState(null);

  useEffect(() => {
    if (open) setTarget(null);
  }, [open]);

  return (
    <Panel
      open={open}
      onClose={onClose}
      maxWidth="xs"
      title="Share shared infrastructure"
      actions={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="contained" disabled={!target} onClick={() => onShare(target.id)}>
            Share host
          </Button>
        </>
      }
    >
      <Alert severity="info">
        This application keeps the notebook. The consumer can only attach the host to its own findings as an
        occurrence.
      </Alert>
      <Mono style={{ fontWeight: 600 }}>{host?.name}</Mono>
      <Combo
        label="Consumer application"
        options={apps}
        value={target}
        disableClearable={false}
        getOptionLabel={(option) => option?.name || ''}
        onChange={setTarget}
      />
    </Panel>
  );
};

export default ShareHostDialog;
