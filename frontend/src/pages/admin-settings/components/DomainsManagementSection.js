import React, { useEffect, useMemo } from 'react';
import { Tabs } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import { DOMAIN_SUBSECTIONS } from '../constants';

const DomainsManagementSection = ({
  canManageCollectors,
  canRunMaintenance,
  canManageIpSources,
  tab,
  onSelectTab,
  collectors,
  refresh,
  cloudDns,
  ipSources
}) => {
  const tabs = useMemo(() => {
    const flags = {
      collectors: canManageCollectors || canRunMaintenance,
      cloud: canManageCollectors,
      ipSources: canManageIpSources
    };
    return DOMAIN_SUBSECTIONS.filter((item) => {
      if (item.key === 'collectors') return flags.collectors;
      if (item.key === 'cloud') return flags.cloud;
      if (item.key === 'ip-sources') return flags.ipSources;
      return false;
    }).map((item) => ({ value: item.key, label: item.tabLabel }));
  }, [canManageCollectors, canManageIpSources, canRunMaintenance]);

  useEffect(() => {
    if (!tabs.length) return;
    if (!tabs.some((item) => item.value === tab)) {
      onSelectTab(tabs[0].value);
    }
  }, [onSelectTab, tab, tabs]);

  if (!tabs.length) return null;

  return (
    <div>
      <Tabs value={tab} onChange={onSelectTab} items={tabs} />
      {tab === 'collectors' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x16 }}>
          {canManageCollectors ? collectors : null}
          {canRunMaintenance ? refresh : null}
        </div>
      ) : null}
      {tab === 'cloud' ? cloudDns : null}
      {tab === 'ip-sources' ? ipSources : null}
    </div>
  );
};

export default DomainsManagementSection;
