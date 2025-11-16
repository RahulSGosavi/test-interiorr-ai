import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import * as pdfjsLib from "pdfjs-dist";
import { filesAPI, annotationsAPI } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { ArrowLeft, Home, Menu } from "lucide-react";
import AnnotationToolbar from "@/components/AnnotationToolbar";
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

  const [canvasStatus, setCanvasStatus] = useState({
    loading: true,
    message: "Preparing workspace...",
  });

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

  useEffect(() => {
    currentPageRef.current = currentPage;
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
      
      // Get page rotation from metadata (common in CAD-generated PDFs)
      const rotation = page.rotate || 0;
      
      // Get viewport with rotation accounted for
      // CRITICAL: Ensure we get the full viewport dimensions including rotation
      const viewport = page.getViewport({ scale: 1.5, rotation });
      
      // Get actual page dimensions (before rotation) for reference
      const viewportNoRotation = page.getViewport({ scale: 1.0, rotation: 0 });
      const actualPageWidth = viewportNoRotation.width;
      const actualPageHeight = viewportNoRotation.height;
      
      // Ensure canvas dimensions match viewport exactly (no rounding issues)
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d", { willReadFrequently: true });
      // Use Math.ceil to ensure we capture the full page, especially for landscape/wide pages
      canvas.width = Math.ceil(viewport.width);
      canvas.height = Math.ceil(viewport.height);
      
      // Render the full page to canvas
      await page.render({ canvasContext: context, viewport }).promise;
      
      // Verify canvas was fully rendered by checking if image data exists
      const imageData = canvas.toDataURL();
      if (!imageData || imageData === 'data:,') {
        throw new Error('Failed to render PDF page to canvas');
      }
      
      setPageImage(imageData);
      // Set dimensions exactly as rendered (use actual canvas dimensions)
      // CRITICAL: Use actual canvas dimensions to ensure full page is captured
      // This prevents rounding issues that can cause right side to be cut off
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
  }, []);

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
        
        // Better error messages based on error type
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
      setPageStates((prev) => ({
        ...prev,
        [currentPageRef.current]: snapshot,
      }));
      return snapshot;
    }
    return pageStates[currentPageRef.current];
  }, [pageStates]);

  const handlePageStateChange = useCallback((snapshot) => {
    if (!snapshot) return;
    setPageStates((prev) => ({
      ...prev,
      [currentPageRef.current]: snapshot,
    }));
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
      
      // Use EXACT same scale as renderPdfPage to ensure annotations match perfectly
      const RENDER_SCALE = 1.5;
      
      // Process each page
      for (let pageNum = 1; pageNum <= numPages; pageNum++) {
        toast.info(`Processing page ${pageNum}/${numPages}...`);
        
        // Get PDF page with its rotation
        const pdfJsPage = await pdfJsDoc.getPage(pageNum);
        const rotation = pdfJsPage.rotate || 0;
        
        // Get viewport at render scale (matches display exactly)
        const viewport = pdfJsPage.getViewport({ scale: RENDER_SCALE, rotation });
        
        // Get unrotated viewport for PDF page dimensions
        const unrotatedViewport = pdfJsPage.getViewport({ scale: 1.0, rotation: 0 });
        
        // Create canvas for PDF page - use Math.ceil to ensure full page captured
        const pdfCanvas = document.createElement("canvas");
        const pdfContext = pdfCanvas.getContext("2d", { willReadFrequently: true });
        pdfCanvas.width = Math.ceil(viewport.width);
        pdfCanvas.height = Math.ceil(viewport.height);
        
        // Render PDF page to canvas
        await pdfJsPage.render({ canvasContext: pdfContext, viewport }).promise;
        
        // Get annotations for this page
        const snapshot = exportStates[pageNum];
        const shapes = snapshot?.shapes || [];
        
        // Create composite canvas (same size as PDF canvas)
        const compositeCanvas = document.createElement("canvas");
        const compositeContext = compositeCanvas.getContext("2d", { willReadFrequently: true });
        compositeCanvas.width = pdfCanvas.width;
        compositeCanvas.height = pdfCanvas.height;
        
        // Draw PDF background first
        compositeContext.drawImage(pdfCanvas, 0, 0, pdfCanvas.width, pdfCanvas.height);
        
        // Draw all annotations on top (using exact same coordinates as display)
        for (const shape of shapes) {
          if (!shape || !shape.type) continue;
          
          compositeContext.save();
          compositeContext.strokeStyle = shape.stroke || "#1d4ed8";
          compositeContext.fillStyle = shape.stroke || "#1d4ed8";
          compositeContext.lineWidth = shape.strokeWidth || 2;
          
          // Set line dash pattern
          if (shape.dash && shape.dash.length === 2) {
            compositeContext.setLineDash([shape.dash[0], shape.dash[1]]);
          } else {
            compositeContext.setLineDash([]);
          }
          
          // Draw based on shape type
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
                
                // Draw arrowhead for arrows
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
                
                // Draw handles
                compositeContext.beginPath();
                compositeContext.arc(shape.start.x, shape.start.y, 4, 0, Math.PI * 2);
                compositeContext.fill();
                compositeContext.beginPath();
                compositeContext.arc(shape.end.x, shape.end.y, 4, 0, Math.PI * 2);
                compositeContext.fill();
                
                // Draw label
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
                
                // Draw arc
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
                
                // Draw label
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
        
        // Convert composite canvas to image
        const imageDataUrl = compositeCanvas.toDataURL("image/png", 1.0);
        const imageBytes = await fetch(imageDataUrl).then(res => res.arrayBuffer());
        
        // Embed image into PDF
        const pdfImage = await pdfLibDoc.embedPng(imageBytes);
        
        // Get unrotated page dimensions (original PDF page size in points)
        const pageWidth = unrotatedViewport.width;
        const pageHeight = unrotatedViewport.height;
        
        // Create PDF page with original dimensions (always unrotated)
        const page = pdfLibDoc.addPage([pageWidth, pageHeight]);
        
        // CRITICAL FIX: Use simple approach - always use unrotated page dimensions
        // pdf-lib automatically scales images to fit the specified dimensions
        // This prevents cut-off issues with rotated pages
        
        // Get embedded image dimensions for debugging
        const embeddedImageWidth = pdfImage.width;
        const embeddedImageHeight = pdfImage.height;
        
        // Debug logging to verify dimensions
        console.log(`Page ${pageNum} - Image embedding:`, {
          rotation,
          embeddedImage: { width: embeddedImageWidth, height: embeddedImageHeight },
          pageDimensions: { width: pageWidth, height: pageHeight },
          canvasDimensions: { width: compositeCanvas.width, height: compositeCanvas.height },
          viewportDimensions: { width: viewport.width, height: viewport.height },
        });
        
        // Always use unrotated page dimensions
        // pdf-lib will automatically scale the image to fit these dimensions
        // This works for all rotation types (0°, 90°, 180°, 270°)
        page.drawImage(pdfImage, {
          x: 0,
          y: 0,
          width: pageWidth,  // Always use unrotated page width
          height: pageHeight, // Always use unrotated page height
        });
      }

      // Save and download PDF
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

  const snapshot = pageStates[currentPage];
  const totalElements = snapshot?.shapes?.length ?? snapshot?.objects?.length ?? 0;

  return (
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-slate-950 text-slate-100 fixed inset-0 safe-area-inset">
      <header className="h-11 sm:h-11 flex items-center justify-between px-2 sm:px-3 border-b border-slate-900/80 bg-slate-950/70 backdrop-blur flex-shrink-0 safe-area-header">
        <div className="flex items-center gap-1 sm:gap-2 min-w-0 flex-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
            data-testid="home-button"
            className="text-slate-200 hover:bg-slate-800 h-7 sm:h-8 px-1.5 sm:px-2 text-xs"
            title="Go to Home"
          >
            <Home className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
            <span className="hidden md:inline ml-1">Home</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/file/${fileId}`)}
            data-testid="menu-button"
            className="text-slate-200 hover:bg-slate-800 h-7 sm:h-8 px-1.5 sm:px-2 text-xs"
            title="Go to File Menu"
          >
            <Menu className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
            <span className="hidden md:inline ml-1">Menu</span>
          </Button>
          <div className="h-4 w-px bg-slate-800 hidden sm:block" />
          <div className="min-w-0">
            <h1 className="text-[10px] sm:text-xs font-semibold truncate">CAD Annotation</h1>
            <p className="text-[8px] sm:text-[9px] text-slate-400 truncate hidden lg:block max-w-[120px] sm:max-w-xs">{file?.name}</p>
          </div>
        </div>
        <div className="flex items-center gap-1 text-[9px] sm:text-[10px] flex-shrink-0">
          <div className="hidden md:flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-slate-900/60 border border-slate-800">
            <span className="text-slate-400 text-[8px] sm:text-[9px]">Active</span>
            <span className="font-semibold text-slate-100 capitalize text-[9px] sm:text-[10px]">{activeTool.replace("-", " ")}</span>
          </div>
          <div className="px-1.5 py-0.5 rounded-full bg-slate-900/60 border border-slate-800 text-slate-300">
            {Math.round(zoom * 100)}%
          </div>
          {canvasStatus.loading && (
            <div className="hidden sm:flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-blue-500/10 border border-blue-500/40 text-blue-200">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75 animate-ping" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-blue-300" />
              </span>
              <span className="font-medium text-[8px] sm:text-[9px]">{canvasStatus.message || "Loading..."}</span>
            </div>
          )}
          <div
            className={`px-1.5 py-0.5 rounded-full border ${
              isSaved
                ? "border-emerald-500/40 text-emerald-200 bg-emerald-500/10"
                : "border-amber-500/40 text-amber-200 bg-amber-500/10"
            }`}
          >
            {isSaved ? "Saved" : "Unsaved"}
          </div>
        </div>
      </header>

      <main className="flex-1 flex overflow-hidden">
        <AnnotationToolbar
          activeTool={activeTool}
          onToolSelect={handleToolSelect}
          onUndo={handleUndo}
          onRedo={handleRedo}
          onZoomIn={handleZoomIn}
          onZoomOut={handleZoomOut}
          onFitToScreen={handleFitToScreen}
          onCopy={handleCopySelection}
          onRotate={handleRotateSelection}
          onScale={handleScaleSelection}
          onSave={handleSave}
          onDownload={handleDownload}
          onPrevPage={handlePrevPage}
          onNextPage={handleNextPage}
          currentPage={currentPage}
          numPages={numPages}
          disabled={controlsDisabled}
        />

        <section className="flex-1 flex flex-col min-h-0">
          <div className="h-12 sm:h-13 px-2 sm:px-3 py-1.5 border-b border-slate-900 bg-slate-950/80 backdrop-blur flex items-center justify-between flex-shrink-0 overflow-x-auto gap-2 sm:gap-3">
            <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
              <div className="flex flex-col gap-0.5">
                <span className="text-[9px] uppercase tracking-wider text-slate-500">Width</span>
                <div className="flex items-center gap-2">
                  <Slider
                    value={[strokeWidth]}
                    onValueChange={([value]) => setStrokeWidth(value)}
                    min={1}
                    max={18}
                    step={1}
                    disabled={controlsDisabled}
                    className="w-32 disabled:opacity-40"
                    data-testid="stroke-width-slider"
                    variant="contrast"
                  />
                  <span className="text-[10px] font-semibold w-8 text-center">{strokeWidth}px</span>
                </div>
              </div>

              <div className="flex flex-col gap-0.5">
                <span className="text-[9px] uppercase tracking-wider text-slate-500">Style</span>
                <div className="flex items-center gap-1.5">
                  {["solid", "dashed", "dotted"].map((style) => (
                    <Button
                      key={style}
                      size="sm"
                      variant={strokeStyle === style ? "default" : "outline"}
                      onClick={() => setStrokeStyle(style)}
                      disabled={controlsDisabled}
                      className="h-7 text-[10px] capitalize disabled:opacity-50 disabled:cursor-not-allowed px-2"
                    >
                      {style}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="flex flex-col gap-0.5">
                <span className="text-[9px] uppercase tracking-wider text-slate-500">Color</span>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={strokeColor}
                    onChange={(e) => setStrokeColor(e.target.value)}
                    disabled={controlsDisabled}
                    className="w-8 h-8 rounded border border-slate-800 bg-slate-900 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                    data-testid="stroke-color-picker"
                  />
                  <span className="text-[10px] font-semibold">{strokeColor}</span>
                </div>
              </div>

            <div className="flex flex-col gap-0.5">
              <span className="text-[9px] uppercase tracking-wider text-slate-500">Unit</span>
              <div className="flex items-center gap-2 text-xs text-slate-300">
                <label className="flex items-center gap-1.5 bg-slate-900/60 border border-slate-800 rounded px-2 py-1">
                  <span className="uppercase tracking-wider text-[9px] text-slate-400">Unit</span>
                  <select
                    value={measurementUnit}
                    onChange={(event) => setMeasurementUnit(event.target.value)}
                    className="bg-slate-900 text-blue-300 text-[10px] font-semibold uppercase focus:outline-none rounded px-1 py-0.5"
                    disabled={controlsDisabled}
                  >
                    <option value="mm" className="text-slate-900">mm</option>
                    <option value="cm" className="text-slate-900">cm</option>
                    <option value="m" className="text-slate-900">m</option>
                  </select>
                </label>
                <label className="flex items-center gap-1.5 bg-slate-900/60 border border-slate-800 rounded px-2 py-1">
                  <span className="uppercase tracking-wider text-[9px] text-slate-400">Scale</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={unitsPerPixel}
                    onChange={(event) => setUnitsPerPixel(Math.max(parseFloat(event.target.value) || 0, 0.0001))}
                    className="w-16 bg-slate-900 text-blue-300 text-[10px] font-semibold focus:outline-none rounded px-1 py-0.5"
                    disabled={controlsDisabled}
                  />
                </label>
              </div>
            </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex flex-col items-end">
                <span className="text-[9px] uppercase tracking-wider text-slate-500">Elements</span>
                <span className="text-xs font-semibold">{totalElements}</span>
              </div>
              <div className="flex flex-col items-end">
                <span className="text-[9px] uppercase tracking-wider text-slate-500">Page</span>
                <span className="text-xs font-semibold">
                  {currentPage}/{numPages}
                </span>
              </div>
            </div>
          </div>

          <div className="flex-1 overflow-hidden bg-slate-900 min-h-0" data-testid="cad-editor-surface">
            <CadCanvasEditor
              ref={canvasRef}
              pageImage={pageImage}
              pageDimensions={pageDimensions}
              pageState={currentPageState}
              onStateChange={handlePageStateChange}
              activeTool={activeTool}
              strokeColor={strokeColor}
              strokeWidth={strokeWidth}
              strokeStyle={strokeStyle}
              zoom={zoom}
              onZoomChange={setZoom}
              disabled={controlsDisabled}
              measurementSettings={{ unit: measurementUnit, unitsPerPixel }}
            />
          </div>
        </section>
      </main>
    </div>
  );
};

export default AnnotationPage;
