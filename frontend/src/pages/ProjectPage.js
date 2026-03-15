import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import {
  Grid, Paper, Typography, Box, Tabs, Tab, TextField, IconButton,
  Button, CircularProgress, Alert, Chip, LinearProgress,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Card, CardContent, MenuItem, Select, FormControl, InputLabel,
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import SaveIcon from '@mui/icons-material/Save';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ScienceIcon from '@mui/icons-material/Science';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import PsychologyIcon from '@mui/icons-material/Psychology';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { apiFetch } from '../api';

/* ---------- Tab Panel ---------- */
function TabPanel({ children, value, index }) {
  return value === index ? <Box sx={{ p: 2 }}>{children}</Box> : null;
}

/* ---------- Main Component ---------- */
export default function ProjectPage() {
  const { id } = useParams();
  const [tab, setTab] = useState(0);

  // Project data
  const [project, setProject] = useState(null);
  const [loadingProject, setLoadingProject] = useState(true);

  // Definition fields
  const [genesDesc, setGenesDesc] = useState('');
  const [objectivesDesc, setObjectivesDesc] = useState('');
  const [constraintsDesc, setConstraintsDesc] = useState('');
  const [defSaving, setDefSaving] = useState(false);
  const [defFeedback, setDefFeedback] = useState(null);
  const [editingGenes, setEditingGenes] = useState(false);
  const [editingObjectives, setEditingObjectives] = useState(false);
  const [editingConstraints, setEditingConstraints] = useState(false);

  // Chat
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef(null);

  // Genes (parsed, from backend)
  const [genes, setGenes] = useState([]);

  // Fitness function editor
  const [fitnessCode, setFitnessCode] = useState('');
  const [fitnessSaving, setFitnessSaving] = useState(false);
  const [fitnessRegenerating, setFitnessRegenerating] = useState(false);
  const [fitnessFeedback, setFitnessFeedback] = useState(null);

  // Benchmark
  const [geneValues, setGeneValues] = useState({});
  const [benchmarkResult, setBenchmarkResult] = useState(null);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [benchmarkError, setBenchmarkError] = useState('');

  // Executions
  const [iterations, setIterations] = useState(100);
  const [executions, setExecutions] = useState([]);
  const [executionLoading, setExecutionLoading] = useState(false);
  const [selectedExecution, setSelectedExecution] = useState(null);
  const [interpreting, setInterpreting] = useState(false);
  const pollingRef = useRef(null);

  /* ---------- Load project ---------- */
  const loadProject = useCallback(async () => {
    try {
      const data = await apiFetch(`/projects/${id}`);
      if (data) {
        setProject(data);
        setGenesDesc(data.genes_description || '');
        setObjectivesDesc(data.objectives_description || '');
        setConstraintsDesc(data.constraints_description || '');
        setFitnessCode(data.fitness_function_code || '');
      }
    } catch (err) {
      console.error('Failed to load project', err);
    } finally {
      setLoadingProject(false);
    }
  }, [id]);

  /* ---------- Load genes ---------- */
  const loadGenes = useCallback(async () => {
    try {
      const data = await apiFetch(`/projects/${id}/genes`);
      if (data) setGenes(data);
    } catch (err) {
      console.error('Failed to load genes', err);
    }
  }, [id]);

  /* ---------- Load messages ---------- */
  const loadMessages = useCallback(async () => {
    try {
      const data = await apiFetch(`/projects/${id}/messages`);
      if (data) setMessages(data);
    } catch (err) {
      console.error('Failed to load messages', err);
    }
  }, [id]);

  /* ---------- Load executions ---------- */
  const loadExecutions = useCallback(async () => {
    try {
      const data = await apiFetch(`/projects/${id}/executions`);
      if (data) setExecutions(data);
    } catch (err) {
      console.error('Failed to load executions', err);
    }
  }, [id]);

  useEffect(() => {
    loadProject();
    loadMessages();
    loadExecutions();
    loadGenes();
  }, [loadProject, loadMessages, loadExecutions, loadGenes]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, chatLoading]);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  /* ---------- Chat send ---------- */
  const handleSend = async () => {
    const content = chatInput.trim();
    if (!content) return;
    setChatInput('');
    setChatLoading(true);

    // Optimistic user message
    const tempMsg = { id: Date.now(), role: 'user', content, created_at: new Date().toISOString() };
    setMessages(prev => [...prev, tempMsg]);

    try {
      const data = await apiFetch(`/projects/${id}/messages`, {
        method: 'POST',
        body: JSON.stringify({ content }),
      });
      if (data) {
        setMessages(prev => {
          const filtered = prev.filter(m => m.id !== tempMsg.id);
          return [...filtered, { ...tempMsg }, data.message];
        });
        // Update definition fields if provided
        if (data.genes_description != null) setGenesDesc(data.genes_description);
        if (data.objectives_description != null) setObjectivesDesc(data.objectives_description);
        if (data.constraints_description != null) setConstraintsDesc(data.constraints_description);

        // If definitions were updated, reload genes and project (fitness may have been regenerated)
        if (data.genes_description != null || data.objectives_description != null || data.constraints_description != null) {
          await loadGenes();
          await loadProject();
        }
      }
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { id: Date.now() + 1, role: 'assistant', content: `Error: ${err.message}`, created_at: new Date().toISOString() },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  /* ---------- Save definition ---------- */
  const handleSaveDefinition = async () => {
    setDefSaving(true);
    setDefFeedback(null);
    try {
      await apiFetch(`/projects/${id}`, {
        method: 'PUT',
        body: JSON.stringify({
          genes_description: genesDesc,
          objectives_description: objectivesDesc,
          constraints_description: constraintsDesc,
        }),
      });
      setDefFeedback({ severity: 'success', text: 'Definition saved. Fitness function regenerated.' });
      await loadGenes();
      await loadProject();
    } catch (err) {
      setDefFeedback({ severity: 'error', text: err.message });
    } finally {
      setDefSaving(false);
    }
  };

  /* ---------- Fitness function ---------- */
  const handleSaveFitness = async () => {
    setFitnessSaving(true);
    setFitnessFeedback(null);
    try {
      await apiFetch(`/projects/${id}`, {
        method: 'PUT',
        body: JSON.stringify({ fitness_function_code: fitnessCode }),
      });
      setFitnessFeedback({ severity: 'success', text: 'Fitness function saved.' });
    } catch (err) {
      setFitnessFeedback({ severity: 'error', text: err.message });
    } finally {
      setFitnessSaving(false);
    }
  };

  const handleRegenerateFitness = async () => {
    setFitnessRegenerating(true);
    setFitnessFeedback(null);
    try {
      const data = await apiFetch(`/projects/${id}/regenerate-fitness`, { method: 'POST' });
      if (data) {
        setFitnessCode(data.fitness_function_code || '');
        setFitnessFeedback({ severity: 'success', text: 'Fitness function regenerated.' });
      }
    } catch (err) {
      setFitnessFeedback({ severity: 'error', text: err.message });
    } finally {
      setFitnessRegenerating(false);
    }
  };

  /* ---------- Benchmark ---------- */
  const handleGeneValueChange = (geneName, value) => {
    setGeneValues(prev => ({ ...prev, [geneName]: value }));
  };

  const handleBenchmark = async () => {
    setBenchmarkLoading(true);
    setBenchmarkResult(null);
    setBenchmarkError('');
    try {
      // Coerce values to appropriate types before sending
      const coerced = {};
      for (const gene of genes) {
        const val = geneValues[gene.name];
        if (gene.type === 'float') {
          coerced[gene.name] = parseFloat(val) || 0;
        } else if (gene.type === 'int') {
          coerced[gene.name] = parseInt(val, 10) || 0;
        } else {
          coerced[gene.name] = val || '';
        }
      }
      const data = await apiFetch(`/projects/${id}/benchmark`, {
        method: 'POST',
        body: JSON.stringify({ gene_values: coerced }),
      });
      if (data) setBenchmarkResult(data);
    } catch (err) {
      setBenchmarkError(err.message);
    } finally {
      setBenchmarkLoading(false);
    }
  };

  /* ---------- Executions ---------- */
  const handleRunOptimization = async () => {
    setExecutionLoading(true);
    try {
      const data = await apiFetch(`/projects/${id}/executions`, {
        method: 'POST',
        body: JSON.stringify({ num_iterations: iterations }),
      });
      if (data) {
        setExecutions(prev => [data, ...prev]);
        startPolling(data.id);
      }
    } catch (err) {
      console.error('Failed to start execution', err);
    } finally {
      setExecutionLoading(false);
    }
  };

  const startPolling = (execId) => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      try {
        const data = await apiFetch(`/projects/${id}/executions/${execId}`);
        if (data) {
          setExecutions(prev => prev.map(e => e.id === execId ? data : e));
          if (data.status === 'completed' || data.status === 'failed') {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
          }
        }
      } catch (err) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    }, 2000);
  };

  const handleViewExecution = async (execId) => {
    try {
      const data = await apiFetch(`/projects/${id}/executions/${execId}`);
      if (data) setSelectedExecution(data);
    } catch (err) {
      console.error('Failed to load execution', err);
    }
  };

  const handleDeleteExecution = async (execId) => {
    if (!window.confirm('Delete this execution? This cannot be undone.')) return;
    try {
      await apiFetch(`/projects/${id}/executions/${execId}`, { method: 'DELETE' });
      setExecutions(prev => prev.filter(e => e.id !== execId));
      if (selectedExecution?.id === execId) setSelectedExecution(null);
    } catch (err) {
      console.error('Failed to delete execution', err);
    }
  };

  const handleInterpret = async () => {
    if (!selectedExecution) return;
    setInterpreting(true);
    try {
      const data = await apiFetch(`/projects/${id}/executions/${selectedExecution.id}/interpret`, {
        method: 'POST',
      });
      if (data) setSelectedExecution(data);
    } catch (err) {
      console.error('Failed to interpret execution', err);
    } finally {
      setInterpreting(false);
    }
  };

  /* ---------- Render helpers ---------- */
  const statusColor = (status) => {
    switch (status) {
      case 'completed': return 'success';
      case 'running': return 'warning';
      case 'failed': return 'error';
      case 'pending': return 'default';
      default: return 'default';
    }
  };

  const renderConvergenceChart = (resultData) => {
    if (!resultData?.convergence) return null;
    const chartData = resultData.convergence.map((val, idx) => ({
      generation: idx + 1,
      fitness: val,
    }));
    return (
      <Box sx={{ width: '100%', height: 250, mt: 2 }}>
        <Typography variant="subtitle2" gutterBottom>Fitness Convergence</Typography>
        <ResponsiveContainer>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="generation" label={{ value: 'Generation', position: 'insideBottom', offset: -5 }} />
            <YAxis 
              label={{ value: 'Fitness', angle: -90, position: 'insideLeft' }} 
              domain={['auto', 'auto']} // autoscale Y axis between min/max in data
              allowDataOverflow={false}
            />
            <Tooltip />
            <Line type="monotone" dataKey="fitness" stroke="#1976d2" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </Box>
    );
  };

  const renderSolutionsTable = (solutions, label) => {
    if (!solutions || solutions.length === 0) return null;
    const keys = Object.keys(solutions[0]);
    return (
      <Box sx={{ mt: 2 }}>
        <Typography variant="subtitle2" gutterBottom>{label}</Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                {keys.map(k => <TableCell key={k}><strong>{k}</strong></TableCell>)}
              </TableRow>
            </TableHead>
            <TableBody>
              {solutions.map((sol, idx) => (
                <TableRow key={idx}>
                  {keys.map(k => (
                    <TableCell key={k}>
                      {typeof sol[k] === 'number' ? sol[k].toFixed(4) : String(sol[k] ?? '')}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </Box>
    );
  };

  if (loadingProject) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Grid container spacing={2} sx={{ height: 'calc(100vh - 120px)', overflow: 'hidden' }}>
      {/* Left panel - Chat */}
      <Grid item xs={12} md={5} sx={{ height: '100%' }}>
        <Paper sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', flexShrink: 0 }}>
            <Typography variant="h6">{project?.name || 'Chat'}</Typography>
          </Box>

          {/* Messages */}
          <Box sx={{ flexGrow: 1, p: 2, overflow: 'auto', minHeight: 0 }}>
            {messages.length === 0 && !chatLoading && (
              <Typography color="text.secondary" align="center" sx={{ mt: 4 }}>
                Describe the optimization problem you want to solve.
              </Typography>
            )}
            {messages.map((msg) => (
              <Box
                key={msg.id}
                sx={{
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  mb: 1.5,
                }}
              >
                <Box
                  sx={{
                    maxWidth: '80%',
                    px: 2,
                    py: 1,
                    borderRadius: 2,
                    bgcolor: msg.role === 'user' ? 'primary.dark' : 'background.paper',
                    color: msg.role === 'user' ? '#0a0e14' : 'text.primary',
                    wordBreak: 'break-word',
                    fontSize: '0.9rem',
                    ...(msg.role === 'user'
                      ? { whiteSpace: 'pre-wrap' }
                      : {
                          '& p': { m: 0, mb: 0.5, '&:last-child': { mb: 0 } },
                          '& h1, & h2, & h3, & h4': { mt: 1, mb: 0.5, fontSize: '0.95rem', fontWeight: 'bold' },
                          '& ul, & ol': { pl: 2.5, my: 0.5 },
                          '& li': { mb: 0.25 },
                          '& table': {
                            width: '100%',
                            borderCollapse: 'collapse',
                            my: 1,
                            fontSize: '0.85rem',
                          },
                          '& th, & td': {
                            border: '1px solid',
                            borderColor: 'divider',
                            px: 1,
                            py: 0.5,
                            textAlign: 'left',
                          },
                          '& th': { bgcolor: 'action.hover', fontWeight: 'bold' },
                          '& code': {
                            bgcolor: 'action.hover',
                            px: 0.5,
                            borderRadius: 0.5,
                            fontSize: '0.8rem',
                            fontFamily: 'monospace',
                          },
                          '& pre': {
                            bgcolor: 'action.hover',
                            p: 1,
                            borderRadius: 1,
                            overflow: 'auto',
                            my: 0.5,
                            '& code': { bgcolor: 'transparent', p: 0 },
                          },
                          '& blockquote': {
                            borderLeft: 3,
                            borderColor: 'primary.main',
                            pl: 1.5,
                            ml: 0,
                            color: 'text.secondary',
                          },
                          '& hr': { my: 1, borderColor: 'divider' },
                        }),
                  }}
                >
                  {msg.role === 'user' ? (
                    msg.content
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {msg.content}
                    </ReactMarkdown>
                  )}
                </Box>
              </Box>
            ))}
            {chatLoading && (
              <Box sx={{ display: 'flex', justifyContent: 'flex-start', mb: 1.5 }}>
                <Box sx={{ px: 2, py: 1, borderRadius: 2, bgcolor: 'action.selected' }}>
                  <CircularProgress size={20} />
                </Box>
              </Box>
            )}
            <div ref={chatEndRef} />
          </Box>

          {/* Input */}
          <Box sx={{ p: 2, display: 'flex', gap: 1, borderTop: 1, borderColor: 'divider' }}>
            <TextField
              fullWidth
              size="small"
              placeholder="Describe your optimization problem..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={handleKeyDown}
              multiline
              maxRows={4}
              disabled={chatLoading}
            />
            <IconButton color="primary" onClick={handleSend} disabled={chatLoading || !chatInput.trim()}>
              <SendIcon />
            </IconButton>
          </Box>
        </Paper>
      </Grid>

      {/* Right panel - Definition / Benchmark / Executions */}
      <Grid item xs={12} md={7} sx={{ height: '100%' }}>
        <Paper sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)}>
            <Tab label="Definition" />
            <Tab label="Fitness Function" />
            <Tab label="Benchmark" />
            <Tab label="Executions" />
          </Tabs>
          <Box sx={{ flexGrow: 1, overflow: 'auto' }}>

            {/* ===== Definition Tab ===== */}
            <TabPanel value={tab} index={0}>
              {defFeedback && (
                <Alert severity={defFeedback.severity} sx={{ mb: 2 }} onClose={() => setDefFeedback(null)}>
                  {defFeedback.text}
                </Alert>
              )}
              {/* --- Genes --- */}
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>Genes Description</Typography>
                {!editingGenes && (
                  <IconButton size="small" onClick={() => setEditingGenes(true)} title="Edit">
                    <EditIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
              {editingGenes ? (
                <TextField
                  fullWidth
                  multiline
                  rows={5}
                  placeholder="Gene definitions will appear here after chatting with AI..."
                  value={genesDesc}
                  onChange={(e) => setGenesDesc(e.target.value)}
                  sx={{ mb: 2 }}
                />
              ) : (
                <Box
                  onClick={() => !genesDesc && setEditingGenes(true)}
                  sx={{
                    mb: 2, p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1,
                    minHeight: 60, bgcolor: 'background.paper', cursor: genesDesc ? 'default' : 'pointer',
                    '& p': { m: 0, mb: 0.5, fontSize: '0.875rem', '&:last-child': { mb: 0 } },
                    '& ul, & ol': { pl: 2.5, my: 0.5, fontSize: '0.875rem' },
                    '& li': { mb: 0.25 },
                    '& h1,& h2,& h3,& h4': { mt: 1, mb: 0.5, fontSize: '0.95rem', fontWeight: 'bold' },
                    '& code': { bgcolor: 'action.selected', px: 0.5, borderRadius: 0.5, fontSize: '0.8rem', fontFamily: 'monospace' },
                    '& pre': { bgcolor: 'action.selected', p: 1, borderRadius: 1, overflow: 'auto', my: 0.5, '& code': { bgcolor: 'transparent', p: 0 } },
                    '& table': { width: '100%', borderCollapse: 'collapse', my: 1, fontSize: '0.85rem' },
                    '& th,& td': { border: '1px solid', borderColor: 'divider', px: 1, py: 0.5, textAlign: 'left' },
                    '& th': { bgcolor: 'action.selected', fontWeight: 'bold' },
                  }}
                >
                  {genesDesc ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{genesDesc}</ReactMarkdown>
                  ) : (
                    <Typography variant="body2" color="text.secondary">Gene definitions will appear here after chatting with AI...</Typography>
                  )}
                </Box>
              )}

              {/* --- Objectives --- */}
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>Objectives Description</Typography>
                {!editingObjectives && (
                  <IconButton size="small" onClick={() => setEditingObjectives(true)} title="Edit">
                    <EditIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
              {editingObjectives ? (
                <TextField
                  fullWidth
                  multiline
                  rows={5}
                  placeholder="Objective function description..."
                  value={objectivesDesc}
                  onChange={(e) => setObjectivesDesc(e.target.value)}
                  sx={{ mb: 2 }}
                />
              ) : (
                <Box
                  onClick={() => !objectivesDesc && setEditingObjectives(true)}
                  sx={{
                    mb: 2, p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1,
                    minHeight: 60, bgcolor: 'background.paper', cursor: objectivesDesc ? 'default' : 'pointer',
                    '& p': { m: 0, mb: 0.5, fontSize: '0.875rem', '&:last-child': { mb: 0 } },
                    '& ul, & ol': { pl: 2.5, my: 0.5, fontSize: '0.875rem' },
                    '& li': { mb: 0.25 },
                    '& h1,& h2,& h3,& h4': { mt: 1, mb: 0.5, fontSize: '0.95rem', fontWeight: 'bold' },
                    '& code': { bgcolor: 'action.selected', px: 0.5, borderRadius: 0.5, fontSize: '0.8rem', fontFamily: 'monospace' },
                    '& pre': { bgcolor: 'action.selected', p: 1, borderRadius: 1, overflow: 'auto', my: 0.5, '& code': { bgcolor: 'transparent', p: 0 } },
                    '& table': { width: '100%', borderCollapse: 'collapse', my: 1, fontSize: '0.85rem' },
                    '& th,& td': { border: '1px solid', borderColor: 'divider', px: 1, py: 0.5, textAlign: 'left' },
                    '& th': { bgcolor: 'action.selected', fontWeight: 'bold' },
                  }}
                >
                  {objectivesDesc ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{objectivesDesc}</ReactMarkdown>
                  ) : (
                    <Typography variant="body2" color="text.secondary">Objective function description...</Typography>
                  )}
                </Box>
              )}

              {/* --- Constraints --- */}
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                <Typography variant="subtitle2" sx={{ flexGrow: 1 }}>Constraints Description</Typography>
                {!editingConstraints && (
                  <IconButton size="small" onClick={() => setEditingConstraints(true)} title="Edit">
                    <EditIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
              {editingConstraints ? (
                <TextField
                  fullWidth
                  multiline
                  rows={5}
                  placeholder="Constraints will appear here..."
                  value={constraintsDesc}
                  onChange={(e) => setConstraintsDesc(e.target.value)}
                  sx={{ mb: 2 }}
                />
              ) : (
                <Box
                  onClick={() => !constraintsDesc && setEditingConstraints(true)}
                  sx={{
                    mb: 2, p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1,
                    minHeight: 60, bgcolor: 'background.paper', cursor: constraintsDesc ? 'default' : 'pointer',
                    '& p': { m: 0, mb: 0.5, fontSize: '0.875rem', '&:last-child': { mb: 0 } },
                    '& ul, & ol': { pl: 2.5, my: 0.5, fontSize: '0.875rem' },
                    '& li': { mb: 0.25 },
                    '& h1,& h2,& h3,& h4': { mt: 1, mb: 0.5, fontSize: '0.95rem', fontWeight: 'bold' },
                    '& code': { bgcolor: 'action.selected', px: 0.5, borderRadius: 0.5, fontSize: '0.8rem', fontFamily: 'monospace' },
                    '& pre': { bgcolor: 'action.selected', p: 1, borderRadius: 1, overflow: 'auto', my: 0.5, '& code': { bgcolor: 'transparent', p: 0 } },
                    '& table': { width: '100%', borderCollapse: 'collapse', my: 1, fontSize: '0.85rem' },
                    '& th,& td': { border: '1px solid', borderColor: 'divider', px: 1, py: 0.5, textAlign: 'left' },
                    '& th': { bgcolor: 'action.selected', fontWeight: 'bold' },
                  }}
                >
                  {constraintsDesc ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{constraintsDesc}</ReactMarkdown>
                  ) : (
                    <Typography variant="body2" color="text.secondary">Constraints will appear here...</Typography>
                  )}
                </Box>
              )}

              <Button
                variant="contained"
                startIcon={defSaving ? <CircularProgress size={16} color="inherit" /> : <SaveIcon />}
                onClick={() => {
                  setEditingGenes(false);
                  setEditingObjectives(false);
                  setEditingConstraints(false);
                  handleSaveDefinition();
                }}
                disabled={defSaving}
              >
                {defSaving ? 'Saving & Generating...' : 'Save Definition'}
              </Button>
            </TabPanel>

            {/* ===== Fitness Function Tab ===== */}
            <TabPanel value={tab} index={1}>
              {fitnessFeedback && (
                <Alert severity={fitnessFeedback.severity} sx={{ mb: 2 }} onClose={() => setFitnessFeedback(null)}>
                  {fitnessFeedback.text}
                </Alert>
              )}
              <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
                <Button
                  variant="contained"
                  startIcon={fitnessSaving ? <CircularProgress size={16} color="inherit" /> : <SaveIcon />}
                  onClick={handleSaveFitness}
                  disabled={fitnessSaving || fitnessRegenerating}
                >
                  {fitnessSaving ? 'Saving...' : 'Save'}
                </Button>
                <Button
                  variant="outlined"
                  startIcon={fitnessRegenerating ? <CircularProgress size={16} /> : <AutoFixHighIcon />}
                  onClick={handleRegenerateFitness}
                  disabled={fitnessSaving || fitnessRegenerating}
                >
                  {fitnessRegenerating ? 'Regenerating...' : 'Regenerate from Definitions'}
                </Button>
              </Box>
              <TextField
                fullWidth
                multiline
                rows={22}
                placeholder="The fitness function will be generated here once you save the definition..."
                value={fitnessCode}
                onChange={(e) => setFitnessCode(e.target.value)}
                InputProps={{
                  sx: {
                    fontFamily: 'monospace',
                    fontSize: '0.85rem',
                    alignItems: 'flex-start',
                  },
                }}
              />
            </TabPanel>

            {/* ===== Benchmark Tab ===== */}
            <TabPanel value={tab} index={2}>
              {genes.length === 0 ? (
                <Typography color="text.secondary">
                  Define genes in the Definition tab and save first. The benchmark UI will be generated based on gene types.
                </Typography>
              ) : (
                <>
                  <Typography variant="subtitle2" gutterBottom>
                    Test Gene Values
                  </Typography>
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 2 }}>
                    {genes.map((gene) => {
                      const options = gene.options
                        ? gene.options.split(',').map(o => o.trim()).filter(Boolean)
                        : [];
                      return (
                        <Box key={gene.name}>
                          {gene.type === 'enum' ? (
                            <FormControl fullWidth size="small">
                              <InputLabel>{gene.name}</InputLabel>
                              <Select
                                label={gene.name}
                                value={geneValues[gene.name] || ''}
                                onChange={(e) => handleGeneValueChange(gene.name, e.target.value)}
                              >
                                {options.map(opt => (
                                  <MenuItem key={opt} value={opt}>{opt}</MenuItem>
                                ))}
                              </Select>
                            </FormControl>
                          ) : (
                            <TextField
                              fullWidth
                              size="small"
                              type="number"
                              label={gene.name}
                              helperText={`${gene.description || ''}${gene.low != null ? ` (${gene.low} – ${gene.high})` : ''}`}
                              value={geneValues[gene.name] ?? ''}
                              onChange={(e) => handleGeneValueChange(gene.name, e.target.value)}
                              inputProps={{
                                min: gene.low,
                                max: gene.high,
                                step: gene.type === 'float' ? Math.pow(10, -(gene.decimals || 2)) : 1,
                              }}
                            />
                          )}
                        </Box>
                      );
                    })}
                  </Box>

                  <Button
                    variant="contained"
                    startIcon={<ScienceIcon />}
                    onClick={handleBenchmark}
                    disabled={benchmarkLoading}
                  >
                    {benchmarkLoading ? 'Executing...' : 'Execute'}
                  </Button>

                  {benchmarkError && (
                    <Alert severity="error" sx={{ mt: 2 }}>{benchmarkError}</Alert>
                  )}

                  {benchmarkResult && (
                    <Card sx={{ mt: 2 }}>
                      <CardContent>
                        <Typography variant="subtitle2" gutterBottom>Results</Typography>
                        {benchmarkResult.results && Object.entries(benchmarkResult.results).map(([key, val]) => (
                          <Box key={key} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
                            <Typography variant="body2" color="text.secondary">{key}</Typography>
                            <Typography variant="body2" fontWeight="bold">
                              {typeof val === 'number' ? val.toFixed(4) : String(val)}
                            </Typography>
                          </Box>
                        ))}
                        {benchmarkResult.errors && benchmarkResult.errors.length > 0 && (
                          <Box sx={{ mt: 1 }}>
                            <Typography variant="subtitle2" color="error">Constraint Violations</Typography>
                            {benchmarkResult.errors.map((err, idx) => (
                              <Typography key={idx} variant="body2" color="error">- {err}</Typography>
                            ))}
                          </Box>
                        )}
                      </CardContent>
                    </Card>
                  )}
                </>
              )}
            </TabPanel>

            {/* ===== Executions Tab ===== */}
            <TabPanel value={tab} index={3}>
              <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 3 }}>
                <TextField
                  size="small"
                  type="number"
                  label="Iterations"
                  value={iterations}
                  onChange={(e) => setIterations(parseInt(e.target.value, 10) || 100)}
                  inputProps={{ min: 1 }}
                  sx={{ width: 140 }}
                />
                <Button
                  variant="contained"
                  startIcon={<PlayArrowIcon />}
                  onClick={handleRunOptimization}
                  disabled={executionLoading}
                >
                  {executionLoading ? 'Starting...' : 'Run Optimization'}
                </Button>
              </Box>

              {/* Executions list */}
              {executions.length === 0 ? (
                <Typography color="text.secondary">
                  No executions yet. Configure iterations and run an optimization.
                </Typography>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  {executions.map((exec) => (
                    <Card key={exec.id} variant="outlined">
                      <CardContent>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                          <Typography variant="subtitle2">
                            Execution #{exec.id} - {exec.num_iterations} iterations
                          </Typography>
                          <Chip label={exec.status} color={statusColor(exec.status)} size="small" />
                        </Box>

                        {exec.status === 'running' && (
                          <Box sx={{ mb: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={exec.progress || 0}
                              sx={{ height: 8, borderRadius: 4 }}
                            />
                            <Typography variant="caption" color="text.secondary">
                              {exec.progress || 0}% complete
                            </Typography>
                          </Box>
                        )}

                        {exec.status === 'completed' && (
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            <Button
                              size="small"
                              onClick={() => handleViewExecution(exec.id)}
                            >
                              View Results
                            </Button>
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={() => {
                                const resultData = exec.result_data;
                                if (!resultData) return;
                                const best =
                                  resultData.top_solutions?.[0] ||
                                  resultData.pareto_front?.[0];
                                if (!best) return;
                                const geneNames = new Set(genes.map(g => g.name));
                                const values = {};
                                for (const [k, v] of Object.entries(best)) {
                                  if (geneNames.has(k)) values[k] = v;
                                }
                                setGeneValues(values);
                                setTab(2); // switch to Benchmark tab
                              }}
                            >
                              Push to Benchmark
                            </Button>
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleDeleteExecution(exec.id)}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Box>
                        )}

                        {exec.status !== 'completed' && (
                          <IconButton
                            size="small"
                            color="error"
                            onClick={() => handleDeleteExecution(exec.id)}
                            sx={{ mt: 0.5 }}
                          >
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        )}

                        {exec.created_at && (
                          <Typography variant="caption" color="text.secondary" display="block">
                            Started: {new Date(exec.created_at).toLocaleString()}
                          </Typography>
                        )}
                      </CardContent>
                    </Card>
                  ))}
                </Box>
              )}

              {/* Selected execution details */}
              {selectedExecution && selectedExecution.status === 'completed' && (
                <Box sx={{ mt: 3, pt: 2, borderTop: 1, borderColor: 'divider' }}>
                  <Typography variant="h6" gutterBottom>
                    Execution #{selectedExecution.id} Results
                  </Typography>

                  {selectedExecution.result_data?.convergence && renderConvergenceChart(selectedExecution.result_data)}

                  {selectedExecution.result_data?.top_solutions && renderSolutionsTable(
                    selectedExecution.result_data.top_solutions.slice(0, 5),
                    'Top 5 Solutions'
                  )}

                  {selectedExecution.result_data?.pareto_front && renderSolutionsTable(
                    selectedExecution.result_data.pareto_front,
                    'Pareto Front Solutions'
                  )}

                  <Box sx={{ mt: 2 }}>
                    <Button
                      variant="outlined"
                      startIcon={interpreting ? <CircularProgress size={16} /> : <PsychologyIcon />}
                      onClick={handleInterpret}
                      disabled={interpreting}
                    >
                      {interpreting
                        ? 'Interpreting...'
                        : selectedExecution.interpretation
                          ? 'Re-interpret with AI'
                          : 'Interpret Results with AI'}
                    </Button>
                  </Box>

                  {selectedExecution.interpretation && (
                    <Card sx={{ mt: 2, bgcolor: 'background.paper' }}>
                      <CardContent>
                        <Typography variant="subtitle2" gutterBottom>AI Interpretation</Typography>
                        <Box sx={{
                          '& h1, & h2, & h3, & h4': { mt: 2, mb: 1 },
                          '& p': { mb: 1, fontSize: '0.875rem', lineHeight: 1.6 },
                          '& ul, & ol': { pl: 3, mb: 1, fontSize: '0.875rem' },
                          '& li': { mb: 0.5 },
                          '& table': {
                            width: '100%',
                            borderCollapse: 'collapse',
                            mb: 2,
                            fontSize: '0.875rem',
                          },
                          '& th, & td': {
                            border: '1px solid',
                            borderColor: 'divider',
                            px: 1.5,
                            py: 0.75,
                            textAlign: 'left',
                          },
                          '& th': {
                            bgcolor: 'action.selected',
                            fontWeight: 'bold',
                          },
                          '& code': {
                            bgcolor: 'action.selected',
                            px: 0.5,
                            borderRadius: 0.5,
                            fontSize: '0.8rem',
                            fontFamily: 'monospace',
                          },
                          '& pre': {
                            bgcolor: 'action.selected',
                            p: 1.5,
                            borderRadius: 1,
                            overflow: 'auto',
                            mb: 1,
                          },
                          '& blockquote': {
                            borderLeft: 3,
                            borderColor: 'primary.main',
                            pl: 2,
                            ml: 0,
                            color: 'text.secondary',
                          },
                          '& strong': { fontWeight: 'bold' },
                          '& hr': { my: 2, borderColor: 'divider' },
                        }}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {selectedExecution.interpretation}
                          </ReactMarkdown>
                        </Box>
                      </CardContent>
                    </Card>
                  )}
                </Box>
              )}
            </TabPanel>
          </Box>
        </Paper>
      </Grid>
    </Grid>
  );
}
