import React from 'react';
import { Button, Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';

const DomainsRefreshCard = ({ loading, onRunUpdate }) => (
  <div
    style={{
      display: 'flex',
      flexWrap: 'wrap',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: SPACE.x16,
      marginTop: SPACE.x24,
      paddingTop: SPACE.x16,
      borderTop: '1px solid var(--raptor-line)'
    }}
  >
    <Text as="h2" variant="h2">
      Refresh
    </Text>
    <Button variant="contained" onClick={onRunUpdate} disabled={loading} style={{ flexShrink: 0 }}>
      Run update
    </Button>
  </div>
);

export default DomainsRefreshCard;
