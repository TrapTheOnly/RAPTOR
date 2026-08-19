import React, { useEffect, useState } from 'react';
import { Alert } from '@mui/material';
import { AnimatePresence, LayoutGroup, motion } from 'motion/react';
import {
  Button,
  EnvTag,
  Field,
  Stepper,
  SwitchRow,
  Tag,
  Text
} from '../../../design/primitives';
import { FONTS, SPACE, TYPE } from '../../../design/tokens';
import { TRANSITION, disclosureVariants } from '../../../design/motion';
import { usePalette } from '../../../design/usePalette';

const emptyForm = {
  display_name: '',
  roe_text: '',
  contacts: '',
  data_class: '',
  test_window: '',
  creds_vault_pointer: '',
  include_in_exec_report: false,
  allow_destructive: false,
  max_concurrent_scans: 1
};

const Band = ({ eyebrow, hint, children, last = false }) => {
  const palette = usePalette();
  return (
    <section
      style={{
        paddingBottom: last ? 0 : SPACE.x32,
        marginBottom: last ? 0 : SPACE.x32,
        borderBottom: last ? 'none' : `1px solid ${palette.line}`
      }}
    >
      <div style={{ ...TYPE.eyebrow, color: palette.textTertiary, marginBottom: SPACE.x8 }}>{eyebrow}</div>
      {hint ? (
        <Text as="p" variant="meta" tone="secondary" style={{ margin: `0 0 ${SPACE.x16}px`, maxWidth: 560 }}>
          {hint}
        </Text>
      ) : null}
      {children}
    </section>
  );
};

const EnvironmentSettingsTab = ({ env, canManage, globalDestructiveEnabled, onSaveEnvironment }) => {
  const palette = usePalette();
  const [form, setForm] = useState(emptyForm);
  const [dirty, setDirty] = useState(false);
  const [ceilingError, setCeilingError] = useState('');

  useEffect(() => {
    if (!env) return;
    setForm({
      display_name: env.display_name || '',
      roe_text: env.roe_text || '',
      contacts: env.contacts || '',
      data_class: env.data_class || '',
      test_window: env.test_window || '',
      creds_vault_pointer: env.creds_vault_pointer || '',
      include_in_exec_report: Boolean(env.include_in_exec_report),
      allow_destructive: Boolean(env.allow_destructive),
      max_concurrent_scans: Number(env.max_concurrent_scans || 1)
    });
    setDirty(false);
    setCeilingError('');
  }, [env]);

  const update = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const save = () => {
    const ceiling = Number(form.max_concurrent_scans);
    if (!Number.isInteger(ceiling) || ceiling < 1 || ceiling > 10) {
      setCeilingError('Must be a whole number between 1 and 10.');
      return;
    }
    setCeilingError('');
    onSaveEnvironment(form);
    setDirty(false);
  };

  if (!env) return null;

  return (
    <LayoutGroup>
      <style>{`
        .raptor-env-settings {
          display: grid;
          grid-template-columns: minmax(0, 1fr) 320px;
          gap: 40px;
          align-items: start;
        }
        .raptor-env-facts {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
          gap: 20px 24px;
        }
        .raptor-env-rail {
          position: sticky;
          top: 64px;
          border-left: 1px solid var(--raptor-line);
          padding-left: 24px;
        }
        @media (max-width: 960px) {
          .raptor-env-settings { grid-template-columns: 1fr; }
          .raptor-env-rail {
            position: static;
            border-left: 0;
            padding-left: 0;
            border-top: 1px solid var(--raptor-line);
            padding-top: 32px;
          }
          .raptor-env-facts { grid-template-columns: 1fr; }
        }
      `}</style>
      <div className="raptor-env-settings">
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-end',
              justifyContent: 'space-between',
              gap: SPACE.x16,
              marginBottom: SPACE.x32,
              paddingBottom: SPACE.x16,
              borderBottom: `1px solid ${palette.line}`,
              position: 'relative'
            }}
          >
            <AnimatePresence initial={false}>
              {dirty ? (
                <motion.span
                  key="dirty-rail"
                  initial={{ opacity: 0, scaleY: 0.4 }}
                  animate={{ opacity: 1, scaleY: 1 }}
                  exit={{ opacity: 0, scaleY: 0.4 }}
                  transition={TRANSITION.enter}
                  style={{
                    position: 'absolute',
                    left: -SPACE.x16,
                    top: 4,
                    bottom: SPACE.x16,
                    width: 2,
                    background: palette.accent,
                    transformOrigin: 'top'
                  }}
                />
              ) : null}
            </AnimatePresence>

            <div style={{ display: 'flex', alignItems: 'center', gap: SPACE.x12, minWidth: 0, flex: 1 }}>
              <EnvTag slug={env.slug} label={env.slug} />
              <input
                value={form.display_name}
                disabled={!canManage}
                onChange={(event) => update('display_name', event.target.value)}
                aria-label="Display name"
                style={{
                  ...TYPE.h1,
                  border: 0,
                  background: 'transparent',
                  color: palette.text,
                  outline: 'none',
                  minWidth: 0,
                  width: '100%',
                  padding: 0,
                  fontFamily: FONTS.sans
                }}
              />
            </div>

            {canManage ? (
              <motion.div layout transition={TRANSITION.layout}>
                <Button variant={dirty ? 'contained' : 'outlined'} disabled={!dirty} onClick={save}>
                  <AnimatePresence mode="wait" initial={false}>
                    <motion.span
                      key={dirty ? 'save' : 'saved'}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      transition={TRANSITION.press}
                      style={{ display: 'inline-block' }}
                    >
                      {dirty ? 'Save changes' : 'Saved'}
                    </motion.span>
                  </AnimatePresence>
                </Button>
              </motion.div>
            ) : null}
          </div>

          <Band
            eyebrow="Rules of engagement"
            hint="Standing constraints for this environment. Every wave that includes it inherits this text. Owner packs never include it."
          >
            <textarea
              value={form.roe_text}
              disabled={!canManage}
              placeholder="Constraints, escalation path, prohibited techniques"
              onChange={(event) => update('roe_text', event.target.value)}
              aria-label="Rules of engagement"
              style={{
                width: '100%',
                minHeight: 220,
                resize: 'vertical',
                boxSizing: 'border-box',
                padding: SPACE.x16,
                background: palette.canvas,
                color: palette.text,
                border: `1px solid ${palette.lineStrong}`,
                borderRadius: 4,
                fontFamily: FONTS.sans,
                fontSize: 13,
                lineHeight: '22px',
                outline: 'none'
              }}
            />
          </Band>

          <Band eyebrow="Facts" last>
            <div className="raptor-env-facts">
              <Field
                label="Contacts"
                placeholder="Names, emails, or a distribution list"
                value={form.contacts}
                disabled={!canManage}
                onChange={(event) => update('contacts', event.target.value)}
              />
              <Field
                label="Data classification"
                placeholder="e.g. Confidential"
                value={form.data_class}
                disabled={!canManage}
                onChange={(event) => update('data_class', event.target.value)}
              />
              <Field
                label="Test window"
                placeholder="Weekdays 20:00–06:00 GST"
                value={form.test_window}
                disabled={!canManage}
                onChange={(event) => update('test_window', event.target.value)}
              />
              <Field
                label="Credentials vault pointer"
                placeholder="Path or URL — never paste a secret here"
                value={form.creds_vault_pointer}
                disabled={!canManage}
                onChange={(event) => update('creds_vault_pointer', event.target.value)}
              />
            </div>
          </Band>
        </div>

        <aside className="raptor-env-rail">
          <Band
            eyebrow="Scanner ceiling"
            hint="The environment is the job ceiling. Destructive tooling needs both the global scanner flag and this switch. Waves that include this environment inherit it."
          >
            <AnimatePresence initial={false}>
              {globalDestructiveEnabled === false && form.allow_destructive ? (
                <motion.div
                  key="ceiling-warning"
                  variants={disclosureVariants}
                  initial="initial"
                  animate="animate"
                  exit="exit"
                  style={{ overflow: 'hidden', marginBottom: SPACE.x12 }}
                >
                  <Alert severity="info">
                    Destructive tools are allowed here but disabled globally, so scans stay non-destructive until an
                    admin enables the global flag in Settings → AI Scanner.
                  </Alert>
                </motion.div>
              ) : null}
            </AnimatePresence>
            <SwitchRow
              label="Allow destructive tools"
              hint="Scanner payloads that can change state."
              checked={form.allow_destructive}
              disabled={!canManage}
              onChange={(value) => update('allow_destructive', value)}
            />
            <div style={{ marginTop: SPACE.x8 }}>
              <Stepper
                label="Max concurrent scans"
                value={form.max_concurrent_scans}
                min={1}
                max={10}
                disabled={!canManage}
                error={ceilingError}
                hint="Launches are refused once this many scans are running on hosts here."
                onChange={(value) => update('max_concurrent_scans', value)}
              />
            </div>
          </Band>

          <Band eyebrow="Export" last>
            <SwitchRow
              label="Pre-check on the export sheet"
              hint="Include this environment when generating an owner pack."
              checked={form.include_in_exec_report}
              disabled={!canManage}
              onChange={(value) => update('include_in_exec_report', value)}
            />
            {env.slug === 'prod' || env.is_production ? <Tag emphasized>prod default</Tag> : null}
          </Band>
        </aside>
      </div>
    </LayoutGroup>
  );
};

export default EnvironmentSettingsTab;
