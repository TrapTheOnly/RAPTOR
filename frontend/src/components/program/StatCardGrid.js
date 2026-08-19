import React from 'react';
import { MetricStrip } from '../../design/primitives';

const StatCardGrid = ({ cards = [] }) => (
  <MetricStrip
    items={cards.map((card) => ({
      key: card.key,
      label: card.title,
      value: card.value,
      hint: card.subtitle,
      onClick: card.onClick
    }))}
  />
);

export default StatCardGrid;
