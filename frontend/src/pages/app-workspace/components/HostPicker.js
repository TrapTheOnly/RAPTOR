import React, { useEffect, useState } from 'react';
import { Combo, EnvTag, Mono } from '../../../design/primitives';
import { listAppHosts } from '../services';

const HostPicker = ({
  appId,
  sharedHosts = [],
  label,
  placeholder,
  multiple = false,
  value,
  onChange,
  excludeIds = [],
  disabled = false,
  locked = false,
  envId
}) => {
  const [options, setOptions] = useState([]);
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (!appId || locked) return undefined;
    let cancelled = false;
    const handle = setTimeout(async () => {
      try {
        const response = await listAppHosts(appId, {
          q: query.trim() || undefined,
          limit: 20,
          env_id: envId || undefined
        });
        if (cancelled) return;
        const remote = response.data.hosts || [];
        const term = query.trim().toLowerCase();
        const shared = (sharedHosts || []).filter(
          (host) => !term || String(host.name || '').toLowerCase().includes(term)
        );
        const merged = [...remote];
        shared.forEach((host) => {
          if (!merged.some((item) => String(item.id) === String(host.id))) merged.push(host);
        });
        setOptions(merged);
      } catch (error) {
        if (!cancelled) setOptions(sharedHosts || []);
      }
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [appId, query, sharedHosts, locked, envId]);

  const excluded = new Set((excludeIds || []).map((id) => String(id)));
  const visible = (locked && value ? (multiple ? value : [value]) : options).filter(
    (host) => host && !excluded.has(String(host.id))
  );

  return (
    <Combo
      label={label}
      placeholder={placeholder}
      multiple={multiple}
      options={visible}
      value={value}
      disabled={disabled || locked}
      disableClearable={locked || false}
      getOptionLabel={(option) => option?.name || ''}
      filterOptions={(items) => items}
      onInputChange={(_event, next, reason) => {
        if (reason === 'input') setQuery(next);
      }}
      renderOption={(props, option) => (
        <li {...props} key={option.id}>
          <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
            <EnvTag
              slug={option.environment_slug || (option.owner_application_name ? 'shared' : 'unassigned')}
              label={option.owner_application_name ? 'shared' : option.environment_slug || 'unassigned'}
            />
            <Mono>{option.name}</Mono>
          </span>
        </li>
      )}
      onChange={onChange}
    />
  );
};

export default HostPicker;
