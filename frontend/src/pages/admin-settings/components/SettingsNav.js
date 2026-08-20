import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Text } from '../../../design/primitives';
import { FONTS, RADIUS, SPACE } from '../../../design/tokens';
import { disclosureVariants } from '../../../design/motion';
import { usePalette } from '../../../design/usePalette';
import { USER_SUBSECTIONS, AI_SCANNER_SUBSECTIONS } from '../constants';

const NavButton = ({ selected, nested = false, onClick, children }) => {
  const palette = usePalette();
  const [hovered, setHovered] = useState(false);

  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      aria-current={selected ? 'page' : undefined}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        border: 0,
        borderRadius: RADIUS.base,
        padding: nested ? '6px 10px' : '8px 10px',
        marginBottom: 2,
        background: selected ? palette.accentFill : hovered ? palette.hover : 'transparent',
        color: selected ? palette.accent : palette.text,
        cursor: 'pointer',
        fontFamily: FONTS.sans,
        fontSize: nested ? 12 : 13,
        fontWeight: selected ? 500 : 400,
        lineHeight: '20px'
      }}
    >
      {children}
    </button>
  );
};

const SettingsNav = ({
  sections,
  selectedSection,
  onSelectSection,
  userManagementPage,
  onSelectUserManagementPage,
  domainManagementPage,
  onSelectDomainManagementPage,
  domainTabs = [],
  aiScannerPage,
  onSelectAiScannerPage = () => {},
  reportTemplates,
  selectedReportTemplateId,
  onCreateReportTemplate,
  onSelectReportTemplate
}) => {
  const [usersOpen, setUsersOpen] = useState(selectedSection === 'users');
  const [domainsOpen, setDomainsOpen] = useState(selectedSection === 'domains');
  const [aiOpen, setAiOpen] = useState(selectedSection === 'ai-scanner');
  const [reportTemplatesOpen, setReportTemplatesOpen] = useState(
    selectedSection === 'report-templates'
  );

  useEffect(() => {
    if (selectedSection === 'users') setUsersOpen(true);
  }, [selectedSection]);

  useEffect(() => {
    if (selectedSection === 'domains') setDomainsOpen(true);
  }, [selectedSection]);

  useEffect(() => {
    if (selectedSection === 'ai-scanner') setAiOpen(true);
  }, [selectedSection]);

  useEffect(() => {
    if (selectedSection === 'report-templates') setReportTemplatesOpen(true);
  }, [selectedSection]);

  const toggleOrSelect = (key, isOpen, setOpen) => {
    if (selectedSection !== key) {
      onSelectSection(key);
      setOpen(true);
      return;
    }
    setOpen(!isOpen);
  };

  return (
    <div>
      {sections.map((section) => {
        const isUsers = section.key === 'users';
        const isDomains = section.key === 'domains';
        const isAi = section.key === 'ai-scanner';
        const isReports = section.key === 'report-templates';
        const selected = selectedSection === section.key;
        const nestedOpen = isUsers
          ? usersOpen
          : isDomains
            ? domainsOpen
            : isAi
              ? aiOpen
              : isReports
                ? reportTemplatesOpen
                : false;

        return (
          <div key={section.key}>
            <NavButton
              selected={selected}
              onClick={() => {
                if (isUsers) {
                  toggleOrSelect('users', usersOpen, setUsersOpen);
                  return;
                }
                if (isDomains) {
                  toggleOrSelect('domains', domainsOpen, setDomainsOpen);
                  return;
                }
                if (isAi) {
                  toggleOrSelect('ai-scanner', aiOpen, setAiOpen);
                  return;
                }
                if (isReports) {
                  toggleOrSelect('report-templates', reportTemplatesOpen, setReportTemplatesOpen);
                  return;
                }
                onSelectSection(section.key);
              }}
            >
              {section.label}
            </NavButton>

            {isUsers ? (
              <AnimatePresence initial={false}>
                {nestedOpen ? (
                  <motion.div
                    key="users-sub"
                    variants={disclosureVariants}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    style={{ overflow: 'hidden', paddingLeft: SPACE.x12 }}
                  >
                    {USER_SUBSECTIONS.map((sub) => (
                      <NavButton
                        key={sub.key}
                        nested
                        selected={selected && userManagementPage === sub.key}
                        onClick={() => {
                          onSelectUserManagementPage(sub.key);
                          onSelectSection('users');
                        }}
                      >
                        {sub.label}
                      </NavButton>
                    ))}
                  </motion.div>
                ) : null}
              </AnimatePresence>
            ) : null}

            {isDomains ? (
              <AnimatePresence initial={false}>
                {nestedOpen ? (
                  <motion.div
                    key="domains-sub"
                    variants={disclosureVariants}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    style={{ overflow: 'hidden', paddingLeft: SPACE.x12 }}
                  >
                    {domainTabs.map((sub) => (
                      <NavButton
                        key={sub.key}
                        nested
                        selected={selected && domainManagementPage === sub.key}
                        onClick={() => {
                          onSelectDomainManagementPage(sub.key);
                          onSelectSection('domains');
                        }}
                      >
                        {sub.label}
                      </NavButton>
                    ))}
                  </motion.div>
                ) : null}
              </AnimatePresence>
            ) : null}

            {isAi ? (
              <AnimatePresence initial={false}>
                {nestedOpen ? (
                  <motion.div
                    key="ai-sub"
                    variants={disclosureVariants}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    style={{ overflow: 'hidden', paddingLeft: SPACE.x12 }}
                  >
                    {AI_SCANNER_SUBSECTIONS.map((sub) => (
                      <NavButton
                        key={sub.key}
                        nested
                        selected={selected && aiScannerPage === sub.key}
                        onClick={() => {
                          onSelectAiScannerPage(sub.key);
                          onSelectSection('ai-scanner');
                        }}
                      >
                        {sub.label}
                      </NavButton>
                    ))}
                  </motion.div>
                ) : null}
              </AnimatePresence>
            ) : null}

            {isReports ? (
              <AnimatePresence initial={false}>
                {nestedOpen ? (
                  <motion.div
                    key="reports-sub"
                    variants={disclosureVariants}
                    initial="initial"
                    animate="animate"
                    exit="exit"
                    style={{ overflow: 'hidden', paddingLeft: SPACE.x12 }}
                  >
                    <NavButton
                      nested
                      selected={selected && !selectedReportTemplateId}
                      onClick={() => {
                        onCreateReportTemplate();
                        onSelectSection('report-templates');
                      }}
                    >
                      New Template
                    </NavButton>
                    {(reportTemplates || []).map((template) => (
                      <NavButton
                        key={template.id}
                        nested
                        selected={selected && selectedReportTemplateId === template.id}
                        onClick={() => {
                          onSelectReportTemplate(template);
                          onSelectSection('report-templates');
                        }}
                      >
                        <span style={{ display: 'block' }}>{template.name}</span>
                        {template.enabled ? null : (
                          <Text as="span" variant="micro" tone="tertiary">
                            Disabled
                          </Text>
                        )}
                      </NavButton>
                    ))}
                  </motion.div>
                ) : null}
              </AnimatePresence>
            ) : null}
          </div>
        );
      })}
    </div>
  );
};

export default SettingsNav;
