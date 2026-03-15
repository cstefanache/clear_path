import React, { useState, useEffect } from 'react';
import {
  Typography, TextField, Button, Paper, Box, MenuItem, Select,
  FormControl, InputLabel, Alert, CircularProgress,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import { apiFetch } from '../api';

const MODEL_OPTIONS = {
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
  anthropic: ['claude-sonnet-4-20250514', 'claude-haiku-4-20250414'],
  gemini: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash'],
  ollama: [], // free-form text input
};

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [anthropicKey, setAnthropicKey] = useState('');
  const [geminiKey, setGeminiKey] = useState('');
  const [ollamaUrl, setOllamaUrl] = useState('');

  // Masked keys from server (for display hints)
  const [maskedKeys, setMaskedKeys] = useState({});

  useEffect(() => {
    const load = async () => {
      try {
        const data = await apiFetch('/settings/');
        if (data) {
          setProvider(data.active_provider || '');
          setModel(data.active_model || '');
          setOllamaUrl(data.ollama_url || '');
          setMaskedKeys({
            openai: data.openai_api_key || null,
            anthropic: data.anthropic_api_key || null,
            gemini: data.gemini_api_key || null,
          });
        }
      } catch (err) {
        setFeedback({ severity: 'error', text: err.message });
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      const body = {
        active_provider: provider || null,
        active_model: model || null,
        ollama_url: ollamaUrl || null,
      };
      // Only send API keys if user typed a new value (not the masked placeholder)
      if (openaiKey && !openaiKey.includes('****')) {
        body.openai_api_key = openaiKey;
      }
      if (anthropicKey && !anthropicKey.includes('****')) {
        body.anthropic_api_key = anthropicKey;
      }
      if (geminiKey && !geminiKey.includes('****')) {
        body.gemini_api_key = geminiKey;
      }

      const data = await apiFetch('/settings/', {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      if (data) {
        setMaskedKeys({
          openai: data.openai_api_key || null,
          anthropic: data.anthropic_api_key || null,
          gemini: data.gemini_api_key || null,
        });
        setOpenaiKey('');
        setAnthropicKey('');
        setGeminiKey('');
      }
      setFeedback({ severity: 'success', text: 'Settings saved successfully.' });
    } catch (err) {
      setFeedback({ severity: 'error', text: err.message });
    } finally {
      setSaving(false);
    }
  };

  const handleProviderChange = (newProvider) => {
    setProvider(newProvider);
    // Reset model when provider changes
    const options = MODEL_OPTIONS[newProvider] || [];
    if (options.length > 0) {
      setModel(options[0]);
    } else {
      setModel('');
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  const modelOptions = MODEL_OPTIONS[provider] || [];

  return (
    <>
      <Typography variant="h4" gutterBottom>Settings</Typography>
      <Paper sx={{ p: 3, maxWidth: 600 }}>
        <Typography variant="h6" gutterBottom>LLM Provider Configuration</Typography>

        {feedback && (
          <Alert severity={feedback.severity} sx={{ mb: 2 }} onClose={() => setFeedback(null)}>
            {feedback.text}
          </Alert>
        )}

        <FormControl fullWidth margin="normal">
          <InputLabel>Active Provider</InputLabel>
          <Select
            value={provider}
            label="Active Provider"
            onChange={(e) => handleProviderChange(e.target.value)}
          >
            <MenuItem value="openai">OpenAI</MenuItem>
            <MenuItem value="anthropic">Anthropic</MenuItem>
            <MenuItem value="gemini">Google Gemini</MenuItem>
            <MenuItem value="ollama">Ollama (Local)</MenuItem>
          </Select>
        </FormControl>

        {/* Model Selection */}
        {provider && (
          provider === 'ollama' ? (
            <TextField
              label="Model Name"
              fullWidth
              margin="normal"
              placeholder="e.g. llama3, mistral, codellama"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
          ) : (
            <FormControl fullWidth margin="normal">
              <InputLabel>Model</InputLabel>
              <Select
                value={model}
                label="Model"
                onChange={(e) => setModel(e.target.value)}
              >
                {modelOptions.map(m => (
                  <MenuItem key={m} value={m}>{m}</MenuItem>
                ))}
              </Select>
            </FormControl>
          )
        )}

        <Box sx={{ mt: 2 }}>
          <Typography variant="subtitle2" color="text.secondary" gutterBottom>
            API Keys
          </Typography>
        </Box>

        <TextField
          label="OpenAI API Key"
          type="password"
          fullWidth
          margin="normal"
          placeholder={maskedKeys.openai ? `Current: ${maskedKeys.openai}` : 'Enter your OpenAI API key'}
          value={openaiKey}
          onChange={(e) => setOpenaiKey(e.target.value)}
          helperText={maskedKeys.openai ? `Saved: ${maskedKeys.openai}` : 'Not configured'}
        />
        <TextField
          label="Anthropic API Key"
          type="password"
          fullWidth
          margin="normal"
          placeholder={maskedKeys.anthropic ? `Current: ${maskedKeys.anthropic}` : 'Enter your Anthropic API key'}
          value={anthropicKey}
          onChange={(e) => setAnthropicKey(e.target.value)}
          helperText={maskedKeys.anthropic ? `Saved: ${maskedKeys.anthropic}` : 'Not configured'}
        />
        <TextField
          label="Gemini API Key"
          type="password"
          fullWidth
          margin="normal"
          placeholder={maskedKeys.gemini ? `Current: ${maskedKeys.gemini}` : 'Enter your Gemini API key'}
          value={geminiKey}
          onChange={(e) => setGeminiKey(e.target.value)}
          helperText={maskedKeys.gemini ? `Saved: ${maskedKeys.gemini}` : 'Not configured'}
        />
        <TextField
          label="Ollama Server URL"
          fullWidth
          margin="normal"
          placeholder="http://localhost:11434"
          value={ollamaUrl}
          onChange={(e) => setOllamaUrl(e.target.value)}
        />

        <Button
          variant="contained"
          startIcon={<SaveIcon />}
          sx={{ mt: 2 }}
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Saving...' : 'Save Settings'}
        </Button>
      </Paper>
    </>
  );
}
