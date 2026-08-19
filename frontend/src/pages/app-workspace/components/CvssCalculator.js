import React from 'react';
import { Combo, Tag, Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import { CVSS_METRIC_ROWS, CVSS_OPTIONS } from '../../pentest-record/constants';
import { getCvssSeverityConfig } from '../../pentest-record/cvss';

const CvssCalculator = ({ metrics = {}, score = 0, onChange, disabled = false }) => {
  const meta = getCvssSeverityConfig(score);
  return (
    <section>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: SPACE.x16 }}>
        <Text as="div" variant="h2">
          CVSS 3.1
        </Text>
        <Tag emphasized style={{ color: meta.color }}>
          {score > 0 ? `${score.toFixed(1)} ${meta.label}` : 'Unscored'}
        </Tag>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: SPACE.x12 }}>
        {CVSS_METRIC_ROWS.map(([key, label]) => (
          <Combo
            key={key}
            label={label}
            options={CVSS_OPTIONS[key]}
            value={metrics[key] || CVSS_OPTIONS[key][0].value}
            onChange={(value) => onChange({ ...metrics, [key]: value })}
            disabled={disabled}
          />
        ))}
      </div>
    </section>
  );
};

export default CvssCalculator;
