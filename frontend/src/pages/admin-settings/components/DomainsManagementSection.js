import React, { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, Divider, Stack, Tab, Tabs } from '@mui/material';
import { Dns as DnsIcon, Storage as StorageIcon } from '@mui/icons-material';

const DomainsManagementSection = ({
  canManageCollectors,
  canRunMaintenance,
  canManageIpSources,
  collectors,
  refresh,
  ipSources
}) => {
  const tabs = useMemo(() => {
    const items = [];
    if (canManageCollectors || canRunMaintenance) {
      items.push({
        value: 'collectors',
        label: 'Collectors',
        icon: <DnsIcon fontSize="small" />
      });
    }
    if (canManageIpSources) {
      items.push({
        value: 'ip-sources',
        label: 'IP Sources',
        icon: <StorageIcon fontSize="small" />
      });
    }
    return items;
  }, [canManageCollectors, canManageIpSources, canRunMaintenance]);

  const [tab, setTab] = useState(tabs[0]?.value || 'collectors');

  useEffect(() => {
    if (!tabs.some((item) => item.value === tab)) {
      setTab(tabs[0]?.value || 'collectors');
    }
  }, [tab, tabs]);

  if (!tabs.length) {
    return null;
  }

  return (
    <Stack spacing={2}>
      <Card variant="outlined">
        <CardContent sx={{ py: 1.25, '&:last-child': { pb: 1.25 } }}>
          <Tabs
            value={tab}
            onChange={(_, value) => setTab(value)}
            variant="scrollable"
            allowScrollButtonsMobile
            sx={{ minHeight: 42 }}
          >
            {tabs.map((item) => (
              <Tab
                key={item.value}
                value={item.value}
                label={item.label}
                icon={item.icon}
                iconPosition="start"
                sx={{ minHeight: 42, textTransform: 'none', fontWeight: 600 }}
              />
            ))}
          </Tabs>
          <Divider sx={{ mt: 1 }} />
        </CardContent>
      </Card>

      {tab === 'collectors' ? (
        <Stack spacing={2}>
          {canManageCollectors ? collectors : null}
          {canRunMaintenance ? refresh : null}
        </Stack>
      ) : (
        ipSources
      )}
    </Stack>
  );
};

export default DomainsManagementSection;
