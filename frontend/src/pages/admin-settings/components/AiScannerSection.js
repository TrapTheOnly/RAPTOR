import React from 'react';
import { Tabs } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import { AI_SCANNER_SUBSECTIONS } from '../constants';
import AiConnectionsPanel from './AiConnectionsPanel';
import AiLocalModelPanel from './AiLocalModelPanel';
import AiPolicyPanel from './AiPolicyPanel';

const AiScannerSection = ({ tab, onSelectTab, showMessage }) => {
  const tabs = AI_SCANNER_SUBSECTIONS.map((item) => ({ value: item.key, label: item.tabLabel }));
  return (
    <div>
      <Tabs value={tab} onChange={onSelectTab} items={tabs} />
      <div style={{ marginTop: SPACE.x16 }}>
        {tab === 'connections' ? <AiConnectionsPanel showMessage={showMessage} /> : null}
        {tab === 'local' ? <AiLocalModelPanel showMessage={showMessage} /> : null}
        {tab === 'policy' ? <AiPolicyPanel showMessage={showMessage} /> : null}
      </div>
    </div>
  );
};

export default AiScannerSection;
