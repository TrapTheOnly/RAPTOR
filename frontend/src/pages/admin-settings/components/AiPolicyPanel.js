import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Button, Field, Stepper, SwitchRow, Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import SectionHeader from './SectionHeader';

const AiPolicyPanel = ({ showMessage }) => {
  const [config, setConfig] = useState({
    allow_destructive_tools: false,
    max_concurrent_scans: 2,
    cost_limit_usd: 5,
    thinking_budget_tokens: 8000,
    max_turns: 40,
    proxy_url: '',
    proxy_username: '',
    proxy_password: ''
  });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await axios.get('/admin/scanner-config');
      const c = response.data?.config || {};
      setConfig({
        allow_destructive_tools: Boolean(Number(c.allow_destructive_tools || 0)),
        max_concurrent_scans: Number(c.max_concurrent_scans || 2),
        cost_limit_usd: Number(c.cost_limit_usd || 5),
        thinking_budget_tokens: Number(c.thinking_budget_tokens || 8000),
        max_turns: Number(c.max_turns || 40),
        proxy_url: c.proxy_url || '',
        proxy_username: c.proxy_username || '',
        proxy_password: c.proxy_password || ''
      });
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to load scanner policy.');
    }
  }, [showMessage]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      await axios.put('/admin/scanner-config', config);
      showMessage?.('success', 'Policy saved.');
      await load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to save policy.');
    } finally {
      setSaving(false);
    }
  };

  const setField = (key) => (event) => {
    setConfig((prev) => ({ ...prev, [key]: event.target.value }));
  };

  return (
    <div style={{ maxWidth: 520 }}>
      <SectionHeader title="Policy" />
      <Text as="p" variant="meta" tone="secondary" style={{ margin: `0 0 ${SPACE.x16}px` }}>
        Dollar estimates use the active model&apos;s published list price. Local scans are $0 and
        stop at max turns. The cost limit only fires when those rates are known.
      </Text>
      <SwitchRow
        label="Allow destructive Kali tools"
        hint="Also requires the environment ceiling. sqlmap, Hydra, Metasploit, and shell."
        checked={config.allow_destructive_tools}
        onChange={(checked) => setConfig((prev) => ({ ...prev, allow_destructive_tools: checked }))}
      />
      <Stepper
        label="Max concurrent scans"
        value={config.max_concurrent_scans}
        min={1}
        max={10}
        onChange={(value) => setConfig((prev) => ({ ...prev, max_concurrent_scans: value }))}
      />
      <Field
        label="Cost limit (USD)"
        hint="Stops the scan when the list-price estimate reaches this cap."
        value={String(config.cost_limit_usd)}
        onChange={setField('cost_limit_usd')}
      />
      <Field
        label="Thinking budget tokens (Anthropic / Bedrock)"
        value={String(config.thinking_budget_tokens)}
        onChange={setField('thinking_budget_tokens')}
      />
      <Field label="Max turns" value={String(config.max_turns)} onChange={setField('max_turns')} />
      <Field label="Proxy URL" value={config.proxy_url} onChange={setField('proxy_url')} />
      <Field label="Proxy username" value={config.proxy_username} onChange={setField('proxy_username')} />
      <Field
        label="Proxy password (leave blank to keep)"
        type="password"
        value={config.proxy_password}
        onChange={setField('proxy_password')}
      />
      <div style={{ marginTop: SPACE.x16 }}>
        <Button variant="contained" disabled={saving} onClick={save}>
          Save policy
        </Button>
      </div>
    </div>
  );
};

export default AiPolicyPanel;
