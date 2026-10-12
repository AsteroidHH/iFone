import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import '@fontsource/schibsted-grotesk/400.css';
import '@fontsource/schibsted-grotesk/500.css';
import '@fontsource/schibsted-grotesk/700.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource-variable/bricolage-grotesque';
import '@fontsource/silkscreen/400.css';
import './styles/tokens.css';
import './styles/app.css';
import './styles/proof-room.css';
import './styles/tools.css';
import './styles/layers.css';
import './landing/landing.css';
import { App } from './App';

createRoot(document.getElementById('root') as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
