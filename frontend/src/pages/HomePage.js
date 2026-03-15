import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Typography, Button, List, ListItem, ListItemText, ListItemButton,
  ListItemSecondaryAction, Paper, Box, Dialog, DialogTitle,
  DialogContent, DialogActions, TextField, IconButton, Alert,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { apiFetch } from '../api';

export default function HomePage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const loadProjects = async () => {
    try {
      const data = await apiFetch('/projects/');
      if (data) setProjects(data);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    loadProjects();
  }, []);

  const handleCreate = async () => {
    setError('');
    try {
      const project = await apiFetch('/projects/', {
        method: 'POST',
        body: JSON.stringify({ name, description: description || null }),
      });
      if (project) {
        setDialogOpen(false);
        setName('');
        setDescription('');
        navigate(`/project/${project.id}`);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDelete = async (projectId) => {
    try {
      await apiFetch(`/projects/${projectId}`, { method: 'DELETE' });
      setDeleteConfirm(null);
      loadProjects();
    } catch (err) {
      setError(err.message);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric',
    });
  };

  return (
    <>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Your Projects</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setDialogOpen(true)}
        >
          New Project
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper>
        {projects.length === 0 ? (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography color="text.secondary">
              No projects yet. Create your first optimization project to get started.
            </Typography>
          </Box>
        ) : (
          <List>
            {projects.map((project) => (
              <ListItem
                key={project.id}
                disablePadding
                secondaryAction={
                  <IconButton
                    edge="end"
                    color="error"
                    onClick={(e) => {
                      e.stopPropagation();
                      setDeleteConfirm(project);
                    }}
                  >
                    <DeleteIcon />
                  </IconButton>
                }
              >
                <ListItemButton onClick={() => navigate(`/project/${project.id}`)}>
                  <ListItemText
                    primary={project.name}
                    secondary={
                      <>
                        {project.description && <span>{project.description}</span>}
                        {project.description && ' — '}
                        <span style={{ opacity: 0.5 }}>
                          Created {formatDate(project.created_at)}
                        </span>
                      </>
                    }
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        )}
      </Paper>

      {/* Create Project Dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New Optimization Project</DialogTitle>
        <DialogContent>
          <TextField
            label="Project Name"
            fullWidth
            margin="normal"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            required
          />
          <TextField
            label="Description"
            fullWidth
            margin="normal"
            multiline
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate} disabled={!name.trim()}>
            Create
          </Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteConfirm} onClose={() => setDeleteConfirm(null)}>
        <DialogTitle>Delete Project</DialogTitle>
        <DialogContent>
          <Typography>
            Are you sure you want to delete "{deleteConfirm?.name}"? This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteConfirm(null)}>Cancel</Button>
          <Button
            variant="contained"
            color="error"
            onClick={() => handleDelete(deleteConfirm.id)}
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
