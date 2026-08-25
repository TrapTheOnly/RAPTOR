import React from 'react';
import { Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';

const SectionHeader = ({ title, children }) => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: SPACE.x12,
      marginBottom: SPACE.x16
    }}
  >
    <Text as="h2" variant="h2">
      {title}
    </Text>
    {children}
  </div>
);

export default SectionHeader;
