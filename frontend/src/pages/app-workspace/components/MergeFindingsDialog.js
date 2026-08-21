import React, { useEffect, useMemo, useState } from 'react';
import { Alert } from '@mui/material';
import { Button, Combo, Panel, SeverityDot, Text, severityKeyFromScore } from '../../../design/primitives';

const MergeFindingsDialog = ({ open, survivor, findings, onClose, onMerge }) => {
  const [loser, setLoser] = useState(null);

  useEffect(() => {
    if (open) setLoser(null);
  }, [open]);

  const candidates = useMemo(
    () => findings.filter((item) => item.id !== survivor?.id),
    [findings, survivor]
  );

  const mergedHostCount = useMemo(() => {
    if (!survivor || !loser) return 0;
    const ids = new Set([
      ...(survivor.occurrences || []).map((item) => item.record_id),
      ...(loser.occurrences || []).map((item) => item.record_id)
    ]);
    return ids.size;
  }, [survivor, loser]);

  return (
    <Panel
      open={open}
      onClose={onClose}
      title="Merge duplicate finding"
      actions={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="contained" disabled={!loser} onClick={() => onMerge(loser.id)}>
            Merge and remove duplicate
          </Button>
        </>
      }
    >
      <Alert severity="info">
        The finding you keep keeps its write-up, category, CVSS score, and ticket. Empty description,
        impact, evidence, and remediation fill from the duplicate. Hosts and collaborators move across,
        then the duplicate is removed.
      </Alert>
      <div>
        <Text as="div" variant="micro" tone="tertiary" style={{ marginBottom: 6 }}>
          Keeping
        </Text>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <SeverityDot severity={severityKeyFromScore(survivor?.baseScore)} />
          <Text variant="bodyStrong">{survivor?.title || survivor?.categoryName || 'Untitled finding'}</Text>
        </div>
        <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 4 }}>
          {(survivor?.occurrences || []).length} host(s) today
        </Text>
      </div>
      <Combo
        label="Finding to merge in and remove"
        options={candidates}
        value={loser}
        disableClearable={false}
        getOptionLabel={(option) => option?.title || option?.categoryName || option?.id || ''}
        renderOption={(props, option) => (
          <li {...props} key={option.id}>
            <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
              <SeverityDot severity={severityKeyFromScore(option.baseScore)} />
              <span>{option.title || option.categoryName || option.id}</span>
            </span>
          </li>
        )}
        onChange={setLoser}
      />
      {loser ? (
        <Text variant="meta" tone="secondary">
          After the merge this finding covers {mergedHostCount} host(s).
        </Text>
      ) : null}
    </Panel>
  );
};

export default MergeFindingsDialog;
