import React, { useEffect, useMemo, useState } from 'react';
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
import { DEFAULT_DOC_ROUTE, DOC_SECTIONS, flattenDocsPages } from './docs/outline';

const buildDocPath = (sectionSlug, pageSlug) => `/docs/${sectionSlug}/${pageSlug}`;

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
        sx={{ fontWeight: 700, mb: 1, color: isImportant ? 'warning.contrastText' : 'info.contrastText' }}
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

const DocumentationPortal = () => {
  const navigate = useNavigate();
  const { sectionSlug, pageSlug } = useParams();
  const [searchTerm, setSearchTerm] = useState('');

  const allPages = useMemo(() => flattenDocsPages(), []);
  const activeSection = useMemo(
    () => DOC_SECTIONS.find((section) => section.slug === sectionSlug),
    [sectionSlug]
  );
  const activePage = useMemo(
    () => activeSection?.pages.find((page) => page.slug === pageSlug),
    [activeSection, pageSlug]
  );

  useEffect(() => {
    if (!activePage) {
      navigate(
        buildDocPath(DEFAULT_DOC_ROUTE.sectionSlug, DEFAULT_DOC_ROUTE.pageSlug),
        { replace: true }
      );
    }
  }, [activePage, navigate]);

  const normalizedSearch = searchTerm.trim().toLowerCase();

  const filteredSections = useMemo(
    () =>
      DOC_SECTIONS.map((section) => ({
        ...section,
        pages: section.pages.filter((page) => {
          if (!normalizedSearch) return true;
          const inTitle = page.title.toLowerCase().includes(normalizedSearch);
          const inSummary = page.summary.toLowerCase().includes(normalizedSearch);
          const inCoverage = page.coverage.some((line) =>
            line.toLowerCase().includes(normalizedSearch)
          );
          const inArticleSections =
            page.article?.sections?.some(
              (articleSection) =>
                articleSection.title.toLowerCase().includes(normalizedSearch) ||
                (articleSection.paragraphs || []).some((paragraph) =>
                  paragraph.toLowerCase().includes(normalizedSearch)
                )
            ) || false;
          return inTitle || inSummary || inCoverage || inArticleSections;
        })
      })).filter((section) => section.pages.length > 0),
    [normalizedSearch]
  );

  if (!activeSection || !activePage) {
    return null;
  }

  const globalPageIndex = allPages.findIndex(
    (page) =>
      page.sectionSlug === activeSection.slug && page.slug === activePage.slug
  );
  const previousPage = globalPageIndex > 0 ? allPages[globalPageIndex - 1] : null;
  const nextPage =
    globalPageIndex < allPages.length - 1 ? allPages[globalPageIndex + 1] : null;

  const onNavigatePage = (nextSectionSlug, nextPageSlug) => {
    navigate(buildDocPath(nextSectionSlug, nextPageSlug));
  };

  const article = activePage.article;

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
                      section.slug === activeSection.slug && page.slug === activePage.slug;
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
                  onNavigatePage(DEFAULT_DOC_ROUTE.sectionSlug, DEFAULT_DOC_ROUTE.pageSlug)
                }
              >
                Documentation
              </Link>
              <Typography color="text.primary">{activeSection.title}</Typography>
              <Typography color="text.primary">{activePage.title}</Typography>
            </Breadcrumbs>

            <Typography
              component="h1"
              variant="h4"
              sx={{ fontWeight: 650, fontSize: { xs: '1.55rem', md: '1.85rem' }, mb: 0.75 }}
            >
              {activePage.title}
            </Typography>
            <Typography
              variant="body1"
              color="text.secondary"
              sx={{ mb: 2.5, lineHeight: 1.7, maxWidth: 950 }}
            >
              {activePage.summary}
            </Typography>

            {article ? (
              <Grid container spacing={2}>
                <Grid item xs={12} xl={9}>
                  {article.warning && (
                    <Admonition
                      variant={article.warning.variant}
                      title={article.warning.title}
                      paragraphs={article.warning.paragraphs}
                    />
                  )}

                  {article.sections.map((section) => (
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
                    {article.sections.map((section) => (
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
                  {activePage.coverage.map((item) => (
                    <Typography key={item} component="li" variant="body2" sx={{ mb: 0.75 }}>
                      {item}
                    </Typography>
                  ))}
                </Box>
              </Paper>
            )}

            <Stack
              direction="row"
              justifyContent="space-between"
              spacing={2}
              sx={{ mt: 3 }}
            >
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
