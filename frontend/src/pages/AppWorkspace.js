import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useMatch, useLocation, Link as RouterLink, useNavigate } from 'react-router-dom';
import { Alert, Tooltip } from '@mui/material';
import { ArrowBack, Description, GppGood } from '@mui/icons-material';
import {
  Button,
  EnvTag,
  MetricStrip,
  Page,
  PageHeader,
  Progress,
  Tabs,
  Tag,
  Toast
} from '../design/primitives';
import ExportSheetDialog from './app-workspace/components/ExportSheetDialog';
import FindingsDashboardTab, { waveCoversEnv } from './app-workspace/components/FindingsDashboardTab';
import HostsTab from './app-workspace/components/HostsTab';
import EnvironmentsTab from './app-workspace/components/EnvironmentsTab';
import EnvironmentSettingsTab from './app-workspace/components/EnvironmentSettingsTab';
import WavesTab from './app-workspace/components/WavesTab';
import WaveDetailTab from './app-workspace/components/WaveDetailTab';
import FindingPage from './app-workspace/components/FindingPage';
import ProgramTab from './app-workspace/components/ProgramTab';
import OverviewTab from './app-workspace/components/OverviewTab';
import NewFindingDialog from './app-workspace/components/NewFindingDialog';
import AttachHostsDialog from './app-workspace/components/AttachHostsDialog';
import MergeFindingsDialog from './app-workspace/components/MergeFindingsDialog';
import TicketDialog from './app-workspace/components/TicketDialog';
import ShareHostDialog from './app-workspace/components/ShareHostDialog';
import {
  addFindingOccurrences,
  assignHosts,
  closeWave,
  claimWaveHosts,
  createAppFinding,
  createDnsZone,
  createEnvironment,
  createWave,
  deleteDnsZone,
  deleteEnvironment,
  deleteWave,
  downloadReportExport,
  fetchPentestUsers,
  fetchReportTemplates,
  generateAppReport,
  generateEnvReport,
  getApp,
  getApps,
  getWave,
  listAppFindings,
  listAppHosts,
  listDnsZones,
  listSharedHosts,
  listWaves,
  mergeFindings,
  patchFinding,
  patchOccurrence,
  previewAppReport,
  promoteFinding,
  putWaveEnvironments,
  putWaveMembers,
  setWaveHostScope,
  shareHost,
  startWave,
  updateApp,
  updateEnvironment,
  verifyReportExport
} from './app-workspace/services';
import { hasPermission as hasRolePermission } from '../utils/permissions';
import { peekAppPreview, rememberAppPreview } from './app-workspace/appPreview';

const PAGE_SIZE = 25;
const usernamesFrom = (data) => {
  const list = Array.isArray(data) ? data : data?.users || data?.usernames || [];
  return list.map((item) => (typeof item === 'string' ? item : item?.username)).filter(Boolean);
};

const METADATA_KEYS = [
  'owner',
  'app_lead',
  'data_class',
  'roe_link',
  'cookie_domain',
  'idp',
  'token_audience'
];

const AppWorkspace = ({ userRole, userPermissions, username = '' }) => {
  const { appId, envId: paramEnvId, waveId: paramWaveId, findingId: paramFindingId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const envMatch = useMatch('/apps/:appId/envs/:envId');
  const waveMatch = useMatch('/apps/:appId/waves/:waveId');
  const findingMatch = useMatch('/apps/:appId/findings/:findingId');
  const envId = paramEnvId || envMatch?.params?.envId;
  const waveId = paramWaveId || waveMatch?.params?.waveId;
  const findingId = paramFindingId || findingMatch?.params?.findingId;
  const hasPermission = (permission) => hasRolePermission(userRole, userPermissions, permission);
  const canExport = hasPermission('export_pentests');
  const canModify = hasPermission('modify_pentests');
  const canManageApps = hasPermission('manage_apps');
  const canDeleteWave = ['admin', 'manager'].includes(String(userRole || '').toLowerCase());

  const [app, setApp] = useState(
    () => peekAppPreview(appId) || location.state?.app || null
  );
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(() => !peekAppPreview(appId) && !location.state?.app);
  const [refreshing, setRefreshing] = useState(false);
  const [toast, setToast] = useState({ open: false, message: '', severity: 'success' });

  const [findings, setFindings] = useState([]);
  const [findingTotal, setFindingTotal] = useState(0);
  const [busyFinding, setBusyFinding] = useState('');

  const [hosts, setHosts] = useState([]);
  const [hostTotal, setHostTotal] = useState(0);
  const [hostPage, setHostPage] = useState(1);
  const [hostSearch, setHostSearch] = useState('');
  const [envFilter, setEnvFilter] = useState('');

  const [waves, setWaves] = useState([]);
  const [zones, setZones] = useState([]);
  const [sharedHosts, setSharedHosts] = useState([]);
  const [otherApps, setOtherApps] = useState([]);
  const [pentestUsers, setPentestUsers] = useState([]);
  const [reportTemplates, setReportTemplates] = useState([]);

  const [metadata, setMetadata] = useState({});
  const [metadataDirty, setMetadataDirty] = useState(false);

  const [exportOpen, setExportOpen] = useState(false);
  const [exportPackage, setExportPackage] = useState('owner_delivery');
  const [scopedWave, setScopedWave] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [lastExport, setLastExport] = useState(null);
  const [newFindingOpen, setNewFindingOpen] = useState(false);
  const [mergeTarget, setMergeTarget] = useState(null);
  const [ticketTarget, setTicketTarget] = useState(null);
  const [shareTarget, setShareTarget] = useState(null);
  const [attachTarget, setAttachTarget] = useState(null);
  const [waveDetail, setWaveDetail] = useState(null);
  const [hiddenEnvIds, setHiddenEnvIds] = useState([]);
  const pendingDeleteRef = useRef(null);

  const allEnvironments = useMemo(() => app?.environments || [], [app]);
  const environments = useMemo(
    () => allEnvironments.filter((env) => !hiddenEnvIds.includes(env.id)),
    [allEnvironments, hiddenEnvIds]
  );
  const activeEnv = useMemo(
    () => (envId ? environments.find((env) => String(env.id) === String(envId)) : null),
    [envId, environments]
  );
  const prodEnvIds = useMemo(
    () =>
      environments
        .filter((env) => env.slug === 'prod' || (env.is_production && env.include_in_exec_report))
        .map((env) => env.id),
    [environments]
  );
  const defaultExportEnvIds = useMemo(
    () => (envId ? [Number(envId)] : prodEnvIds),
    [envId, prodEnvIds]
  );

  const notify = useCallback(
    (severity, message) => setToast({ open: true, message, severity }),
    []
  );

  useEffect(() => {
    if (!toast.open) return undefined;
    const handle = window.setTimeout(
      () => setToast((prev) => ({ ...prev, open: false })),
      toast.duration || 4000
    );
    return () => window.clearTimeout(handle);
  }, [toast.open, toast.message, toast.duration]);

  useEffect(() => {
    if (!lastExport) return undefined;
    const handle = window.setTimeout(() => setLastExport(null), 10000);
    return () => window.clearTimeout(handle);
  }, [lastExport]);

  const failWith = useCallback(
    (error, fallback) => notify('error', error?.response?.data?.error || fallback),
    [notify]
  );

  const loadApp = useCallback(async () => {
    const response = await getApp(appId);
    setApp(response.data);
    rememberAppPreview(response.data);
    setMetadata(
      METADATA_KEYS.reduce((acc, key) => ({ ...acc, [key]: response.data[key] || '' }), {})
    );
    setMetadataDirty(false);
  }, [appId]);

  const loadFindings = useCallback(async () => {
    const params = {
      limit: 200,
      offset: 0,
      include_drafts: 1
    };
    if (envId) params.env_id = envId;
    const response = await listAppFindings(appId, params);
    setFindings(response.data.findings || []);
    setFindingTotal(response.data.total || 0);
  }, [appId, envId]);

  const loadHosts = useCallback(async () => {
    const params = { limit: PAGE_SIZE, offset: (hostPage - 1) * PAGE_SIZE };
    const scopedEnv = envId || envFilter;
    if (scopedEnv) params.env_id = scopedEnv;
    if (hostSearch.trim()) params.q = hostSearch.trim();
    const response = await listAppHosts(appId, params);
    setHosts(response.data.hosts || []);
    setHostTotal(response.data.total || 0);
  }, [appId, envId, envFilter, hostPage, hostSearch]);

  const loadProgram = useCallback(async () => {
    const [waveRes, zoneRes, sharedRes, appsRes, usersRes, templatesRes] = await Promise.all([
      listWaves(appId),
      listDnsZones(appId),
      listSharedHosts(appId),
      getApps(),
      fetchPentestUsers().catch(() => ({ data: [] })),
      fetchReportTemplates().catch(() => ({ data: { templates: [] } }))
    ]);
    setWaves(waveRes.data.waves || []);
    setZones(zoneRes.data.zones || []);
    setSharedHosts(sharedRes.data.hosts || []);
    const apps = Array.isArray(appsRes.data) ? appsRes.data : [];
    setOtherApps(apps.filter((item) => String(item.id) !== String(appId)));
    setPentestUsers(usernamesFrom(usersRes.data));
    setReportTemplates(templatesRes.data.templates || []);
  }, [appId]);

  const loadWave = useCallback(async () => {
    if (!waveId) {
      setWaveDetail(null);
      return;
    }
    const response = await getWave(appId, waveId);
    setWaveDetail(response.data);
  }, [appId, waveId]);

  const reloadAll = useCallback(async () => {
    setRefreshing(true);
    try {
      await Promise.all([loadApp(), loadFindings(), loadHosts(), loadProgram(), loadWave()]);
    } catch (error) {
      failWith(error, 'Failed to load application workspace.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [loadApp, loadFindings, loadHosts, loadProgram, loadWave, failWith]);

  const lastAppId = useRef(appId);

  useEffect(() => {
    const appChanged = lastAppId.current !== appId;
    lastAppId.current = appId;
    if (appChanged) {
      const preview = peekAppPreview(appId) || location.state?.app || null;
      setApp(preview);
      setLoading(!preview);
    }
    reloadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [appId, envId, waveId, findingId]);

  useEffect(() => {
    if (location.state?.tab && !waveId && !findingId && !envId) {
      setActiveTab(location.state.tab);
    }
  }, [location.state, waveId, findingId, envId]);

  useEffect(() => {
    if (loading) return;
    const handle = setTimeout(() => {
      loadHosts().catch((error) => failWith(error, 'Failed to load hosts.'));
    }, 250);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hostPage, hostSearch, envFilter]);

  useEffect(() => {
    if (envId && activeTab === 'environments') setActiveTab('env-settings');
    if (!envId && activeTab === 'env-settings') setActiveTab('environments');
    if (envId && activeTab === 'program') setActiveTab('overview');
  }, [envId, activeTab]);

  const envWaves = useMemo(
    () => (envId ? waves.filter((wave) => waveCoversEnv(wave, envId)) : waves),
    [waves, envId]
  );

  const stats = useMemo(() => {
    const scopeEnvs = activeEnv ? [activeEnv] : environments;
    const hostCount = scopeEnvs.reduce((sum, env) => sum + Number(env.host_count || 0), 0);
    const scopedOccurrences = (finding) =>
      envId
        ? (finding.occurrences || []).filter((occ) => String(occ.environment_id) === String(envId))
        : finding.occurrences || [];
    const openFindings = envId
      ? findingTotal
      : Number(app?.open_finding_count || findings.filter((finding) =>
          ['open', 'draft', 'retest'].includes(String(finding.status || '').toLowerCase())
        ).length);
    const drafts = findings.filter((finding) => finding.status === 'draft').length;
    const occurrences = findings.reduce((sum, finding) => sum + scopedOccurrences(finding).length, 0);
    const closedOccurrences = findings.reduce(
      (sum, finding) =>
        sum +
        scopedOccurrences(finding).filter((occ) =>
          ['fixed', 'not_affected', 'accepted'].includes(String(occ.status || '').toLowerCase())
        ).length,
      0
    );
    return {
      hostCount,
      openFindings,
      drafts,
      occurrences,
      closedOccurrences,
      remediationPct: occurrences > 0 ? Math.round((closedOccurrences / occurrences) * 100) : 0
    };
  }, [activeEnv, environments, findings, findingTotal, envId, app]);

  const metricItems = useMemo(
    () => [
      {
        key: 'open-findings',
        label: 'Open findings',
        value: stats.openFindings,
        hint: stats.drafts > 0 ? `${stats.drafts} scanner draft(s) waiting` : 'Nothing awaiting triage',
        onClick: () => setActiveTab('findings')
      },
      {
        key: 'blast-radius',
        label: 'Blast radius',
        value: stats.occurrences,
        hint: `across ${findingTotal || findings.length} finding${(findingTotal || findings.length) === 1 ? '' : 's'}`,
        onClick: () => setActiveTab('findings')
      },
      {
        key: 'remediation',
        label: 'Remediation',
        value: `${stats.closedOccurrences}/${stats.occurrences}`,
        hint: `${stats.remediationPct}% of occurrences closed`
      },
      {
        key: 'hosts',
        label: 'Hosts',
        value: stats.hostCount,
        hint: 'Filed into environments',
        onClick: () => setActiveTab('hosts')
      }
    ],
    [stats, findings.length, findingTotal]
  );

  const handleOccurrenceStatus = async (findingId, recordId, status) => {
    setBusyFinding(findingId);
    try {
      const response = await patchOccurrence(findingId, recordId, { status });
      const updated = response.data.finding;
      setFindings((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      if (waveId) await loadWave();
      notify('success', 'Occurrence status updated.');
    } catch (error) {
      failWith(error, 'Failed to update occurrence.');
    } finally {
      setBusyFinding('');
    }
  };

  const handleCreateFinding = async (form) => {
    try {
      const response = await createAppFinding(appId, {
        title: form.title,
        description: form.description,
        impact: form.impact,
        evidence: form.evidence,
        remediation: form.remediation,
        record_id: Number(form.record_id),
        record_ids: (form.record_ids || []).filter((id) => String(id) !== String(form.record_id)),
        auth_context: form.auth_context,
        ticket_url: form.ticket_url,
        wave_id: form.wave_id || waveId || undefined
      });
      setNewFindingOpen(false);
      await loadFindings();
      if (waveId) await loadWave();
      const createdId = response.data.finding?.id;
      notify('success', 'Finding created.');
      if (createdId) navigate(`/apps/${appId}/findings/${createdId}`);
    } catch (error) {
      failWith(error, 'Failed to create finding.');
    }
  };

  const handleMerge = async (loserId) => {
    try {
      await mergeFindings(mergeTarget.id, { loser_id: loserId });
      setMergeTarget(null);
      await loadFindings();
      notify('success', 'Findings merged.');
    } catch (error) {
      failWith(error, 'Failed to merge findings.');
    }
  };

  const handleSaveTicket = async (ticketUrl) => {
    try {
      await patchFinding(ticketTarget.id, { ticket_url: ticketUrl });
      setTicketTarget(null);
      await loadFindings();
      notify('success', 'Ticket link saved.');
    } catch (error) {
      failWith(error, 'Failed to save ticket.');
    }
  };

  const handlePromote = async (finding) => {
    try {
      await promoteFinding(finding.id, {});
      await loadFindings();
      notify('success', 'Draft promoted to an open finding.');
    } catch (error) {
      failWith(error, 'Failed to promote draft.');
    }
  };

  const handleAttachHosts = (finding) => {
    setAttachTarget(finding);
  };

  const handleAttachHostsSave = async (recordIds) => {
    if (!attachTarget) return;
    try {
      await addFindingOccurrences(attachTarget.id, { record_ids: recordIds });
      setAttachTarget(null);
      await loadFindings();
      if (waveId) await loadWave();
      notify('success', `Attached ${recordIds.length} host(s).`);
    } catch (error) {
      failWith(error, 'Failed to attach hosts.');
    }
  };

  const handleBulkAssign = async (payload) => {
    const ids = payload.record_ids || [];
    if (ids.length === 0) return;
    try {
      // Scope-only changes must keep each host in its own environment, so group
      // by current environment instead of applying one target to everything.
      const groups = new Map();
      if (payload.environment_id) {
        groups.set(payload.environment_id, ids);
      } else {
        ids.forEach((id) => {
          const host = hosts.find((item) => item.id === id);
          const envKey = host?.environment_id || environments[0]?.id;
          if (!envKey) return;
          groups.set(envKey, [...(groups.get(envKey) || []), id]);
        });
      }
      if (groups.size === 0) {
        notify('error', 'No environment available to file these hosts into.');
        return;
      }
      await Promise.all(
        [...groups.entries()].map(([environmentId, recordIds]) => {
          const body = { record_ids: recordIds, environment_id: environmentId };
          if (typeof payload.in_scope === 'boolean') body.in_scope = payload.in_scope;
          return assignHosts(appId, body);
        })
      );
      await Promise.all([loadHosts(), loadApp()]);
      notify('success', `Updated ${ids.length} host(s).`);
    } catch (error) {
      failWith(error, 'Failed to update hosts.');
    }
  };

  const handleLaunchScan = () => {
    if (!waveId) return;
    navigate(`/apps/${appId}/waves/${waveId}/scan-live`);
  };

  const handleRestartScan = () => {
    if (!waveId) return;
    navigate(`/apps/${appId}/waves/${waveId}/scan-live`);
  };

  const handleShare = async (consumerAppId) => {
    try {
      await shareHost(appId, shareTarget.id, { consumer_application_id: consumerAppId });
      setShareTarget(null);
      notify('success', 'Host shared. The consumer can attach it as an occurrence only.');
    } catch (error) {
      failWith(error, 'Failed to share host.');
    }
  };

  const handleSaveMetadata = async () => {
    try {
      await updateApp(appId, { name: app.name, ...metadata });
      await loadApp();
      notify('success', 'Application metadata saved.');
    } catch (error) {
      failWith(error, 'Failed to save metadata.');
    }
  };

  const handleSaveEnvironment = async (form) => {
    const env = activeEnv || waveDetail?.environment;
    if (!env) return;
    try {
      await updateEnvironment(appId, env.id, form);
      await loadApp();
      if (waveId) await loadWave();
      notify('success', 'Environment saved.');
    } catch (error) {
      failWith(error, 'Failed to save environment.');
    }
  };

  const handleCreateEnvironment = async (form) => {
    try {
      await createEnvironment(appId, form);
      await loadApp();
      notify('success', 'Environment created.');
    } catch (error) {
      failWith(error, 'Failed to create environment.');
    }
  };

  const commitPendingDelete = useCallback(
    async (env) => {
      try {
        await deleteEnvironment(appId, env.id);
        setHiddenEnvIds((ids) => ids.filter((id) => id !== env.id));
        await loadApp();
      } catch (error) {
        setHiddenEnvIds((ids) => ids.filter((id) => id !== env.id));
        failWith(error, 'Failed to delete environment. Move or unfile its hosts first.');
      }
    },
    [appId, failWith, loadApp]
  );

  const revertPendingDelete = useCallback(() => {
    const pending = pendingDeleteRef.current;
    if (!pending) return;
    window.clearTimeout(pending.timeoutId);
    pendingDeleteRef.current = null;
    setHiddenEnvIds((ids) => ids.filter((id) => id !== pending.env.id));
    setToast({ open: false, message: '', severity: 'success' });
  }, []);

  const handleDeleteEnvironment = useCallback(
    (env) => {
      if (pendingDeleteRef.current) {
        const previous = pendingDeleteRef.current;
        window.clearTimeout(previous.timeoutId);
        pendingDeleteRef.current = null;
        commitPendingDelete(previous.env);
      }
      setHiddenEnvIds((ids) => (ids.includes(env.id) ? ids : [...ids, env.id]));
      const timeoutId = window.setTimeout(() => {
        pendingDeleteRef.current = null;
        setToast((prev) => ({ ...prev, open: false }));
        commitPendingDelete(env);
      }, 5000);
      pendingDeleteRef.current = { env, timeoutId };
      setToast({
        open: true,
        message: `${env.display_name} deleted.`,
        severity: 'success',
        actionLabel: 'Revert',
        duration: 5000
      });
    },
    [commitPendingDelete]
  );

  const handleCreateWave = async (form) => {
    try {
      const response = await createWave(appId, form);
      await loadProgram();
      notify('success', 'Wave opened. Live hosts from those environments are on the wave.');
      const createdId = response.data.wave?.id;
      if (createdId) navigate(`/apps/${appId}/waves/${createdId}`);
    } catch (error) {
      failWith(error, 'Failed to open wave.');
    }
  };

  const handleSaveWaveMembers = async (usernames) => {
    if (!waveId) return;
    try {
      const response = await putWaveMembers(appId, waveId, { usernames });
      setWaveDetail((prev) =>
        prev
          ? {
              ...prev,
              wave: { ...prev.wave, members: response.data.members },
              members: response.data.members
            }
          : prev
      );
      notify('success', 'Wave testers saved. They now collaborate on every host in this wave.');
    } catch (error) {
      failWith(error, 'Failed to save wave members.');
    }
  };

  const handleClaimWaveHost = async (host) => {
    if (!waveId || !host?.id) return;
    try {
      await claimWaveHosts(appId, waveId, { record_ids: [host.id] });
      await loadWave();
      notify('success', `Assigned ${host.name} to you.`);
    } catch (error) {
      failWith(error, 'Failed to assign this host.');
    }
  };

  const handleStartWave = async (targetId) => {
    try {
      await startWave(appId, targetId);
      await loadProgram();
      if (waveId) await loadWave();
      notify('success', 'Wave started. Hosts on this engagement are now In Progress.');
    } catch (error) {
      failWith(error, 'Failed to start wave.');
    }
  };

  const handleDeleteWave = async (targetId) => {
    try {
      await deleteWave(appId, targetId);
      await loadProgram();
      notify('success', 'Wave deleted. Findings were kept.');
      if (String(waveId) === String(targetId)) navigate(`/apps/${appId}`, { state: { tab: 'waves' } });
    } catch (error) {
      failWith(error, 'Failed to delete wave.');
    }
  };

  const handleSaveWaveEnvironments = async (envIds) => {
    if (!waveId) return;
    try {
      const response = await putWaveEnvironments(appId, waveId, { env_ids: envIds });
      setWaveDetail((prev) =>
        prev
          ? {
              ...prev,
              wave: response.data.wave,
              environments: prev.environments
            }
          : prev
      );
      await loadWave();
      notify('success', 'Wave environments updated. Live hosts now follow those environments.');
    } catch (error) {
      failWith(error, 'Failed to update wave environments.');
    }
  };

  const handleSetWaveHostScope = async ({ record_ids, in_scope }) => {
    if (!waveId) return;
    try {
      await setWaveHostScope(appId, waveId, { record_ids, in_scope });
      await loadWave();
      notify('success', in_scope ? 'Marked in scope for this wave.' : 'Marked out of scope for this wave.');
    } catch (error) {
      failWith(error, 'Failed to update wave scope.');
    }
  };

  const handleAddHosts = async ({ record_ids, environment_id }) => {
    await handleBulkAssign({ record_ids, environment_id });
  };

  const handleCreateZone = async (payload) => {
    try {
      await createDnsZone({ ...payload, application_id: Number(appId) });
      await loadProgram();
      notify('success', 'Zone added to the catalog.');
    } catch (error) {
      failWith(error, 'Failed to add zone.');
    }
  };

  const handleDeleteZone = async (zoneId) => {
    try {
      await deleteDnsZone(zoneId);
      await loadProgram();
      notify('success', 'Zone removed.');
    } catch (error) {
      failWith(error, 'Failed to remove zone.');
    }
  };

  const closeExportSheet = () => {
    setExportOpen(false);
    setScopedWave(null);
  };

  const openExport = (packageKey = 'owner_delivery') => {
    setScopedWave(null);
    setExportPackage(packageKey);
    setLastExport(null);
    setExportOpen(true);
  };

  const openExportWave = (wave) => {
    if (!wave) return;
    setScopedWave(wave);
    setExportPackage('wave_archive');
    setLastExport(null);
    setExportOpen(true);
  };

  const handleEndWave = async (waveOrId) => {
    const targetId = typeof waveOrId === 'object' ? waveOrId?.id : waveOrId;
    if (!targetId) return;
    try {
      await closeWave(appId, targetId);
      await loadProgram();
      if (waveId) await loadWave();
      notify('success', 'Wave ended. The engagement is frozen.');
    } catch (error) {
      failWith(error, 'Failed to end wave.');
    }
  };

  const handlePreview = (payload) =>
    previewAppReport(
      appId,
      envId && !payload?.wave_id ? { ...payload, selected_env_ids: [Number(envId)] } : payload
    );

  const handleGenerate = async (payload) => {
    setGenerating(true);
    try {
      const response =
        envId && !payload?.wave_id
          ? await generateEnvReport(appId, envId, payload)
          : await generateAppReport(appId, payload);
      const exportId = response.data.export_id;
      let verified = null;
      if (exportId) {
        try {
          const verifyResponse = await verifyReportExport(exportId);
          verified = verifyResponse.data.valid;
        } catch (error) {
          verified = null;
        }
        const file = await downloadReportExport(exportId);
        const url = window.URL.createObjectURL(file.data);
        const link = document.createElement('a');
        link.href = url;
        link.download = `raptor-${payload.package || 'owner-delivery'}-${exportId}.pdf`;
        link.click();
        window.URL.revokeObjectURL(url);
      }
      setLastExport({
        exportId,
        package: response.data.package,
        findingCount: response.data.finding_count,
        watermark: response.data.watermark,
        verified
      });
      notify('success', 'Export frozen, signed, and downloaded.');
      closeExportSheet();
    } catch (error) {
      failWith(error, 'Failed to generate report.');
    } finally {
      setGenerating(false);
    }
  };

  if (loading && !app) {
    return (
      <Page>
        <PageHeader
          crumbs={[{ label: 'Applications', to: '/pentest' }]}
          leading={
            <Button size="small" component={RouterLink} to="/pentest" startIcon={<ArrowBack sx={{ fontSize: 16 }} />}>
              Dashboard
            </Button>
          }
          title="Application"
          subtitle="Loading workspace…"
        />
        <Progress deferred />
      </Page>
    );
  }

  if (!app) {
    return (
      <Page>
        <Alert severity="error">Application not found.</Alert>
      </Page>
    );
  }

  const dialogs = (
    <>
      <NewFindingDialog
        open={newFindingOpen}
        appId={appId}
        sharedHosts={sharedHosts}
        envId={waveDetail?.environment?.id || waveDetail?.wave?.environment_id || envId}
        waveId={waveId}
        onClose={() => setNewFindingOpen(false)}
        onCreate={handleCreateFinding}
      />
      <AttachHostsDialog
        open={Boolean(attachTarget)}
        finding={attachTarget}
        appId={appId}
        sharedHosts={sharedHosts}
        onClose={() => setAttachTarget(null)}
        onSave={handleAttachHostsSave}
      />
      <MergeFindingsDialog
        open={Boolean(mergeTarget)}
        survivor={mergeTarget}
        findings={findings}
        onClose={() => setMergeTarget(null)}
        onMerge={handleMerge}
      />
      <TicketDialog
        open={Boolean(ticketTarget)}
        finding={ticketTarget}
        onClose={() => setTicketTarget(null)}
        onSave={handleSaveTicket}
      />
      <ShareHostDialog
        open={Boolean(shareTarget)}
        host={shareTarget}
        apps={otherApps}
        onClose={() => setShareTarget(null)}
        onShare={handleShare}
      />
      <ExportSheetDialog
        open={exportOpen}
        onClose={closeExportSheet}
        environments={environments}
        defaultEnvIds={defaultExportEnvIds}
        waves={waves}
        zones={zones}
        canExport={canExport}
        generating={generating}
        onGenerate={handleGenerate}
        onPreview={handlePreview}
        defaultPackage={exportPackage}
        scopedWave={scopedWave}
        templates={reportTemplates}
        scopeLabel={activeEnv ? `${app.name} · ${activeEnv.display_name}` : app.name}
      />
      <Toast
        open={toast.open}
        message={toast.message}
        severity={toast.severity}
        actionLabel={toast.actionLabel}
        onAction={toast.actionLabel === 'Revert' ? revertPendingDelete : undefined}
        onClose={() => setToast((prev) => ({ ...prev, open: false }))}
      />
    </>
  );

  if (findingId) {
    return (
      <>
        <FindingPage
          appId={appId}
          app={app}
          findingId={findingId}
          canModify={canModify}
          pentestUsers={pentestUsers}
          onAttachHosts={handleAttachHosts}
          onOpenTicket={setTicketTarget}
          onOpenMerge={setMergeTarget}
          onPromote={handlePromote}
          onOccurrenceStatusChange={handleOccurrenceStatus}
          busyFinding={busyFinding}
          failWith={failWith}
          notify={notify}
        />
        {dialogs}
      </>
    );
  }

  if (waveId) {
    return (
      <>
        <WaveDetailTab
          appId={appId}
          appName={app.name}
          wave={waveDetail?.wave}
          environments={environments}
          hosts={waveDetail?.hosts || []}
          findings={waveDetail?.findings || []}
          members={waveDetail?.members || waveDetail?.wave?.members || []}
          pentestUsers={pentestUsers}
          canModify={canModify}
          canExport={canExport}
          canCreateFinding={canModify}
          canDelete={canDeleteWave}
          busyFinding={busyFinding}
          onEndWave={handleEndWave}
          onExportWave={openExportWave}
          onStartWave={handleStartWave}
          onDeleteWave={handleDeleteWave}
          onOccurrenceStatusChange={handleOccurrenceStatus}
          onOpenTicket={setTicketTarget}
          onOpenMerge={setMergeTarget}
          onPromote={handlePromote}
          onAttachHosts={handleAttachHosts}
          onCreateFinding={() => setNewFindingOpen(true)}
          onSaveMembers={handleSaveWaveMembers}
          onSaveEnvironments={handleSaveWaveEnvironments}
          username={username}
          onClaimHost={handleClaimWaveHost}
          onSetHostScope={handleSetWaveHostScope}
          canLaunchScan={canModify}
          onLaunchScan={handleLaunchScan}
          onRestartScan={handleRestartScan}
          scanBusy={false}
        />
        {dialogs}
      </>
    );
  }

  const tabs = [
    { value: 'overview', label: 'Overview' },
    { value: 'findings', label: 'Findings' },
    { value: 'hosts', label: `Hosts${hostTotal ? ` (${hostTotal})` : ''}` },
    envId
      ? { value: 'env-settings', label: 'Environment settings' }
      : { value: 'environments', label: 'Environments' },
    { value: 'waves', label: `Waves (${envWaves.length})` },
    ...(envId ? [] : [{ value: 'program', label: 'Program' }])
  ];

  const crumbs = [
    { label: 'Applications', to: '/pentest' },
    ...(envId
      ? [{ label: app.name, to: `/apps/${appId}` }, { label: activeEnv?.display_name || 'Environment' }]
      : [{ label: app.name }])
  ];

  return (
    <Page>
      <PageHeader
        crumbs={crumbs}
        leading={
          envId ? (
            <Button size="small" component={RouterLink} to={`/apps/${appId}`} startIcon={<ArrowBack sx={{ fontSize: 16 }} />}>
              App overview
            </Button>
          ) : (
            <Button size="small" component={RouterLink} to="/pentest" startIcon={<ArrowBack sx={{ fontSize: 16 }} />}>
              Dashboard
            </Button>
          )
        }
        title={activeEnv ? activeEnv.display_name : app.name}
        subtitle={
          activeEnv
            ? 'Environment drill-down. Findings here are filtered to this environment. File new findings from a wave.'
            : 'Application workspace. File findings from a wave — that is the engagement. Export a signed pack from here when you are delivering to the owner.'
        }
        meta={
          activeEnv ? (
            <EnvTag slug={activeEnv.slug} label={activeEnv.slug} />
          ) : (
            <Tag>{`${environments.length} environments`}</Tag>
          )
        }
        actions={
          canExport ? (
            <Button variant="contained" startIcon={<Description />} onClick={() => openExport('owner_delivery')}>
              Export
            </Button>
          ) : null
        }
      />

      {refreshing ? <Progress deferred /> : null}

      {lastExport ? (
        <Alert
          severity={lastExport.verified === false ? 'warning' : 'success'}
          icon={<GppGood />}
          onClose={() => setLastExport(null)}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            Export #{lastExport.exportId} frozen — {lastExport.findingCount} finding(s), {lastExport.watermark}{' '}
            watermark.
            {lastExport.verified === true ? (
              <Tooltip title="HMAC-SHA256 of the content hash matches the server signature">
                <span>
                  <Tag emphasized>Signature valid</Tag>
                </span>
              </Tooltip>
            ) : lastExport.verified === false ? (
              <Tag>Signature mismatch</Tag>
            ) : null}
          </span>
        </Alert>
      ) : null}

      <MetricStrip items={metricItems} />

      <Tabs
        value={activeTab}
        onChange={setActiveTab}
        items={tabs}
      />

      {activeTab === 'overview' && (
        <OverviewTab
          appId={appId}
          envId={envId}
          environments={environments}
          findings={findings}
          waves={envWaves}
          onGoToTab={setActiveTab}
          onOpenWave={(wave) => navigate(`/apps/${appId}/waves/${wave.id}`)}
        />
      )}

      {activeTab === 'findings' && (
        <FindingsDashboardTab
          findings={findings}
          waves={envWaves}
          environments={environments}
          appId={appId}
          envId={envId}
        />
      )}

      {activeTab === 'hosts' && (
        <HostsTab
          hosts={hosts}
          total={hostTotal}
          page={hostPage}
          pageSize={PAGE_SIZE}
          onPageChange={setHostPage}
          loading={refreshing}
          search={hostSearch}
          onSearchChange={(value) => {
            setHostSearch(value);
            setHostPage(1);
          }}
          envFilter={envFilter}
          onEnvFilterChange={
            envId
              ? null
              : (value) => {
                  setEnvFilter(value);
                  setHostPage(1);
                }
          }
          environments={environments}
          canManage={canManageApps}
          onBulkAssign={handleBulkAssign}
          onShare={setShareTarget}
          onAddHosts={handleAddHosts}
        />
      )}

      {activeTab === 'environments' && (
        <EnvironmentsTab
          appId={appId}
          environments={environments}
          canManage={canManageApps}
          onCreate={handleCreateEnvironment}
          onDelete={handleDeleteEnvironment}
        />
      )}

      {activeTab === 'env-settings' && (
        <EnvironmentSettingsTab
          appId={appId}
          env={activeEnv}
          canManage={canManageApps}
          pentestUsers={pentestUsers}
          onSaveEnvironment={handleSaveEnvironment}
        />
      )}

      {activeTab === 'waves' && (
        <WavesTab
          waves={envWaves}
          environments={environments}
          canModify={canModify}
          canExport={canExport}
          canDelete={canDeleteWave}
          onCreate={handleCreateWave}
          onEnd={handleEndWave}
          onExport={openExportWave}
          onDelete={handleDeleteWave}
          onOpen={(wave) => navigate(`/apps/${appId}/waves/${wave.id}`)}
          pentestUsers={pentestUsers}
          environmentName={activeEnv?.display_name}
          defaultEnvIds={envId ? [Number(envId)] : []}
        />
      )}

      {activeTab === 'program' && (
        <ProgramTab
          metadata={metadata}
          onMetadataChange={(key, value) => {
            setMetadata((prev) => ({ ...prev, [key]: value }));
            setMetadataDirty(true);
          }}
          onSaveMetadata={handleSaveMetadata}
          metadataDirty={metadataDirty}
          zones={zones}
          onCreateZone={handleCreateZone}
          onDeleteZone={handleDeleteZone}
          sharedHosts={sharedHosts}
          canManage={canManageApps}
        />
      )}

      {dialogs}
    </Page>
  );
};

export default AppWorkspace;
