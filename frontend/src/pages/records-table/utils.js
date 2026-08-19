import Papa from 'papaparse';
import { isEmphasisedEnv } from '../../design/tokens';

export const extractParameterValues = (records, searchParameters) => {
  const values = {};
  const counts = {};

  searchParameters.forEach((param) => {
    if (param.key === 'ports') {
      const allPorts = new Set();
      const portCounts = {};

      records.forEach((record) => {
        const portsValue = param.getValue(record);
        if (portsValue && portsValue.toString().trim() !== '') {
          const recordPorts = portsValue
            .split(',')
            .map((port) => port.trim())
            .filter((port) => port !== '' && !Number.isNaN(Number(port)));

          recordPorts.forEach((port) => {
            allPorts.add(port);
            portCounts[port] = (portCounts[port] || 0) + 1;
          });
        }
      });

      values[param.key] = Array.from(allPorts).sort((a, b) => Number.parseInt(a, 10) - Number.parseInt(b, 10));
      counts[param.key] = portCounts;
      return;
    }

    const uniqueValues = [
      ...new Set(
        records
          .map((record) => param.getValue(record))
          .filter((value) => value && value.toString().trim() !== '')
      )
    ].sort();

    values[param.key] = uniqueValues;

    const valueCounts = {};
    uniqueValues.forEach((value) => {
      valueCounts[value] = records.filter((record) => param.getValue(record) === value).length;
    });
    counts[param.key] = valueCounts;
  });

  return {
    valuesByKey: values,
    countsByKey: counts
  };
};

const findSearchParameter = (name, searchParameters) =>
  searchParameters.find(
    (parameter) =>
      parameter.key === name.toLowerCase() ||
      (parameter.aliases && parameter.aliases.includes(name.toLowerCase()))
  );

export const analyzeSearchInput = (input, searchParameters) => {
  const trimmed = input.trim();

  const completePattern = /^(\w+)\s*=\s*(.+)$/;
  const fieldOnlyPattern = /^(\w+)\s*=\s*$/;
  const partialFieldPattern = /^(\w+)$/;

  const completeMatch = trimmed.match(completePattern);
  const fieldOnlyMatch = trimmed.match(fieldOnlyPattern);
  const partialMatch = trimmed.match(partialFieldPattern);

  if (completeMatch) {
    const [, fieldName, value] = completeMatch;
    const parameter = findSearchParameter(fieldName, searchParameters);
    return {
      type: 'complete',
      field: parameter?.key,
      value: value.trim(),
      hasWildcards: value.includes('*') || value.includes('?')
    };
  }

  if (fieldOnlyMatch) {
    const [, fieldName] = fieldOnlyMatch;
    const parameter = findSearchParameter(fieldName, searchParameters);
    return { type: 'field_ready', field: parameter?.key };
  }

  if (partialMatch && findSearchParameter(partialMatch[1], searchParameters)) {
    return { type: 'field_partial', field: findSearchParameter(partialMatch[1], searchParameters)?.key };
  }

  return { type: 'text' };
};

export const generateSearchSuggestions = (
  input,
  searchParameters,
  parameterValues,
  parameterCounts
) => {
  const analysis = analyzeSearchInput(input, searchParameters);

  if (analysis.type === 'field_ready' && analysis.field) {
    const values = parameterValues[analysis.field] || [];
    return values.map((value) => ({
      type: 'value',
      field: analysis.field,
      value,
      display: value,
      count: parameterCounts[analysis.field]?.[value] || 0
    }));
  }

  if (analysis.type === 'field_partial' || analysis.type === 'text') {
    const inputLower = input.toLowerCase();
    const suggestions = [];

    searchParameters.forEach((param) => {
      if (param.key.includes(inputLower) || param.label.toLowerCase().includes(inputLower)) {
        suggestions.push({
          type: 'field',
          field: param.key,
          display: `${param.key}=`,
          label: param.label,
          icon: param.icon,
          description: param.description
        });
      }

      if (param.aliases) {
        param.aliases.forEach((alias) => {
          if (alias.includes(inputLower)) {
            suggestions.push({
              type: 'field',
              field: param.key,
              display: `${alias}=`,
              label: `${param.label} (${alias})`,
              icon: param.icon,
              description: param.description
            });
          }
        });
      }
    });

    return suggestions;
  }

  return [];
};

export const matchesWildcard = (text, pattern) => {
  const textValue = `${text || ''}`;
  const patternValue = `${pattern || ''}`;

  if (!patternValue.includes('*') && !patternValue.includes('?')) {
    return textValue.toLowerCase().includes(patternValue.toLowerCase());
  }

  const regexPattern = patternValue
    .replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    .replace(/\\\*/g, '.*')
    .replace(/\\\?/g, '.');

  const regex = new RegExp(`^${regexPattern}$`, 'i');
  return regex.test(textValue);
};

export const filterRecords = (records, activeFilters, searchQuery, searchParameters) => {
  let filtered = [...records];

  activeFilters.forEach((filter) => {
    const parameter = searchParameters.find((entry) => entry.key === filter.parameter);
    if (!parameter) return;

    filtered = filtered.filter((record) => {
      const value = parameter.getValue(record);
      if (!value) return false;

      if (filter.parameter === 'ports') {
        const portList = value.split(',').map((port) => port.trim());
        return portList.some((port) => matchesWildcard(port, filter.value));
      }

      if (filter.parameter === 'created') {
        return value === filter.value;
      }

      return matchesWildcard(value, filter.value);
    });
  });

  if (searchQuery.trim()) {
    const query = searchQuery.toLowerCase();
    const hasWildcards = query.includes('*') || query.includes('?');

    filtered = filtered.filter((record) => {
      const searchFields = [
        record.name,
        record.ip_address,
        record.source,
        record.application_owner,
        record.maintainer,
        record.open_ports
      ];

      return searchFields.some((field) => {
        if (!field) return false;
        return hasWildcards
          ? matchesWildcard(field, query)
          : field.toLowerCase().includes(query);
      });
    });
  }

  return filtered;
};

export const createFilterFromAnalysis = (analysis, searchParameters) => {
  if (analysis.type !== 'complete' || !analysis.field || !analysis.value) return null;

  const parameter = searchParameters.find((entry) => entry.key === analysis.field);
  if (!parameter) return null;

  const filterLabel = analysis.hasWildcards
    ? `${parameter.label}: ${analysis.value} (wildcard)`
    : `${parameter.label}: ${analysis.value}`;

  return {
    id: Date.now(),
    parameter: analysis.field,
    value: analysis.value,
    label: filterLabel,
    hasWildcards: analysis.hasWildcards
  };
};

export const createFilterFromSelection = (parameter, value, searchParameters) => ({
  id: Date.now(),
  parameter,
  value,
  label: `${searchParameters.find((entry) => entry.key === parameter)?.label}: ${value}`
});

export const collectUnseenGroupKeys = (seen, keys) => keys.filter((key) => !seen.has(key));

export const calculateRecordStats = (recordsData) => {
  const uniqueSources = new Set(recordsData.map((record) => record.source)).size;
  return {
    total: recordsData.length,
    active: recordsData.filter((record) => record.status === 'unchanged').length,
    updated: recordsData.filter((record) => record.status === 'updated').length,
    missing: recordsData.filter((record) => record.status === 'missing').length,
    conflicts: recordsData.filter((record) => record.sync_conflict).length,
    prod: recordsData.filter((record) => isEmphasisedEnv(record.environment_slug)).length,
    sources: uniqueSources
  };
};

export const summarizeGroup = (records) => {
  const sources = [...new Set(records.map((record) => record.source).filter(Boolean))];
  const prod = records.filter((record) => isEmphasisedEnv(record.environment_slug)).length;
  return {
    hosts: records.length,
    prod,
    other: records.length - prod,
    missing: records.filter((record) => record.status === 'missing').length,
    conflicts: records.filter((record) => record.sync_conflict).length,
    sources,
    manualCount: records.filter((record) => record.origin === 'manual').length
  };
};

export const buildAppGroups = (records) => {
  const grouped = new Map();

  records.forEach((record) => {
    const appKey = record.application_id ? `app-${record.application_id}` : 'unassigned';
    const appName = record.application_name || 'Unassigned';
    if (!grouped.has(appKey)) {
      grouped.set(appKey, { key: appKey, name: appName, records: [] });
    }
    grouped.get(appKey).records.push(record);
  });

  return Array.from(grouped.values())
    .map((group) => ({ ...group, ...summarizeGroup(group.records) }))
    .sort((left, right) => {
      if (left.key === 'unassigned') return 1;
      if (right.key === 'unassigned') return -1;
      if (right.missing !== left.missing) return right.missing - left.missing;
      if (right.conflicts !== left.conflicts) return right.conflicts - left.conflicts;
      if (right.hosts !== left.hosts) return right.hosts - left.hosts;
      return left.name.localeCompare(right.name);
    });
};

export const firstPorts = (value) => {
  const ports = String(value || '')
    .split(',')
    .map((port) => port.trim())
    .filter(Boolean);
  if (ports.length === 0) return { label: '—', title: '' };
  if (ports.length <= 2) return { label: ports.join(', '), title: ports.join(', ') };
  return { label: `${ports.slice(0, 2).join(', ')} +${ports.length - 2}`, title: ports.join(', ') };
};

export const formatDateTime = (datetime) => {
  if (!datetime) return 'Never';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(datetime));
};

export const formatDateTimeFull = (datetime) => {
  if (!datetime) return '—';
  return new Intl.DateTimeFormat('en-GB', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(new Date(datetime));
};

export const historyFieldDiffs = (item) =>
  [
    { key: 'ip', label: 'IP', old: item.old_ip_address, next: item.new_ip_address, mono: true },
    { key: 'source', label: 'Source', old: item.old_source, next: item.new_source, mono: false },
    { key: 'maintainer', label: 'Maintainer', old: item.old_maintainer, next: item.new_maintainer, mono: false }
  ].filter((field) => (field.old || '') !== (field.next || ''));

export const buildRecordsCsv = (records) => Papa.unparse(records);

export const downloadCsvFile = (csv, filename) => {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};
