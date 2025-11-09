import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import * as pdfjsLib from 'pdfjs-dist';

// Ensure any 2D canvas contexts created downstream (e.g. by rrweb, Konva, pdf.js)
// opt into the willReadFrequently optimization to avoid repeated console warnings.
if (typeof window !== 'undefined') {
  const originalGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, options = {}) {
    if (type === '2d') {
      options = { willReadFrequently: true, ...options };
    }
    return originalGetContext.call(this, type, options);
  };
}

// Configure PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjsLib.version}/build/pdf.worker.min.mjs`;

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);