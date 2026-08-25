import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Surface, Text } from '../../../../design/primitives';
import { SPACE, TYPE } from '../../../../design/tokens';
import { TRANSITION, panelVariants } from '../../../../design/motion';
import { usePalette } from '../../../../design/usePalette';
import { REPORT_TEMPLATE_VARIABLE_GROUPS } from '../../report-template-utils';

const VariablePicker = ({ open, onSelect }) => {
  const palette = usePalette();
  const [groupKey, setGroupKey] = useState(null);

  useEffect(() => {
    if (!open) setGroupKey(null);
  }, [open]);

  const group = REPORT_TEMPLATE_VARIABLE_GROUPS.find((item) => item.key === groupKey);

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          key="variable-picker"
          variants={panelVariants}
          initial="initial"
          animate="animate"
          exit="exit"
          style={{ position: 'absolute', right: 0, top: '100%', zIndex: 8, width: 280, marginTop: 4 }}
        >
          <Surface raised style={{ overflow: 'hidden', padding: SPACE.x8 }}>
            <AnimatePresence mode="wait" initial={false}>
              {!group ? (
                <motion.div
                  key="categories"
                  initial={{ x: -16, opacity: 0 }}
                  animate={{ x: 0, opacity: 1, transition: TRANSITION.enter }}
                  exit={{ x: -16, opacity: 0, transition: TRANSITION.exit }}
                >
                  <Text as="div" variant="micro" tone="tertiary" style={{ marginBottom: 8 }}>
                    Category
                  </Text>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {REPORT_TEMPLATE_VARIABLE_GROUPS.map((item) => (
                      <button
                        key={item.key}
                        type="button"
                        onClick={() => setGroupKey(item.key)}
                        style={{
                          ...TYPE.body,
                          textAlign: 'left',
                          padding: '8px 10px',
                          border: `1px solid ${palette.line}`,
                          background: palette.surface,
                          color: palette.text,
                          cursor: 'pointer'
                        }}
                      >
                        {item.label}
                      </button>
                    ))}
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key={group.key}
                  initial={{ x: 16, opacity: 0 }}
                  animate={{ x: 0, opacity: 1, transition: TRANSITION.enter }}
                  exit={{ x: 16, opacity: 0, transition: TRANSITION.exit }}
                >
                  <button
                    type="button"
                    onClick={() => setGroupKey(null)}
                    style={{
                      ...TYPE.micro,
                      border: 0,
                      background: 'transparent',
                      color: palette.accent,
                      cursor: 'pointer',
                      padding: 0,
                      marginBottom: 8
                    }}
                  >
                    ← Categories
                  </button>
                  <Text as="div" variant="micro" tone="tertiary" style={{ marginBottom: 8 }}>
                    {group.label}
                  </Text>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 240, overflowY: 'auto' }}>
                    {group.variables.map((item) => (
                      <button
                        key={item.token}
                        type="button"
                        onClick={() => onSelect(item.token)}
                        style={{
                          ...TYPE.body,
                          textAlign: 'left',
                          padding: '8px 10px',
                          border: `1px solid ${palette.line}`,
                          background: palette.surface,
                          color: palette.text,
                          cursor: 'pointer'
                        }}
                      >
                        {item.label}
                        <div style={{ ...TYPE.micro, color: palette.textTertiary, marginTop: 2 }}>{item.token}</div>
                      </button>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </Surface>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
};

export default VariablePicker;
