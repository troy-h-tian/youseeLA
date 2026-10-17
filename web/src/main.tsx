import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { resolveDataSource } from './data/load';
import './styles.css';

const source = resolveDataSource(window.location.search, import.meta.env.VITE_DATA_SOURCE);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App source={source} />
  </StrictMode>,
);
