import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import HomePage from './pages/HomePage';
import ProjectPage from './pages/ProjectPage';
import SettingsPage from './pages/SettingsPage';

const theme = createTheme({
  palette: {
    mode: 'dark',
    primary: { main: '#00e676' },
    secondary: { main: '#76ff03' },
    background: {
      default: '#0a0e14',
      paper: '#111820',
    },
    text: {
      primary: '#c5cdd8',
      secondary: '#6b7d8e',
    },
    divider: '#1e2a36',
  },
  typography: {
    fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", "Consolas", monospace',
    fontSize: 13,
    h4: { fontWeight: 700, letterSpacing: '-0.02em' },
    h5: { fontWeight: 700, letterSpacing: '-0.01em' },
    h6: { fontWeight: 600 },
    subtitle2: { fontWeight: 600, color: '#00e676', textTransform: 'uppercase', fontSize: '0.7rem', letterSpacing: '0.1em' },
  },
  shape: { borderRadius: 6 },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundColor: '#0a0e14',
          scrollbarWidth: 'thin',
          scrollbarColor: '#1e2a36 #0a0e14',
          '&::-webkit-scrollbar': { width: 6 },
          '&::-webkit-scrollbar-track': { background: '#0a0e14' },
          '&::-webkit-scrollbar-thumb': { background: '#1e2a36', borderRadius: 3 },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          border: '1px solid #1e2a36',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        contained: {
          backgroundColor: '#00e676',
          color: '#0a0e14',
          fontWeight: 700,
          textTransform: 'none',
          '&:hover': { backgroundColor: '#00c853' },
        },
        outlined: {
          borderColor: '#1e2a36',
          color: '#c5cdd8',
          textTransform: 'none',
          '&:hover': { borderColor: '#00e676', color: '#00e676' },
        },
        text: {
          textTransform: 'none',
          color: '#c5cdd8',
          '&:hover': { color: '#00e676' },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            backgroundColor: '#0d1117',
            '& fieldset': { borderColor: '#1e2a36' },
            '&:hover fieldset': { borderColor: '#00e676' },
            '&.Mui-focused fieldset': { borderColor: '#00e676' },
          },
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          fontSize: '0.8rem',
          '&.Mui-selected': { color: '#00e676' },
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        indicator: { backgroundColor: '#00e676' },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundImage: 'none',
          backgroundColor: '#0d1117',
          border: '1px solid #1e2a36',
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          fontSize: '0.75rem',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#0d1117',
          borderBottom: '1px solid #1e2a36',
          backgroundImage: 'none',
        },
      },
    },
    MuiLinearProgress: {
      styleOverrides: {
        root: { backgroundColor: '#1e2a36' },
        bar: { backgroundColor: '#00e676' },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: { border: '1px solid #1e2a36' },
      },
    },
  },
});

function PrivateRoute({ children }) {
  const token = localStorage.getItem('token');
  return token ? children : <Navigate to="/login" />;
}

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            element={
              <PrivateRoute>
                <Layout />
              </PrivateRoute>
            }
          >
            <Route path="/" element={<HomePage />} />
            <Route path="/project/:id" element={<ProjectPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
