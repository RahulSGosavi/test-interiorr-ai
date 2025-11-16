import React, { useEffect, useState, useRef } from 'react';
import * as pdfjsLib from 'pdfjs-dist';

const PrintView = ({ pdfDoc, pageStates, file, onClose }) => {
  const [renderedPages, setRenderedPages] = useState([]);
  const [isRendering, setIsRendering] = useState(true);
  const containerRef = useRef(null);

  useEffect(() => {
    const renderAllPages = async () => {
      if (!pdfDoc) return;
      
      setIsRendering(true);
      const pages = [];
      
      // Calculate appropriate scale based on screen width
      // For screen view: fit to viewport width (max 1200px)
      // For print: use higher DPI (2.0 scale)
      const screenMaxWidth = Math.min(window.innerWidth - 80, 1200); // Leave padding
      const PRINT_SCALE = 2.0; // High quality for printing
      
      // Get first page to calculate scale
      const firstPage = await pdfDoc.getPage(1);
      const firstViewport = firstPage.getViewport({ scale: 1.0 });
      const screenScale = screenMaxWidth / firstViewport.width;
      const displayScale = Math.min(screenScale, 1.5); // Cap at 1.5x for screen

      for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
        try {
          const page = await pdfDoc.getPage(pageNum);
          const rotation = page.rotate || 0;
          
          // Render at print quality for actual printing
          const printViewport = page.getViewport({ scale: PRINT_SCALE, rotation });
          
          // Calculate display dimensions (for screen view)
          const baseViewport = page.getViewport({ scale: 1.0, rotation: 0 });
          const displayWidth = baseViewport.width * displayScale;
          const displayHeight = baseViewport.height * displayScale;
          
          const canvas = document.createElement('canvas');
          const context = canvas.getContext('2d', { willReadFrequently: true });
          canvas.width = printViewport.width;
          canvas.height = printViewport.height;
          
          await page.render({ canvasContext: context, viewport: printViewport }).promise;
          
          pages.push({
            pageNum,
            imageData: canvas.toDataURL('image/png'),
            // Display dimensions for screen view
            displayWidth,
            displayHeight,
            // Print dimensions (actual canvas size)
            printWidth: printViewport.width,
            printHeight: printViewport.height,
            rotation,
            annotations: pageStates[pageNum]?.shapes || [],
            // Store original dimensions for annotation positioning
            originalWidth: baseViewport.width,
            originalHeight: baseViewport.height,
          });
        } catch (error) {
          console.error(`Error rendering page ${pageNum}:`, error);
        }
      }

      setRenderedPages(pages);
      setIsRendering(false);
    };

    renderAllPages();
  }, [pdfDoc, pageStates]);

  useEffect(() => {
    if (!isRendering && renderedPages.length > 0) {
      // Small delay to ensure all images are loaded
      setTimeout(() => {
        window.print();
      }, 500);
    }
  }, [isRendering, renderedPages]);

  const renderAnnotation = (shape, pageWidth, pageHeight, scale) => {
    const style = {
      position: 'absolute',
      pointerEvents: 'none',
    };

    switch (shape.type) {
      case 'rect': {
        return (
          <div
            key={shape.id}
            style={{
              ...style,
              left: `${(shape.x / pageWidth) * 100}%`,
              top: `${(shape.y / pageHeight) * 100}%`,
              width: `${(shape.width / pageWidth) * 100}%`,
              height: `${(shape.height / pageHeight) * 100}%`,
              border: `${(shape.strokeWidth || 1) * scale}px solid ${shape.stroke || '#3B82F6'}`,
              borderStyle: shape.dash?.length ? 'dashed' : 'solid',
              boxSizing: 'border-box',
            }}
          />
        );
      }
      case 'circle': {
        const radius = shape.radius || 0;
        return (
          <div
            key={shape.id}
            style={{
              ...style,
              left: `${((shape.x - radius) / pageWidth) * 100}%`,
              top: `${((shape.y - radius) / pageHeight) * 100}%`,
              width: `${((radius * 2) / pageWidth) * 100}%`,
              height: `${((radius * 2) / pageHeight) * 100}%`,
              border: `${(shape.strokeWidth || 1) * scale}px solid ${shape.stroke || '#3B82F6'}`,
              borderStyle: shape.dash?.length ? 'dashed' : 'solid',
              borderRadius: '50%',
              boxSizing: 'border-box',
            }}
          />
        );
      }
      case 'line':
      case 'arrow':
      case 'free':
      case 'polygon': {
        if (!shape.points || shape.points.length < 4) return null;
        
        const points = [];
        for (let i = 0; i < shape.points.length; i += 2) {
          points.push({
            x: (shape.points[i] / pageWidth) * 100,
            y: (shape.points[i + 1] / pageHeight) * 100,
          });
        }

        const pathData = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x}% ${p.y}%`).join(' ');
        const isClosed = shape.type === 'polygon';
        
        return (
          <svg
            key={shape.id}
            style={{
              ...style,
              width: '100%',
              height: '100%',
              top: 0,
              left: 0,
            }}
            preserveAspectRatio="none"
          >
            <path
              d={`${pathData}${isClosed ? ' Z' : ''}`}
              stroke={shape.stroke || '#3B82F6'}
              strokeWidth={(shape.strokeWidth || 1) * scale}
              fill="none"
              strokeDasharray={shape.dash?.length ? shape.dash.map(d => d * scale).join(',') : undefined}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {shape.type === 'arrow' && points.length >= 2 && (
              <polygon
                points={(() => {
                  const start = points[points.length - 2];
                  const end = points[points.length - 1];
                  const angle = Math.atan2(end.y - start.y, end.x - start.x);
                  const headLength = 18 * scale;
                  const headWidth = 10 * scale;
                  const left = {
                    x: end.x - headLength * Math.cos(angle - Math.PI / 6),
                    y: end.y - headLength * Math.sin(angle - Math.PI / 6),
                  };
                  const right = {
                    x: end.x - headLength * Math.cos(angle + Math.PI / 6),
                    y: end.y - headLength * Math.sin(angle + Math.PI / 6),
                  };
                  return `${end.x},${end.y} ${left.x},${left.y} ${right.x},${right.y}`;
                })()}
                fill={shape.stroke || '#3B82F6'}
              />
            )}
          </svg>
        );
      }
      case 'text': {
        if (!shape.text) return null;
        return (
          <div
            key={shape.id}
            style={{
              ...style,
              left: `${(shape.x / pageWidth) * 100}%`,
              top: `${(shape.y / pageHeight) * 100}%`,
              color: shape.stroke || '#1f2937',
              fontSize: `${(shape.fontSize || 18) * scale}px`,
              fontFamily: 'Arial, sans-serif',
              whiteSpace: 'nowrap',
            }}
          >
            {shape.text}
          </div>
        );
      }
      case 'ruler': {
        if (!shape.start || !shape.end) return null;
        return (
          <svg
            key={shape.id}
            style={{
              ...style,
              width: '100%',
              height: '100%',
              top: 0,
              left: 0,
            }}
            preserveAspectRatio="none"
          >
            <line
              x1={`${(shape.start.x / pageWidth) * 100}%`}
              y1={`${(shape.start.y / pageHeight) * 100}%`}
              x2={`${(shape.end.x / pageWidth) * 100}%`}
              y2={`${(shape.end.y / pageHeight) * 100}%`}
              stroke={shape.stroke || '#3B82F6'}
              strokeWidth={(shape.strokeWidth || 1) * scale}
              strokeDasharray={shape.dash?.length ? shape.dash.map(d => d * scale).join(',') : undefined}
            />
            {shape.label && shape.midpoint && (
              <text
                x={`${(shape.midpoint.x / pageWidth) * 100}%`}
                y={`${(shape.midpoint.y / pageHeight) * 100}%`}
                fill={shape.stroke || '#3B82F6'}
                fontSize={`${12 * scale}px`}
                textAnchor="middle"
                dominantBaseline="middle"
              >
                {shape.label}
              </text>
            )}
          </svg>
        );
      }
      case 'angle': {
        if (!shape.vertex || !shape.pointA || !shape.pointB) return null;
        return (
          <svg
            key={shape.id}
            style={{
              ...style,
              width: '100%',
              height: '100%',
              top: 0,
              left: 0,
            }}
            preserveAspectRatio="none"
          >
            <line
              x1={`${(shape.vertex.x / pageWidth) * 100}%`}
              y1={`${(shape.vertex.y / pageHeight) * 100}%`}
              x2={`${(shape.pointA.x / pageWidth) * 100}%`}
              y2={`${(shape.pointA.y / pageHeight) * 100}%`}
              stroke={shape.stroke || '#3B82F6'}
              strokeWidth={(shape.strokeWidth || 1) * scale}
              strokeDasharray={shape.dash?.length ? shape.dash.map(d => d * scale).join(',') : undefined}
            />
            <line
              x1={`${(shape.vertex.x / pageWidth) * 100}%`}
              y1={`${(shape.vertex.y / pageHeight) * 100}%`}
              x2={`${(shape.pointB.x / pageWidth) * 100}%`}
              y2={`${(shape.pointB.y / pageHeight) * 100}%`}
              stroke={shape.stroke || '#3B82F6'}
              strokeWidth={(shape.strokeWidth || 1) * scale}
              strokeDasharray={shape.dash?.length ? shape.dash.map(d => d * scale).join(',') : undefined}
            />
            {shape.label && shape.labelPosition && (
              <text
                x={`${(shape.labelPosition.x / pageWidth) * 100}%`}
                y={`${(shape.labelPosition.y / pageHeight) * 100}%`}
                fill={shape.stroke || '#3B82F6'}
                fontSize={`${12 * scale}px`}
                textAnchor="middle"
                dominantBaseline="middle"
              >
                {shape.label}
              </text>
            )}
          </svg>
        );
      }
      default:
        return null;
    }
  };

  if (isRendering) {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-white p-6 rounded-lg shadow-xl">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-700">Preparing pages for printing...</p>
            <p className="text-sm text-gray-500 mt-2">Rendering {renderedPages.length} of {pdfDoc?.numPages || 0} pages</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <style>{`
        @media print {
          body * {
            visibility: hidden;
          }
          .print-container, .print-container * {
            visibility: visible;
          }
          .print-container {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
          }
          .print-page {
            page-break-after: always;
            page-break-inside: avoid;
            width: 100% !important;
            max-width: 100% !important;
            height: auto !important;
          }
          .print-page img {
            width: 100% !important;
            height: auto !important;
            max-width: 100% !important;
          }
          .print-page:last-child {
            page-break-after: auto;
          }
          .no-print {
            display: none !important;
          }
        }
        @media screen {
          .print-container {
            background: #f5f5f5;
            padding: 20px;
            min-height: 100vh;
            width: 100%;
            box-sizing: border-box;
          }
          .print-page {
            background: white;
            margin: 0 auto 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            max-width: 100%;
            box-sizing: border-box;
          }
          .print-page img {
            max-width: 100%;
            height: auto;
            display: block;
          }
        }
      `}</style>
      
      <div className="no-print fixed top-4 right-4 z-50">
        <button
          onClick={onClose}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg hover:bg-blue-700"
        >
          Close Print View
        </button>
      </div>

      <div ref={containerRef} className="print-container">
        {renderedPages.map((page) => {
          // Use original dimensions for annotation positioning (matches canvas coordinate system)
          const annotationWidth = page.originalWidth || page.displayWidth;
          const annotationHeight = page.originalHeight || page.displayHeight;
          // Scale factor: how much the display is scaled from original
          const displayScale = page.displayWidth / annotationWidth;
          
          return (
            <div
              key={page.pageNum}
              className="print-page"
              style={{
                width: `${page.displayWidth}px`,
                maxWidth: '100%',
                position: 'relative',
                margin: '0 auto',
              }}
            >
              <div style={{ position: 'relative', width: '100%' }}>
                <img
                  src={page.imageData}
                  alt={`Page ${page.pageNum}`}
                  style={{
                    width: '100%',
                    height: 'auto',
                    display: 'block',
                  }}
                  onLoad={(e) => {
                    // Update overlay height to match actual image height after load
                    const img = e.target;
                    const overlay = img.nextElementSibling;
                    if (overlay) {
                      overlay.style.height = `${img.offsetHeight}px`;
                    }
                  }}
                />
                <div
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: `${page.displayHeight}px`,
                    pointerEvents: 'none',
                  }}
                >
                  {page.annotations.map((shape) =>
                    renderAnnotation(shape, annotationWidth, annotationHeight, displayScale)
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
};

export default PrintView;

