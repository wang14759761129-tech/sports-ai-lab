import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { PublicFanCatalog } from './PublicFanCatalog';
import './style.css';
import './fan-gold.css';

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PublicFanCatalog><App /></PublicFanCatalog>
  </React.StrictMode>,
);
