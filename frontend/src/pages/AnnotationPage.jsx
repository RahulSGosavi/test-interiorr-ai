import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import * as pdfjsLib from "pdfjs-dist";
import { filesAPI, annotationsAPI } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Home, Menu, FileText } from "lucide-react";
import AnnotationToolbar from "@/components/AnnotationToolbar";
import PropertiesPanel from "@/components/PropertiesPanel";
import CadCanvasEditor from "@/components/CadCanvasEditor";
import { PDFDocument, StandardFonts, rgb } from "pdf-lib";
import api from "@/lib/api";

const hexToPdfColor = (hex) => {
  if (!hex) {
    return rgb(0, 0, 0);
  }
  const normalized = hex.replace("#", "");
  const expanded = normalized.length === 3 ? normalized.split("").map((c) => c + c).join("") : normalized;
  const value = parseInt(expanded, 16);
  const r = ((value >> 16) & 255) / 255;
  const g = ((value >> 8) & 255) / 255;
  const b = (value & 255) / 255;
  return rgb(r, g, b);
};

const buildSvgPath = (points) => {
  if (!points || points.length < 4) return null;
  const [startX, startY, ...rest] = points;
  let path = `M ${startX} ${startY}`;
  for (let i = 0; i < rest.length; i += 2) {
    path += ` L ${rest[i]} ${rest[i + 1]}`;
  }
  return path;
};

const mapDashArray = (dash, scale) => {
  if (!dash || !dash.length) return undefined;
  return dash.map((segment) => Math.max(segment * scale, 0.1));
};

const createLayerId = () =>
  (crypto?.randomUUID ? crypto.randomUUID() : `layer-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`);

const createDefaultLayerState = () => {
  const id = createLayerId();
  return {
    activeLayerId: id,
    items: [{ id, name: "Layer 1", visible: true }],
  };
};

const normalizeLayerState = (state) => {
  if (!state?.items?.length) {
    return createDefaultLayerState();
  }
  const sanitizedItems = state.items.map((layer, index) => ({
    id: layer.id || createLayerId(),
    name: layer.name || `Layer ${index + 1}`,
    visible: layer.visible !== false,
  }));
  const fallback = sanitizedItems.find((layer) => layer.visible) ?? sanitizedItems[0];
  const activeLayerId = sanitizedItems.some((layer) => layer.id === state.activeLayerId && layer.visible !== false)
    ? state.activeLayerId
    : fallback.id;
  return {
    activeLayerId,
    items: sanitizedItems,
  };
};

const createEmptyPageState = () => ({
  shapes: [],
  stagePosition: { x: 0, y: 0 },
  layers: createDefaultLayerState(),
});

// Helper function to check if a file is an image
const checkIfImageFile = (fileName, fileType) => {
  const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'];
  const imageMimeTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp'];
  const ext = fileName?.toLowerCase().substring(fileName.lastIndexOf('.'));
  return imageExtensions.includes(ext) || imageMimeTypes.includes(fileType?.toLowerCase());
};

// Helper function to convert image ArrayBuffer to PDF
const convertImageToPdf = async (imageBytes, imageType = 'image/png') => {
  const pdfDoc = await PDFDocument.create();
  
  let image;
  if (imageType.includes('jpeg') || imageType.includes('jpg')) {
    image = await pdfDoc.embedJpg(imageBytes);
  } else if (imageType.includes('png')) {
    image = await pdfDoc.embedPng(imageBytes);
  } else {
    // For other formats, try to embed as PNG
    try {
      image = await pdfDoc.embedPng(imageBytes);
    } catch {
      // If PNG fails, try JPEG
      image = await pdfDoc.embedJpg(imageBytes);
    }
  }
  
  const page = pdfDoc.addPage([image.width, image.height]);
  page.drawImage(image, {
    x: 0,
    y: 0,
    width: image.width,
    height: image.height,
  });
  
  return await pdfDoc.save();
};

// Helper function to convert canvas to PDF
const convertCanvasToPdf = async (canvasDataUrl, width, height) => {
  const pdfDoc = await PDFDocument.create();
  
  // Convert data URL to image bytes
  const imageBytes = await fetch(canvasDataUrl).then(res => res.arrayBuffer());
  const image = await pdfDoc.embedPng(imageBytes);
  
  const page = pdfDoc.addPage([width, height]);
  page.drawImage(image, {
    x: 0,
    y: 0,
    width,
    height,
  });
  
  return await pdfDoc.save();
};

const AnnotationPage = () => {
  const { fileId } = useParams();
  const navigate = useNavigate();
  const canvasRef = useRef(null);
  const currentPageRef = useRef(1);

  const [file, setFile] = useState(null);
  const [pdfDoc, setPdfDoc] = useState(null);
  const [pageImage, setPageImage] = useState(null);
  const [pageDimensions, setPageDimensions] = useState({ width: 0, height: 0 });
  const [isImageFile, setIsImageFile] = useState(false);

  const [activeTool, setActiveTool] = useState("select");
  const [zoom, setZoom] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState(1);
  const [strokeWidth, setStrokeWidth] = useState(1);
  const [strokeColor, setStrokeColor] = useState("#3B82F6");
  const [strokeStyle, setStrokeStyle] = useState("solid");

  const [pageStates, setPageStates] = useState({});
  const [isSaved, setIsSaved] = useState(true);
  const [isDownloading, setIsDownloading] = useState(false);
  const [measurementUnit, setMeasurementUnit] = useState("cm");
  const [unitsPerPixel, setUnitsPerPixel] = useState(0.1);
  const [pageMetrics, setPageMetrics] = useState({});
  const [pageRotationOverrides, setPageRotationOverrides] = useState({});
  const [isAutoSaving, setIsAutoSaving] = useState(false);

  const [canvasStatus, setCanvasStatus] = useState({
    loading: true,
    message: "Preparing workspace...",
  });
  const defaultPageStateRef = useRef(createEmptyPageState());
  const autoSaveTimerRef = useRef(null);

  const handleCanvasLoadingChange = useCallback((loading, message) => {
    setCanvasStatus({
      loading,
      message: message || "",
    });
  }, []);

  const notifyIfBusy = useCallback(() => {
    if (canvasStatus.loading || !pageImage) {
      const msg = canvasStatus.message || "Preparing workspace...";
      toast.info(msg);
      return true;
    }
    return false;
  }, [canvasStatus.loading, canvasStatus.message, pageImage]);

  const controlsDisabled = canvasStatus.loading || isDownloading || !pageImage;

  const currentPageState = pageStates[currentPage];
  const safePageState = currentPageState ?? defaultPageStateRef.current;
  const currentLayerState = safePageState?.layers || defaultPageStateRef.current.layers;
  const hiddenLayerIds = currentLayerState.items.filter((layer) => !layer.visible).map((layer) => layer.id);
  const manualRotation = pageRotationOverrides[currentPage] || 0;

  useEffect(() => {
    currentPageRef.current = currentPage;
  }, [currentPage]);

  useEffect(() => {
    setPageRotationOverrides({});
  }, [fileId]);

  useEffect(() => {
    setPageStates((prev) => {
      const existing = prev[currentPage];
      if (existing) {
        if (existing.layers?.items?.length) {
          return prev;
        }
        return {
          ...prev,
          [currentPage]: {
            ...existing,
            layers: normalizeLayerState(existing.layers),
          },
        };
      }
      return {
        ...prev,
        [currentPage]: createEmptyPageState(),
      };
    });
  }, [currentPage]);

  const loadAnnotations = useCallback(async () => {
    try {
      const response = await annotationsAPI.getAll(fileId);
      if (response.data.length > 0) {
        const saved = JSON.parse(response.data[0].annotation_json || "{}");
        const normalized = Object.fromEntries(
          Object.entries(saved).map(([page, state]) => [
            page,
            {
              shapes: state?.shapes || state?.objects || [],
              stagePosition: state?.stagePosition || state?.stage || { x: 0, y: 0 },
              layers: normalizeLayerState(state?.layers),
            },
          ])
        );
        setPageStates(normalized);
        setIsSaved(true);
      }
    } catch (error) {
      console.error("Failed to load annotations", error);
    }
  }, [fileId]);

  const renderPdfPage = useCallback(async (doc, pageNumber) => {
    setCanvasStatus({ loading: true, message: "Rendering page..." });
    try {
      const page = await doc.getPage(pageNumber);
      
      // Get page rotation from metadata (common in CAD-generated PDFs) and user overrides
      const manualRotation = pageRotationOverrides[pageNumber] || 0;
      const rotation = ((page.rotate || 0) + manualRotation) % 360;
      
      // Get viewport with rotation accounted for
      const viewport = page.getViewport({ scale: 1.5, rotation });
      
      // Get actual page dimensions (before rotation) for reference
      const viewportNoRotation = page.getViewport({ scale: 1.0, rotation: 0 });
      const actualPageWidth = viewportNoRotation.width;
      const actualPageHeight = viewportNoRotation.height;
      
      // Ensure canvas dimensions match viewport exactly
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d", { willReadFrequently: true });
      canvas.width = Math.ceil(viewport.width);
      canvas.height = Math.ceil(viewport.height);
      
      // Render the full page to canvas
      await page.render({ canvasContext: context, viewport }).promise;
      
      // Verify canvas was fully rendered
      const imageData = canvas.toDataURL();
      if (!imageData || imageData === 'data:,') {
        throw new Error('Failed to render PDF page to canvas');
      }
      
      setPageImage(imageData);
      const renderedWidth = canvas.width;
      const renderedHeight = canvas.height;
      
      setPageDimensions({ width: renderedWidth, height: renderedHeight });
      setPageMetrics((prev) => ({
        ...prev,
        [pageNumber]: {
          width: renderedWidth,
          height: renderedHeight,
          scale: viewport.scale,
          transform: viewport.transform,
          rotation: rotation,
          actualWidth: actualPageWidth,
          actualHeight: actualPageHeight,
        },
      }));
      setCanvasStatus({ loading: false, message: "" });
    } catch (error) {
      console.error("Failed to render page", error);
      setCanvasStatus({ loading: false, message: "Failed to render page" });
    }
  }, [pageRotationOverrides]);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const response = await filesAPI.getOne(fileId);
        const fileData = response.data;
        setFile(fileData);
        
        // Check if file is an image
        const isImage = checkIfImageFile(fileData?.name, fileData?.file_type);
        setIsImageFile(isImage);
        
        await loadAnnotations();

        setCanvasStatus({ loading: true, message: isImage ? "Converting image to PDF..." : "Loading PDF..." });
        const fileResponse = await filesAPI.download(fileId);
        
        if (!fileResponse.data || fileResponse.data.byteLength === 0) {
          throw new Error("Empty file received");
        }
        
        let pdfBytes = fileResponse.data;
        
        // If it's an image, convert it to PDF first
        if (isImage) {
          toast.info("Converting image to PDF for annotation...");
          const imageType = fileData?.file_type || 'image/png';
          pdfBytes = await convertImageToPdf(fileResponse.data, imageType);
        }
        
        const doc = await pdfjsLib.getDocument({ data: pdfBytes }).promise;
        setPdfDoc(doc);
        setNumPages(doc.numPages);
        setCanvasStatus({ loading: false, message: null });
      } catch (error) {
        console.error("Failed to load PDF:", error);
        setCanvasStatus({ loading: false, message: null });
        
        if (error?.response?.status === 404) {
          toast.error("File not found. Please upload the file again.");
        } else if (error?.response?.status === 401) {
          toast.error("Session expired. Please login again.");
        } else if (error?.message?.includes("Invalid PDF")) {
          toast.error("Invalid file format. Please upload a valid PDF or image file.");
        } else {
          toast.error(`Failed to load document: ${error?.message || "Unknown error"}`);
        }
      }
    };
    bootstrap();
  }, [fileId, loadAnnotations]);

  useEffect(() => {
    if (pdfDoc) {
      renderPdfPage(pdfDoc, currentPage);
    }
  }, [pdfDoc, currentPage, renderPdfPage]);

  const persistCurrentPage = useCallback(() => {
    const snapshot = canvasRef.current?.exportState?.();
    if (snapshot) {
      const layers = pageStates[currentPageRef.current]?.layers || createDefaultLayerState();
      const enrichedSnapshot = {
        ...snapshot,
        layers,
      };
      setPageStates((prev) => ({
        ...prev,
        [currentPageRef.current]: enrichedSnapshot,
      }));
      return enrichedSnapshot;
    }
    return pageStates[currentPageRef.current];
  }, [pageStates]);

  const handlePageStateChange = useCallback((snapshot) => {
    if (!snapshot) return;
    setPageStates((prev) => {
      const existing = prev[currentPageRef.current] ?? createEmptyPageState();
      const layers = snapshot.layers
        ? normalizeLayerState(snapshot.layers)
        : existing.layers || createDefaultLayerState();
      return {
        ...prev,
        [currentPageRef.current]: {
          ...existing,
          ...snapshot,
          layers,
        },
      };
    });
    setIsSaved(false);
  }, []);

  const handleUndo = useCallback(() => {
    if (notifyIfBusy()) return;
    if (canvasRef.current?.undo?.()) {
      setIsSaved(false);
    } else {
      toast.info("Nothing to undo");
    }
  }, [notifyIfBusy]);

  const handleRedo = useCallback(() => {
    if (notifyIfBusy()) return;
    if (canvasRef.current?.redo?.()) {
      setIsSaved(false);
    } else {
      toast.info("Nothing to redo");
    }
  }, [notifyIfBusy]);

  const handleCopySelection = useCallback(() => {
    if (notifyIfBusy()) return;
    if (!canvasRef.current?.duplicateSelection?.()) {
      toast.info("Select an element to duplicate");
    } else {
      setIsSaved(false);
    }
  }, [notifyIfBusy]);

  const handleRotateSelection = useCallback(() => {
    if (notifyIfBusy()) return;
    if (!canvasRef.current?.rotateSelection?.(15)) {
      toast.info("Select an element to rotate");
    } else {
      setIsSaved(false);
    }
  }, [notifyIfBusy]);

  const handleScaleSelection = useCallback(() => {
    if (notifyIfBusy()) return;
    if (!canvasRef.current?.scaleSelection?.(1.1)) {
      toast.info("Select an element to scale");
    } else {
      setIsSaved(false);
    }
  }, [notifyIfBusy]);

  const updateLayerState = useCallback(
    (page, updater) => {
      setPageStates((prev) => {
        const existing = prev[page] ?? createEmptyPageState();
        const nextLayers = normalizeLayerState(updater(existing.layers ?? createDefaultLayerState()));
        return {
          ...prev,
          [page]: {
            ...existing,
            layers: nextLayers,
          },
        };
      });
      setIsSaved(false);
    },
    []
  );

  const handleAddLayer = useCallback(() => {
    updateLayerState(currentPage, (current) => {
      const nextIndex = current.items.length + 1;
      const newLayer = { id: createLayerId(), name: `Layer ${nextIndex}`, visible: true };
      return {
        activeLayerId: newLayer.id,
        items: [...current.items, newLayer],
      };
    });
  }, [currentPage, updateLayerState]);

  const handleSelectLayer = useCallback(
    (layerId) => {
      updateLayerState(currentPage, (current) => {
        if (current.activeLayerId === layerId) return current;
        const items = current.items.map((layer) =>
          layer.id === layerId ? { ...layer, visible: true } : layer
        );
        return {
          activeLayerId: layerId,
          items,
        };
      });
    },
    [currentPage, updateLayerState]
  );

  const handleToggleLayerVisibility = useCallback(
    (layerId) => {
      updateLayerState(currentPage, (current) => {
        const target = current.items.find((layer) => layer.id === layerId);
        if (!target) return current;
        const visibleCount = current.items.filter((layer) => layer.visible).length;
        if (visibleCount === 1 && target.visible) {
          return current;
        }
        const items = current.items.map((layer) =>
          layer.id === layerId ? { ...layer, visible: !layer.visible } : layer
        );
        const updatedTarget = items.find((layer) => layer.id === layerId);
        let activeLayerId = current.activeLayerId;
        if (!updatedTarget?.visible) {
          const fallbackLayer = items.find((layer) => layer.visible) ?? updatedTarget;
          activeLayerId = fallbackLayer?.id || current.activeLayerId;
        }
        return {
          activeLayerId,
          items,
        };
      });
    },
    [currentPage, updateLayerState]
  );

  const handleDeleteSelection = useCallback(() => {
    if (notifyIfBusy()) return;
    if (!canvasRef.current?.deleteSelection?.()) {
      toast.info("Select an element to delete");
    } else {
      setIsSaved(false);
    }
  }, [notifyIfBusy]);

  const handleToolSelect = useCallback(
    (tool) => {
      if (notifyIfBusy()) return;
      if (tool === "delete") {
        handleDeleteSelection();
        return;
      }
      setActiveTool(tool);
    },
    [handleDeleteSelection, notifyIfBusy]
  );

  useEffect(() => {
    const handleKeyPress = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (notifyIfBusy()) return;

      const key = e.key.toUpperCase();
      const shortcuts = {
        S: "select",
        L: "line",
        R: "rectangle",
        C: "circle",
        A: "arrow",
        P: "polygon",
        F: "freehand",
        T: "text",
        M: "pan",
        E: "eraser",
        G: "angle",
        U: "ruler",
      };

      if ((e.ctrlKey || e.metaKey) && key === "Z") {
        e.preventDefault();
        handleUndo();
        return;
      }

      if ((e.ctrlKey || e.metaKey) && key === "Y") {
        e.preventDefault();
        handleRedo();
        return;
      }

      if ((e.ctrlKey || e.metaKey) && key === "D") {
        e.preventDefault();
        handleCopySelection();
        return;
      }

      if ((e.ctrlKey || e.metaKey) && key === "R") {
        e.preventDefault();
        handleRotateSelection();
        return;
      }

      if ((e.ctrlKey || e.metaKey) && key === "S") {
        e.preventDefault();
        handleScaleSelection();
        return;
      }

      if (key === "DELETE" || key === "BACKSPACE") {
        e.preventDefault();
        handleDeleteSelection();
        return;
      }

      if (key === " ") {
        e.preventDefault();
        setActiveTool("pan");
        return;
      }

      const tool = shortcuts[key];
      if (tool) {
        setActiveTool(tool);
      }
    };

    window.addEventListener("keydown", handleKeyPress);
    return () => window.removeEventListener("keydown", handleKeyPress);
  }, [
    handleCopySelection,
    handleDeleteSelection,
    handleRedo,
    handleRotateSelection,
    handleScaleSelection,
    handleUndo,
    notifyIfBusy,
  ]);

  const handleSave = useCallback(async () => {
    if (notifyIfBusy()) return;
    try {
      const snapshot = persistCurrentPage();
      const payload = snapshot
        ? {
            ...pageStates,
            [currentPageRef.current]: snapshot,
          }
        : pageStates;

      await annotationsAPI.save(fileId, {
        annotation_json: JSON.stringify(payload),
      });
      setIsSaved(true);
      toast.success("Annotations saved successfully");
    } catch (error) {
      toast.error("Failed to save annotations");
    }
  }, [fileId, notifyIfBusy, pageStates, persistCurrentPage]);

  useEffect(() => {
    if (isSaved) {
      setIsAutoSaving(false);
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
        autoSaveTimerRef.current = null;
      }
      return;
    }
    setIsAutoSaving(true);
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }
    autoSaveTimerRef.current = setTimeout(() => {
      handleSave();
    }, 5000);
    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
        autoSaveTimerRef.current = null;
      }
    };
  }, [handleSave, isSaved]);

  const handleDownload = useCallback(async () => {
    if (isDownloading || notifyIfBusy()) return;
    try {
      setIsDownloading(true);
      toast.info("Preparing CAD export...");

      // Get current page state
      const latestSnapshot = canvasRef.current?.exportState?.();
      const exportStates = latestSnapshot
        ? {
            ...pageStates,
            [currentPageRef.current]: latestSnapshot,
          }
        : pageStates;

      // Download original file
      const response = await filesAPI.download(fileId);
      
      if (!response.data || response.data.byteLength === 0) {
        throw new Error("Empty file received");
      }
      
      const fileBytes = response.data;
      const pdfJsDoc = await pdfjsLib.getDocument({ data: fileBytes }).promise;
      const pdfLibDoc = await PDFDocument.create();
      
      const numPages = pdfJsDoc.numPages;
      const projectName = file?.name?.replace?.(/\.[^/.]+$/, "") || "annotated";
      
      const RENDER_SCALE = 1.5;
      
      // Process each page
      for (let pageNum = 1; pageNum <= numPages; pageNum++) {
        toast.info(`Processing page ${pageNum}/${numPages}...`);
        
        const pdfJsPage = await pdfJsDoc.getPage(pageNum);
        const manualRotationForPage = pageRotationOverrides[pageNum] || 0;
        const rotation = ((pdfJsPage.rotate || 0) + manualRotationForPage) % 360;
        
        const viewport = pdfJsPage.getViewport({ scale: RENDER_SCALE, rotation });
        const unrotatedViewport = pdfJsPage.getViewport({ scale: 1.0, rotation: 0 });
        
        const pdfCanvas = document.createElement("canvas");
        const pdfContext = pdfCanvas.getContext("2d", { willReadFrequently: true });
        pdfCanvas.width = Math.ceil(viewport.width);
        pdfCanvas.height = Math.ceil(viewport.height);
        
        await pdfJsPage.render({ canvasContext: pdfContext, viewport }).promise;
        
        const snapshot = exportStates[pageNum];
        const shapes = snapshot?.shapes || [];
        
        const compositeCanvas = document.createElement("canvas");
        const compositeContext = compositeCanvas.getContext("2d", { willReadFrequently: true });
        compositeCanvas.width = pdfCanvas.width;
        compositeCanvas.height = pdfCanvas.height;
        
        compositeContext.drawImage(pdfCanvas, 0, 0, pdfCanvas.width, pdfCanvas.height);
        
        // Draw all annotations
        for (const shape of shapes) {
          if (!shape || !shape.type) continue;
          
          compositeContext.save();
          compositeContext.strokeStyle = shape.stroke || "#1d4ed8";
          compositeContext.fillStyle = shape.stroke || "#1d4ed8";
          compositeContext.lineWidth = shape.strokeWidth || 2;
          
          if (shape.dash && shape.dash.length === 2) {
            compositeContext.setLineDash([shape.dash[0], shape.dash[1]]);
          } else {
            compositeContext.setLineDash([]);
          }
          
          switch (shape.type) {
            case "rect": {
              compositeContext.strokeRect(
                shape.x || 0,
                shape.y || 0,
                shape.width || 0,
                shape.height || 0
              );
              break;
            }
            case "circle": {
              compositeContext.beginPath();
              compositeContext.arc(
                shape.x || 0,
                shape.y || 0,
                shape.radius || 0,
                0,
                Math.PI * 2
              );
              compositeContext.stroke();
              break;
            }
            case "line":
            case "arrow":
            case "free": {
              if (shape.points && shape.points.length >= 4) {
                compositeContext.beginPath();
                compositeContext.moveTo(shape.points[0], shape.points[1]);
                for (let i = 2; i < shape.points.length; i += 2) {
                  if (i + 1 < shape.points.length) {
                    compositeContext.lineTo(shape.points[i], shape.points[i + 1]);
                  }
                }
                compositeContext.stroke();
                
                if (shape.type === "arrow" && shape.points.length >= 4) {
                  const startX = shape.points[shape.points.length - 4];
                  const startY = shape.points[shape.points.length - 3];
                  const endX = shape.points[shape.points.length - 2];
                  const endY = shape.points[shape.points.length - 1];
                  const angle = Math.atan2(endY - startY, endX - startX);
                  const headLength = 18;
                  const headAngle = Math.PI / 6;
                  
                  compositeContext.beginPath();
                  compositeContext.moveTo(endX, endY);
                  compositeContext.lineTo(
                    endX - headLength * Math.cos(angle - headAngle),
                    endY - headLength * Math.sin(angle - headAngle)
                  );
                  compositeContext.moveTo(endX, endY);
                  compositeContext.lineTo(
                    endX - headLength * Math.cos(angle + headAngle),
                    endY - headLength * Math.sin(angle + headAngle)
                  );
                  compositeContext.stroke();
                }
              }
              break;
            }
            case "polygon": {
              if (shape.points && shape.points.length >= 6) {
                compositeContext.beginPath();
                compositeContext.moveTo(shape.points[0], shape.points[1]);
                for (let i = 2; i < shape.points.length; i += 2) {
                  if (i + 1 < shape.points.length) {
                    compositeContext.lineTo(shape.points[i], shape.points[i + 1]);
                  }
                }
                compositeContext.closePath();
                compositeContext.stroke();
              }
              break;
            }
            case "text": {
              if (shape.text) {
                compositeContext.font = `${shape.fontSize || 18}px Arial`;
                compositeContext.textBaseline = "top";
                compositeContext.fillText(shape.text, shape.x || 0, shape.y || 0);
              }
              break;
            }
            case "ruler": {
              if (shape.start && shape.end) {
                compositeContext.beginPath();
                compositeContext.moveTo(shape.start.x, shape.start.y);
                compositeContext.lineTo(shape.end.x, shape.end.y);
                compositeContext.stroke();
                
                compositeContext.beginPath();
                compositeContext.arc(shape.start.x, shape.start.y, 4, 0, Math.PI * 2);
                compositeContext.fill();
                compositeContext.beginPath();
                compositeContext.arc(shape.end.x, shape.end.y, 4, 0, Math.PI * 2);
                compositeContext.fill();
                
                if (shape.label && shape.midpoint) {
                  compositeContext.font = "12px Arial";
                  compositeContext.textAlign = "center";
                  compositeContext.textBaseline = "middle";
                  compositeContext.fillText(
                    shape.label,
                    shape.midpoint.x,
                    shape.midpoint.y
                  );
                }
              }
              break;
            }
            case "angle": {
              if (shape.vertex && shape.pointA && shape.pointB) {
                compositeContext.beginPath();
                compositeContext.moveTo(shape.vertex.x, shape.vertex.y);
                compositeContext.lineTo(shape.pointA.x, shape.pointA.y);
                compositeContext.moveTo(shape.vertex.x, shape.vertex.y);
                compositeContext.lineTo(shape.pointB.x, shape.pointB.y);
                compositeContext.stroke();
                
                if (shape.radius && shape.startDeg !== undefined && shape.sweep !== undefined) {
                  const startAngle = (shape.startDeg || 0) * (Math.PI / 180);
                  const sweepAngle = (shape.sweep || 0) * (Math.PI / 180);
                  compositeContext.beginPath();
                  compositeContext.arc(
                    shape.vertex.x,
                    shape.vertex.y,
                    shape.radius,
                    startAngle,
                    startAngle + sweepAngle
                  );
                  compositeContext.stroke();
                }
                
                if (shape.label && shape.labelPosition) {
                  compositeContext.font = "12px Arial";
                  compositeContext.textAlign = "center";
                  compositeContext.textBaseline = "middle";
                  compositeContext.fillText(
                    shape.label,
                    shape.labelPosition.x,
                    shape.labelPosition.y
                  );
                }
              }
              break;
            }
          }
          
          compositeContext.restore();
        }
        
        const imageDataUrl = compositeCanvas.toDataURL("image/png", 1.0);
        const imageBytes = await fetch(imageDataUrl).then(res => res.arrayBuffer());
        
        const pdfImage = await pdfLibDoc.embedPng(imageBytes);
        
        const pageWidth = unrotatedViewport.width;
        const pageHeight = unrotatedViewport.height;
        
        const page = pdfLibDoc.addPage([pageWidth, pageHeight]);
        
        page.drawImage(pdfImage, {
          x: 0,
          y: 0,
          width: pageWidth,
          height: pageHeight,
        });
      }

      const pdfBytes = await pdfLibDoc.save();
      const blob = new Blob([pdfBytes], { type: "application/pdf" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${projectName}-annotations.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success("CAD export downloaded");
    } catch (error) {
      console.error(error);
      toast.error("Failed to export annotated PDF");
    } finally {
      setIsDownloading(false);
    }
  }, [
    currentPage,
    file?.name,
    fileId,
    isDownloading,
    isImageFile,
    notifyIfBusy,
    pageDimensions,
    pageImage,
    pageMetrics,
    pageStates,
    pageRotationOverrides,
  ]);

  const handleZoomIn = useCallback(() => {
    if (notifyIfBusy()) return;
    setZoom((prev) => Math.min(prev + 0.15, 4));
  }, [notifyIfBusy]);

  const handleZoomOut = useCallback(() => {
    if (notifyIfBusy()) return;
    setZoom((prev) => Math.max(prev - 0.15, 0.1));
  }, [notifyIfBusy]);

  const handleFitToScreen = useCallback(() => {
    if (notifyIfBusy()) return;
    canvasRef.current?.fitToScreen?.();
  }, [notifyIfBusy]);

  const handlePageChange = useCallback(
    (nextPage) => {
      if (notifyIfBusy()) return;
      if (nextPage === currentPage) return;
      persistCurrentPage();
      setCurrentPage(nextPage);
      setActiveTool("select");
    },
    [currentPage, notifyIfBusy, persistCurrentPage]
  );

  const handlePrevPage = () => handlePageChange(Math.max(1, currentPage - 1));
  const handleNextPage = () => handlePageChange(Math.min(numPages, currentPage + 1));
  const handleRotatePage = useCallback(() => {
    setPageRotationOverrides((prev) => {
      const existing = prev[currentPage] || 0;
      const nextValue = (existing + 90) % 360;
      return {
        ...prev,
        [currentPage]: nextValue,
      };
    });
  }, [currentPage]);

  const totalElements = safePageState?.shapes?.length ?? safePageState?.objects?.length ?? 0;

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-[#12141a] text-slate-100 fixed inset-0">
      {/* Top Header Bar - AutoCAD 2020 Style */}
      <header className="h-10 flex items-center justify-between px-3 border-b border-[#2a2e38] bg-[#1a1d24] flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/")}
              className="text-slate-400 hover:text-white hover:bg-[#2a2e38] h-7 px-2 text-xs"
            >
              <Home className="w-3.5 h-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(`/file/${fileId}`)}
              className="text-slate-400 hover:text-white hover:bg-[#2a2e38] h-7 px-2 text-xs"
            >
              <Menu className="w-3.5 h-3.5" />
            </Button>
          </div>
          <div className="h-4 w-px bg-[#2a2e38]" />
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-[#00aaff]" />
            <div>
              <h1 className="text-xs font-semibold text-white leading-none">CAD Annotation</h1>
              <p className="text-[10px] text-slate-500 truncate max-w-[200px]">{file?.name}</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 text-[10px]">
          {canvasStatus.loading && (
            <div className="flex items-center gap-2 px-2 py-1 rounded bg-[#00aaff]/10 border border-[#00aaff]/30">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full rounded-full bg-[#00aaff] opacity-75 animate-ping" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-[#00aaff]" />
              </span>
              <span className="text-[#00aaff]">{canvasStatus.message || "Loading..."}</span>
            </div>
          )}
          <div className="flex items-center gap-2 px-2 py-1 rounded bg-[#2a2e38] text-slate-400">
            <span className="uppercase tracking-wider">Tool:</span>
            <span className="text-white font-medium capitalize">{activeTool}</span>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 flex overflow-hidden">
          {/* Canvas Area */}
          <div className="flex-1 overflow-hidden bg-[#1e2128] relative" data-testid="cad-editor-surface">
          {/* Grid Pattern Background */}
          <div 
            className="absolute inset-0 opacity-[0.03]"
            style={{
              backgroundImage: `
                linear-gradient(to right, #fff 1px, transparent 1px),
                linear-gradient(to bottom, #fff 1px, transparent 1px)
              `,
              backgroundSize: '20px 20px'
            }}
          />
          
          <CadCanvasEditor
            ref={canvasRef}
            pageImage={pageImage}
            pageDimensions={pageDimensions}
            pageState={safePageState}
            onStateChange={handlePageStateChange}
            activeTool={activeTool}
            strokeColor={strokeColor}
            strokeWidth={strokeWidth}
            strokeStyle={strokeStyle}
            zoom={zoom}
            onZoomChange={setZoom}
            disabled={controlsDisabled}
            measurementSettings={{ unit: measurementUnit, unitsPerPixel }}
            activeLayerId={currentLayerState.activeLayerId}
            hiddenLayerIds={hiddenLayerIds}
          />

        </div>

          {/* Right Properties Panel */}
          <PropertiesPanel
          strokeWidth={strokeWidth}
          setStrokeWidth={setStrokeWidth}
          strokeColor={strokeColor}
          setStrokeColor={setStrokeColor}
          strokeStyle={strokeStyle}
          setStrokeStyle={setStrokeStyle}
          measurementUnit={measurementUnit}
          setMeasurementUnit={setMeasurementUnit}
          unitsPerPixel={unitsPerPixel}
          setUnitsPerPixel={setUnitsPerPixel}
          layers={currentLayerState}
          activeLayerId={currentLayerState.activeLayerId}
          onAddLayer={handleAddLayer}
          onSelectLayer={handleSelectLayer}
          onToggleLayerVisibility={handleToggleLayerVisibility}
          zoom={zoom}
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onFitToScreen={handleFitToScreen}
          currentPage={currentPage}
          numPages={numPages}
          onPrevPage={handlePrevPage}
          onNextPage={handleNextPage}
          rotation={manualRotation}
          onRotatePage={handleRotatePage}
          onCopy={handleCopySelection}
          onRotate={handleRotateSelection}
          onScale={handleScaleSelection}
          onSave={handleSave}
          onDownload={handleDownload}
          isSaved={isSaved}
          isAutoSaving={isAutoSaving}
          disabled={controlsDisabled}
          totalElements={totalElements}
        />
        </div>

        {/* Bottom Toolbar */}
        <AnnotationToolbar
          activeTool={activeTool}
          onToolSelect={handleToolSelect}
          onUndo={handleUndo}
          onRedo={handleRedo}
          zoom={zoom}
          currentPage={currentPage}
          numPages={numPages}
          disabled={controlsDisabled}
        />
      </main>
    </div>
  );
};

export default AnnotationPage;
