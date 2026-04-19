import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Box,
  Breadcrumbs,
  Button,
  Divider,
  Grid,
  InputAdornment,
  Link,
  List,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography
} from '@mui/material';
import {
  ArrowBack,
  ArrowForward,
  Search as SearchIcon
} from '@mui/icons-material';

const buildDocPath = (sectionSlug, pageSlug) => `/docs/${sectionSlug}/${pageSlug}`;

const flattenPages = (sections) =>
  (sections || []).flatMap((section) =>
    (section.pages || []).map((page) => ({
      ...page,
      sectionSlug: section.slug,
      sectionTitle: section.title
    }))
  );

const renderInlineCode = (text) => {
  const chunks = String(text || '').split(/(`[^`]+`)/g);
  return chunks.map((chunk, index) => {
    if (chunk.startsWith('`') && chunk.endsWith('`')) {
      const codeText = chunk.slice(1, -1);
      return (
        <Box
          key={`${codeText}-${index}`}
          component="code"
          sx={{
            fontFamily: '"Fira Code", "Consolas", "Monaco", monospace',
            fontSize: '0.88em',
            backgroundColor: 'action.hover',
            border: 1,
            borderColor: 'divider',
            borderRadius: 1,
            px: 0.5,
            py: 0.1
          }}
        >
          {codeText}
        </Box>
      );
    }
    return <React.Fragment key={`text-${index}`}>{chunk}</React.Fragment>;
  });
};

const Admonition = ({ variant = 'tip', title, paragraphs = [] }) => {
  const isImportant = variant === 'important';
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        border: 1,
        borderColor: isImportant ? 'warning.main' : 'info.main',
        backgroundColor: isImportant ? 'warning.dark' : 'info.dark',
        mb: 2
      }}
    >
      <Typography
        component="p"
        variant="body2"
        sx={{
          fontWeight: 700,
          mb: 1,
          color: isImportant ? 'warning.contrastText' : 'info.contrastText'
        }}
      >
        {title}
      </Typography>
      {paragraphs.map((paragraph) => (
        <Typography
          key={paragraph}
          component="p"
          variant="body2"
          sx={{
            lineHeight: 1.7,
            mb: 1,
            color: isImportant ? 'warning.contrastText' : 'info.contrastText'
          }}
        >
          {renderInlineCode(paragraph)}
        </Typography>
      ))}
    </Paper>
  );
};

const SectionAnchorHeading = ({ id, title }) => (
  <Box id={id} sx={{ scrollMarginTop: 96, mt: 4 }}>
    <Typography
      component="h2"
      variant="h5"
      sx={{
        fontWeight: 600,
        fontSize: { xs: '1.35rem', md: '1.5rem' },
        mb: 1.25
      }}
    >
      <Link href={`#${id}`} underline="hover" color="inherit">
        {title}
      </Link>
    </Typography>
  </Box>
);

const formatDateTime = (isoString) => {
  if (!isoString) return '';
  const parsed = new Date(isoString);
  if (Number.isNaN(parsed.getTime())) {
    return String(isoString);
  }
  return parsed.toLocaleString();
};

const DocsAccessMatrix = ({
  matrix,
  loading,
  error,
  onNavigatePath
}) => {
  if (loading) {
    return (
      <Paper
        elevation={0}
        sx={{
          p: 2,
          border: 1,
          borderColor: 'divider',
          backgroundColor: 'action.hover',
          mb: 2
        }}
      >
        <Typography variant="body2" color="text.secondary">
          Loading access matrix...
        </Typography>
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper
        elevation={0}
        sx={{
          p: 2,
          border: 1,
          borderColor: 'error.main',
          backgroundColor: 'error.dark',
          mb: 2
        }}
      >
        <Typography variant="body2" color="error.contrastText">
          {error}
        </Typography>
      </Paper>
    );
  }

  if (!matrix || !Array.isArray(matrix.roles) || matrix.roles.length === 0) {
    return (
      <Paper
        elevation={0}
        sx={{
          p: 2,
          border: 1,
          borderColor: 'divider',
          backgroundColor: 'action.hover',
          mb: 2
        }}
      >
        <Typography variant="body2" color="text.secondary">
          Access matrix is not available.
        </Typography>
      </Paper>
    );
  }

  return (
    <Box sx={{ mb: 2 }}>
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
        Generated: {formatDateTime(matrix.generated_at)} | Total documented pages: {matrix.total_pages_in_manifest}
      </Typography>

      {matrix.roles.map((roleEntry) => (
        <Box key={roleEntry.role} sx={{ mb: 3 }}>
          <Typography
            component="h3"
            variant="h6"
            sx={{ fontWeight: 650, fontSize: { xs: '1rem', md: '1.1rem' }, mb: 1 }}
          >
            {roleEntry.role_label}
          </Typography>

          <TableContainer
            component={Paper}
            elevation={0}
            sx={{ border: 1, borderColor: 'divider', mb: 1.5 }}
          >
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600 }}>Scenario</TableCell>
                  <TableCell sx={{ fontWeight: 600 }}>Optional permissions included</TableCell>
                  <TableCell sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}>Visible pages</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(roleEntry.scenarios || []).map((scenario) => (
                  <TableRow key={scenario.key}>
                    <TableCell>{scenario.label}</TableCell>
                    <TableCell>
                      {(scenario.optional_permissions || []).length > 0
                        ? scenario.optional_permissions.join(', ')
                        : 'None'}
                    </TableCell>
                    <TableCell>{scenario.visible_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          <TableContainer
            component={Paper}
            elevation={0}
            sx={{ border: 1, borderColor: 'divider', mb: 1.5 }}
          >
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell sx={{ fontWeight: 600, minWidth: 300 }}>Page</TableCell>
                  {(roleEntry.scenarios || []).map((scenario) => (
                    <TableCell key={`${roleEntry.role}-${scenario.key}`} sx={{ fontWeight: 600 }}>
                      {scenario.label}
                    </TableCell>
                  ))}
                  <TableCell sx={{ fontWeight: 600, minWidth: 260 }}>Access rule</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(roleEntry.rows || []).map((row) => (
                  <TableRow key={`${roleEntry.role}-${row.path}`}>
                    <TableCell sx={{ verticalAlign: 'top' }}>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        <Link
                          underline="hover"
                          component="button"
                          onClick={() => onNavigatePath(row.path)}
                        >
                          {row.page_title}
                        </Link>
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {row.section_title}
                      </Typography>
                    </TableCell>
                    {(roleEntry.scenarios || []).map((scenario) => (
                      <TableCell
                        key={`${roleEntry.role}-${row.path}-${scenario.key}`}
                        sx={{ verticalAlign: 'top', whiteSpace: 'nowrap' }}
                      >
                        <Typography
                          variant="body2"
                          color={row.visibility?.[scenario.key] ? 'success.main' : 'text.secondary'}
                          sx={{ fontWeight: row.visibility?.[scenario.key] ? 600 : 400 }}
                        >
                          {row.visibility?.[scenario.key] ? 'Yes' : 'No'}
                        </Typography>
                      </TableCell>
                    ))}
                    <TableCell sx={{ verticalAlign: 'top', lineHeight: 1.6 }}>
                      {row.access_rule}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      ))}
    </Box>
  );
};

const DocumentationPortal = () => {
  const navigate = useNavigate();
  const { sectionSlug, pageSlug } = useParams();

  const [docsSections, setDocsSections] = useState([]);
  const [activePageData, setActivePageData] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [loadingManifest, setLoadingManifest] = useState(true);
  const [loadingPage, setLoadingPage] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [docsAccessMatrix, setDocsAccessMatrix] = useState(null);
  const [loadingAccessMatrix, setLoadingAccessMatrix] = useState(false);
  const [accessMatrixError, setAccessMatrixError] = useState('');

  useEffect(() => {
    let canceled = false;

    const fetchManifest = async () => {
      setLoadingManifest(true);
      setErrorMessage('');
      try {
        const response = await axios.get('/docs/manifest');
        const sections = response?.data?.sections || [];
        if (!canceled) {
          setDocsSections(Array.isArray(sections) ? sections : []);
        }
      } catch (error) {
        if (!canceled) {
          setDocsSections([]);
          if (error?.response?.status === 401) {
            setErrorMessage('Session expired. Please sign in again.');
          } else {
            setErrorMessage('Failed to load documentation.');
          }
        }
      } finally {
        if (!canceled) {
          setLoadingManifest(false);
        }
      }
    };

    fetchManifest();
    return () => {
      canceled = true;
    };
  }, []);

  const defaultRoute = useMemo(() => {
    const firstSection = docsSections.find(
      (section) => Array.isArray(section.pages) && section.pages.length > 0
    );
    if (!firstSection) return null;
    return {
      sectionSlug: firstSection.slug,
      pageSlug: firstSection.pages[0].slug
    };
  }, [docsSections]);

  const activeSection = useMemo(
    () => docsSections.find((section) => section.slug === sectionSlug),
    [docsSections, sectionSlug]
  );

  const activePageMeta = useMemo(
    () => activeSection?.pages?.find((page) => page.slug === pageSlug),
    [activeSection, pageSlug]
  );
  const isAccessMatrixPage =
    activeSection?.slug === 'operations-and-governance' &&
    activePageMeta?.slug === 'docs-access-matrix';

  useEffect(() => {
    if (loadingManifest) return;
    if (!defaultRoute) return;

    if (!sectionSlug || !pageSlug || !activePageMeta) {
      navigate(buildDocPath(defaultRoute.sectionSlug, defaultRoute.pageSlug), {
        replace: true
      });
    }
  }, [activePageMeta, defaultRoute, loadingManifest, navigate, pageSlug, sectionSlug]);

  useEffect(() => {
    if (!activeSection || !activePageMeta) {
      setActivePageData(null);
      return;
    }

    let canceled = false;

    const fetchPage = async () => {
      setLoadingPage(true);
      setErrorMessage('');
      try {
        const response = await axios.get(
          `/docs/content/${activeSection.slug}/${activePageMeta.slug}`
        );
        if (!canceled) {
          setActivePageData(response?.data?.page || null);
        }
      } catch (error) {
        if (canceled) return;
        setActivePageData(null);

        if (error?.response?.status === 401) {
          setErrorMessage('Session expired. Please sign in again.');
          return;
        }

        if (error?.response?.status === 403 || error?.response?.status === 404) {
          if (
            defaultRoute &&
            (activeSection.slug !== defaultRoute.sectionSlug ||
              activePageMeta.slug !== defaultRoute.pageSlug)
          ) {
            navigate(buildDocPath(defaultRoute.sectionSlug, defaultRoute.pageSlug), {
              replace: true
            });
            return;
          }
          setErrorMessage('You do not have access to this documentation page.');
          return;
        }

        setErrorMessage('Failed to load documentation page.');
      } finally {
        if (!canceled) {
          setLoadingPage(false);
        }
      }
    };

    fetchPage();
    return () => {
      canceled = true;
    };
  }, [activePageMeta, activeSection, defaultRoute, navigate]);

  useEffect(() => {
    let canceled = false;

    if (!isAccessMatrixPage) {
      setDocsAccessMatrix(null);
      setLoadingAccessMatrix(false);
      setAccessMatrixError('');
      return () => {
        canceled = true;
      };
    }

    const fetchAccessMatrix = async () => {
      setLoadingAccessMatrix(true);
      setAccessMatrixError('');
      try {
        const response = await axios.get('/docs/access-matrix');
        if (!canceled) {
          setDocsAccessMatrix(response?.data?.matrix || null);
        }
      } catch (error) {
        if (canceled) return;
        setDocsAccessMatrix(null);
        if (error?.response?.status === 401) {
          setAccessMatrixError('Session expired. Please sign in again.');
        } else if (error?.response?.status === 403) {
          setAccessMatrixError('You do not have access to the documentation access matrix.');
        } else {
          setAccessMatrixError('Failed to load access matrix.');
        }
      } finally {
        if (!canceled) {
          setLoadingAccessMatrix(false);
        }
      }
    };

    fetchAccessMatrix();
    return () => {
      canceled = true;
    };
  }, [isAccessMatrixPage]);

  const normalizedSearch = searchTerm.trim().toLowerCase();

  const filteredSections = useMemo(
    () =>
      docsSections
        .map((section) => ({
          ...section,
          pages: (section.pages || []).filter((page) => {
            if (!normalizedSearch) return true;
            const inTitle = (page.title || '').toLowerCase().includes(normalizedSearch);
            const inSummary = (page.summary || '').toLowerCase().includes(normalizedSearch);
            const inCoverage = (page.coverage || []).some((line) =>
              String(line || '').toLowerCase().includes(normalizedSearch)
            );
            return inTitle || inSummary || inCoverage;
          })
        }))
        .filter((section) => (section.pages || []).length > 0),
    [docsSections, normalizedSearch]
  );

  const allPages = useMemo(() => flattenPages(docsSections), [docsSections]);
  const globalPageIndex = useMemo(
    () =>
      allPages.findIndex(
        (page) => page.sectionSlug === activeSection?.slug && page.slug === activePageMeta?.slug
      ),
    [activePageMeta?.slug, activeSection?.slug, allPages]
  );
  const previousPage = globalPageIndex > 0 ? allPages[globalPageIndex - 1] : null;
  const nextPage =
    globalPageIndex >= 0 && globalPageIndex < allPages.length - 1
      ? allPages[globalPageIndex + 1]
      : null;

  const onNavigatePage = (nextSectionSlug, nextPageSlug) => {
    navigate(buildDocPath(nextSectionSlug, nextPageSlug));
  };

  const activeTitle = activePageData?.title || activePageMeta?.title || 'Documentation';
  const activeSummary = activePageData?.summary || activePageMeta?.summary || '';
  const activeCoverage = activePageData?.coverage || activePageMeta?.coverage || [];
  const article = activePageData?.article || null;

  if (loadingManifest) {
    return (
      <Box sx={{ p: 3, backgroundColor: 'background.default', minHeight: '100vh' }}>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
          RAPTOR Documentation
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Loading documentation...
        </Typography>
      </Box>
    );
  }

  if (!defaultRoute) {
    return (
      <Box sx={{ p: 3, backgroundColor: 'background.default', minHeight: '100vh' }}>
        <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
          RAPTOR Documentation
        </Typography>
        <Paper elevation={0} sx={{ p: 2, border: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>
            No documentation available
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Your account currently has no documentation pages assigned.
          </Typography>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, backgroundColor: 'background.default', minHeight: '100vh' }}>
      <Stack spacing={0.5} sx={{ mb: 2 }}>
        <Typography
          variant="h4"
          sx={{ fontWeight: 700, fontSize: { xs: '1.75rem', md: '2rem' } }}
        >
          RAPTOR Documentation
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Technical reference for operators, testers, and administrators.
        </Typography>
      </Stack>

      <Grid container spacing={2}>
        <Grid item xs={12} md={4} lg={3}>
          <Paper
            elevation={0}
            sx={{
              p: 2,
              border: 1,
              borderColor: 'divider',
              position: { md: 'sticky' },
              top: { md: 92 },
              maxHeight: { md: 'calc(100vh - 120px)' },
              overflowY: 'auto'
            }}
          >
            <TextField
              size="small"
              fullWidth
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Search docs pages"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                )
              }}
            />

            <Divider sx={{ my: 2 }} />

            {filteredSections.map((section) => (
              <Box key={section.slug} sx={{ mb: 1.5 }}>
                <Typography
                  variant="overline"
                  color="text.secondary"
                  sx={{ fontWeight: 600, letterSpacing: 0.5 }}
                >
                  {section.title}
                </Typography>
                <List dense disablePadding>
                  {section.pages.map((page) => {
                    const selected =
                      section.slug === activeSection?.slug && page.slug === activePageMeta?.slug;
                    return (
                      <ListItemButton
                        key={`${section.slug}-${page.slug}`}
                        selected={selected}
                        onClick={() => onNavigatePage(section.slug, page.slug)}
                        sx={{ borderRadius: 1, mt: 0.5 }}
                      >
                        <ListItemText
                          primary={page.title}
                          primaryTypographyProps={{
                            variant: 'body2',
                            fontWeight: selected ? 600 : 400
                          }}
                        />
                      </ListItemButton>
                    );
                  })}
                </List>
              </Box>
            ))}

            {filteredSections.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                No pages match your search.
              </Typography>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={8} lg={9}>
          <Paper
            elevation={0}
            sx={{
              p: { xs: 2, md: 3 },
              border: 1,
              borderColor: 'divider'
            }}
          >
            <Breadcrumbs sx={{ mb: 1.5 }}>
              <Link
                underline="hover"
                color="inherit"
                component="button"
                onClick={() =>
                  onNavigatePage(defaultRoute.sectionSlug, defaultRoute.pageSlug)
                }
              >
                Documentation
              </Link>
              <Typography color="text.primary">{activeSection?.title || ''}</Typography>
              <Typography color="text.primary">{activeTitle}</Typography>
            </Breadcrumbs>

            <Typography
              component="h1"
              variant="h4"
              sx={{ fontWeight: 650, fontSize: { xs: '1.55rem', md: '1.85rem' }, mb: 0.75 }}
            >
              {activeTitle}
            </Typography>
            <Typography
              variant="body1"
              color="text.secondary"
              sx={{ mb: 2.5, lineHeight: 1.7, maxWidth: 950 }}
            >
              {activeSummary}
            </Typography>

            {errorMessage && (
              <Paper
                elevation={0}
                sx={{
                  p: 2,
                  border: 1,
                  borderColor: 'error.main',
                  backgroundColor: 'error.dark',
                  mb: 2
                }}
              >
                <Typography variant="body2" color="error.contrastText">
                  {errorMessage}
                </Typography>
              </Paper>
            )}

            {loadingPage ? (
              <Paper
                elevation={0}
                sx={{
                  p: 2,
                  border: 1,
                  borderColor: 'divider',
                  backgroundColor: 'action.hover'
                }}
              >
                <Typography variant="body2" color="text.secondary">
                  Loading page...
                </Typography>
              </Paper>
            ) : article ? (
              <Grid container spacing={2}>
                <Grid item xs={12} xl={9}>
                  {article.warning && (
                    <Admonition
                      variant={article.warning.variant}
                      title={article.warning.title}
                      paragraphs={article.warning.paragraphs}
                    />
                  )}

                  {(article.sections || []).map((section) => (
                    <Box key={section.id} sx={{ mb: 0.5 }}>
                      <SectionAnchorHeading id={section.id} title={section.title} />

                      {(section.paragraphs || []).map((paragraph) => (
                        <Typography
                          key={paragraph}
                          component="p"
                          variant="body1"
                          sx={{ mb: 1.5, lineHeight: 1.78 }}
                        >
                          {renderInlineCode(paragraph)}
                        </Typography>
                      ))}

                      {section.table && (
                        <TableContainer
                          component={Paper}
                          elevation={0}
                          sx={{ border: 1, borderColor: 'divider', mb: 2 }}
                        >
                          <Table size="small">
                            <TableHead>
                              <TableRow>
                                {section.table.columns.map((column) => (
                                  <TableCell
                                    key={column}
                                    sx={{ fontWeight: 600, whiteSpace: 'nowrap' }}
                                  >
                                    {column}
                                  </TableCell>
                                ))}
                              </TableRow>
                            </TableHead>
                            <TableBody>
                              {section.table.rows.map((row, rowIndex) => (
                                <TableRow key={`row-${rowIndex}`}>
                                  {row.map((cell) => (
                                    <TableCell
                                      key={`${rowIndex}-${cell}`}
                                      sx={{ verticalAlign: 'top', lineHeight: 1.65 }}
                                    >
                                      {renderInlineCode(cell)}
                                    </TableCell>
                                  ))}
                                </TableRow>
                              ))}
                            </TableBody>
                          </Table>
                        </TableContainer>
                      )}

                      {section.list && (
                        <Box component="ul" sx={{ mt: 0.25, mb: 1.5, pl: 2.5 }}>
                          {section.list.map((item) => (
                            <Typography
                              key={item}
                              component="li"
                              variant="body2"
                              sx={{ mb: 0.65, lineHeight: 1.6 }}
                            >
                              {renderInlineCode(item)}
                            </Typography>
                          ))}
                        </Box>
                      )}

                      {section.orderedList && (
                        <Box component="ol" sx={{ mt: 0.25, mb: 1.5, pl: 2.7 }}>
                          {section.orderedList.map((item) => (
                            <Typography
                              key={item}
                              component="li"
                              variant="body2"
                              sx={{ mb: 0.65, lineHeight: 1.6 }}
                            >
                              {renderInlineCode(item)}
                            </Typography>
                          ))}
                        </Box>
                      )}

                      {section.tip && (
                        <Admonition
                          variant={section.tip.variant}
                          title={section.tip.title}
                          paragraphs={section.tip.paragraphs}
                        />
                      )}

                      {section.dynamic?.type === 'docs-access-matrix' && (
                        <DocsAccessMatrix
                          matrix={docsAccessMatrix}
                          loading={loadingAccessMatrix}
                          error={accessMatrixError}
                          onNavigatePath={(path) => navigate(path)}
                        />
                      )}

                      {section.related && (
                        <Box sx={{ mb: 1.75 }}>
                          <Typography variant="body2" sx={{ fontWeight: 600, mb: 0.5 }}>
                            Related pages
                          </Typography>
                          {section.related.map((entry) => (
                            <Typography key={entry.to} variant="body2" sx={{ mb: 0.3 }}>
                              <Link
                                underline="hover"
                                component="button"
                                onClick={() => navigate(entry.to)}
                              >
                                {entry.label}
                              </Link>
                            </Typography>
                          ))}
                        </Box>
                      )}
                    </Box>
                  ))}
                </Grid>

                <Grid item xs={12} xl={3}>
                  <Paper
                    elevation={0}
                    sx={{
                      p: 2,
                      border: 1,
                      borderColor: 'divider',
                      position: { xl: 'sticky' },
                      top: { xl: 92 }
                    }}
                  >
                    <Typography
                      variant="subtitle2"
                      sx={{ fontWeight: 700, mb: 1, letterSpacing: 0.2 }}
                    >
                      On this page
                    </Typography>
                    {(article.sections || []).map((section) => (
                      <Typography key={section.id} variant="body2" sx={{ mb: 0.65 }}>
                        <Link underline="hover" href={`#${section.id}`} color="text.secondary">
                          {section.title}
                        </Link>
                      </Typography>
                    ))}
                  </Paper>
                </Grid>
              </Grid>
            ) : (
              <Paper
                elevation={0}
                sx={{
                  p: 2,
                  border: 1,
                  borderColor: 'divider',
                  backgroundColor: 'action.hover'
                }}
              >
                <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                  Planned page scope
                </Typography>
                <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                  {activeCoverage.map((item) => (
                    <Typography key={item} component="li" variant="body2" sx={{ mb: 0.75 }}>
                      {item}
                    </Typography>
                  ))}
                </Box>
              </Paper>
            )}

            <Stack direction="row" justifyContent="space-between" spacing={2} sx={{ mt: 3 }}>
              <Button
                startIcon={<ArrowBack />}
                disabled={!previousPage}
                onClick={() =>
                  previousPage &&
                  onNavigatePage(previousPage.sectionSlug, previousPage.slug)
                }
              >
                Previous
              </Button>
              <Button
                endIcon={<ArrowForward />}
                disabled={!nextPage}
                onClick={() => nextPage && onNavigatePage(nextPage.sectionSlug, nextPage.slug)}
              >
                Next
              </Button>
            </Stack>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DocumentationPortal;
