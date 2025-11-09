import { useState, useEffect, useRef, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import * as pdfjsLib from "pdfjs-dist";
import { filesAPI, annotationsAPI } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { ArrowLeft } from "lucide-react";
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

const AnnotationPage = () => {
  const { fileId } = useParams();
  const navigate = useNavigate();
  const canvasRef = useRef(null);
  const currentPageRef = useRef(1);

  const [file, setFile] = useState(null);
  const [pdfDoc, setPdfDoc] = useState(null);
  const [pageImage, setPageImage] = useState(null);
  const [pageDimensions, setPageDimensions] = useState({ width: 0, height: 0 });

  const [activeTool, setActiveTool] = useState("select");
  const [zoom, setZoom] = useState(1);
  const [currentPage, setCurrentPage] = useState(1);
  const [numPages, setNumPages] = useState(1);
  const [strokeWidth, setStrokeWidth] = useState(4);
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
      const viewport = page.getViewport({ scale: 1.5 });
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("2d", { willReadFrequently: true });
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await page.render({ canvasContext: context, viewport }).promise;
      setPageImage(canvas.toDataURL());
      setPageDimensions({ width: viewport.width, height: viewport.height });
      setPageMetrics((prev) => ({
        ...prev,
        [pageNumber]: {
          width: viewport.width,
          height: viewport.height,
          scale: viewport.scale,
          transform: viewport.transform,
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
        setFile(response.data);
      } catch (error) {
        toast.error("Failed to load file");
      }
      await loadAnnotations();

      try {
        const pdfResponse = await api.get(`/files/${fileId}/download`, {
          responseType: "arraybuffer",
        });
        const doc = await pdfjsLib.getDocument({ data: pdfResponse.data }).promise;
        setPdfDoc(doc);
        setNumPages(doc.numPages);
      } catch (error) {
        toast.error("Failed to load document");
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

      const latestSnapshot = canvasRef.current?.exportState?.();
      const exportStates = latestSnapshot
        ? {
            ...pageStates,
            [currentPageRef.current]: latestSnapshot,
          }
        : pageStates;

      const response = await api.get(`/files/${fileId}/download`, {
        responseType: "arraybuffer",
      });
      const fileBytes = response.data;
      const pdfLibDoc = await PDFDocument.load(fileBytes);
      const pdfJsDoc = await pdfjsLib.getDocument({ data: fileBytes }).promise;
      const font = await pdfLibDoc.embedFont(StandardFonts.Helvetica);
      const pages = pdfLibDoc.getPages();

      const projectName = file?.name?.replace?.(/\.[^/.]+$/, "") || "annotated";

      for (let index = 0; index < pages.length; index += 1) {
        const pageNumber = index + 1;
        const snapshot = exportStates[pageNumber];
        if (!snapshot || !snapshot.shapes || snapshot.shapes.length === 0) continue;

        const metrics =
          pageMetrics[pageNumber] ||
          pageMetrics[currentPage] ||
          { width: pageDimensions.width, height: pageDimensions.height, scale: 1.5 };

        if (!metrics?.width || !metrics?.height) continue;

        const pdfLibPage = pages[index];
        const { width: pdfWidth, height: pdfHeight } = pdfLibPage.getSize();
        const pdfJsPage = await pdfJsDoc.getPage(pageNumber);
        const viewport = pdfJsPage.getViewport({ scale: metrics?.scale || 1 });
        const renderScaleX = (viewport.width || metrics.width || pdfWidth) / pdfWidth;
        const renderScaleY = (viewport.height || metrics.height || pdfHeight) / pdfHeight;
        const toPdfPoint = (x, y) => ({
          x: x / (renderScaleX || 1),
          y: pdfHeight - y / (renderScaleY || 1),
        });
        const pixelToPdf = ((1 / (renderScaleX || 1)) + (1 / (renderScaleY || 1))) / 2;

        const strokeOptions = (shape) => ({
          color: hexToPdfColor(shape.stroke || "#1d4ed8"),
          thickness: Math.max((shape.strokeWidth || 1) * pixelToPdf, 0.35),
          dashArray: mapDashArray(shape.dash, pixelToPdf),
        });

        const toPdfPointsArray = (points = []) => {
          const converted = [];
          for (let i = 0; i < points.length; i += 2) {
            const { x, y } = toPdfPoint(points[i], points[i + 1]);
            converted.push({ x, y });
          }
          return converted;
        };

        const buildPathFromPoints = (points, close = false) => {
          if (!points.length) return null;
          let path = `M ${points[0].x} ${points[0].y}`;
          for (let i = 1; i < points.length; i += 1) {
            path += ` L ${points[i].x} ${points[i].y}`;
          }
          if (close) path += " Z";
          return path;
        };

        for (const shape of snapshot.shapes) {
          const opts = strokeOptions(shape);
          switch (shape.type) {
            case "rect": {
              const topLeft = toPdfPoint(shape.x, shape.y);
              const bottomRight = toPdfPoint(shape.x + shape.width, shape.y + shape.height);
              const rectX = Math.min(topLeft.x, bottomRight.x);
              const rectY = Math.min(topLeft.y, bottomRight.y);
              const rectWidth = Math.abs(bottomRight.x - topLeft.x);
              const rectHeight = Math.abs(bottomRight.y - topLeft.y);
              pdfLibPage.drawRectangle({
                x: rectX,
                y: rectY,
                width: rectWidth,
                height: rectHeight,
                borderColor: opts.color,
                borderWidth: opts.thickness,
                dashArray: opts.dashArray,
              });
              break;
            }
            case "circle": {
              const center = toPdfPoint(shape.x, shape.y);
              const edgeX = toPdfPoint(shape.x + shape.radius, shape.y);
              const edgeY = toPdfPoint(shape.x, shape.y - shape.radius);
              const radiusX = Math.abs(edgeX.x - center.x) || pixelToPdf;
              const radiusY = Math.abs(edgeY.y - center.y) || radiusX;
              pdfLibPage.drawEllipse({
                x: center.x,
                y: center.y,
                xScale: radiusX,
                yScale: radiusY,
                borderColor: opts.color,
                borderWidth: opts.thickness,
                dashArray: opts.dashArray,
              });
              break;
            }
            case "line":
            case "free":
            case "polygon":
            case "arrow": {
              const pdfPoints = toPdfPointsArray(shape.points);

              if (shape.type === "free" || shape.type === "polygon") {
                const path = buildPathFromPoints(pdfPoints, shape.type === "polygon");
                if (path) {
                  pdfLibPage.drawSvgPath(path, {
                    borderColor: opts.color,
                    borderWidth: opts.thickness,
                    dashArray: opts.dashArray,
                  });
                }
              } else {
                for (let i = 0; i < pdfPoints.length - 1; i += 1) {
                  pdfLibPage.drawLine({
                    start: pdfPoints[i],
                    end: pdfPoints[i + 1],
                    color: opts.color,
                    thickness: opts.thickness,
                    dashArray: opts.dashArray,
                  });
                }
                if (shape.type === "arrow" && pdfPoints.length >= 2) {
                  const start = pdfPoints[pdfPoints.length - 2];
                  const end = pdfPoints[pdfPoints.length - 1];
                  const angle = Math.atan2(end.y - start.y, end.x - start.x);
                  const headLength = 18 * pixelToPdf;
                  const headWidth = 10 * pixelToPdf;
                  const left = {
                    x: end.x - headLength * Math.cos(angle - Math.PI / 6),
                    y: end.y - headLength * Math.sin(angle - Math.PI / 6),
                  };
                  const right = {
                    x: end.x - headLength * Math.cos(angle + Math.PI / 6),
                    y: end.y - headLength * Math.sin(angle + Math.PI / 6),
                  };
                  pdfLibPage.drawLine({
                    start: end,
                    end: left,
                    color: opts.color,
                    thickness: opts.thickness,
                  });
                  pdfLibPage.drawLine({
                    start: end,
                    end: right,
                    color: opts.color,
                    thickness: opts.thickness,
                  });
                }
              }
              break;
            }
            case "text": {
              if (!shape.text) break;
              const topLeft = toPdfPoint(shape.x, shape.y);
              const fontSize = Math.max((shape.fontSize || 18) * pixelToPdf * (shape.scaleY || 1), 4);
              pdfLibPage.drawText(shape.text, {
                x: topLeft.x,
                y: topLeft.y - fontSize,
                size: fontSize,
                font,
                color: hexToPdfColor(shape.stroke || "#1f2937"),
              });
              break;
            }
            case "ruler": {
              const start = toPdfPoint(shape.start.x, shape.start.y);
              const end = toPdfPoint(shape.end.x, shape.end.y);
              pdfLibPage.drawLine({
                start,
                end,
                color: opts.color,
                thickness: opts.thickness,
                dashArray: opts.dashArray,
              });
              const handleRadius = 4 * pixelToPdf;
              pdfLibPage.drawEllipse({
                x: start.x,
                y: start.y,
                xScale: handleRadius,
                yScale: handleRadius,
                color: opts.color,
              });
              pdfLibPage.drawEllipse({
                x: end.x,
                y: end.y,
                xScale: handleRadius,
                yScale: handleRadius,
                color: opts.color,
              });
              if (shape.label) {
                const midpoint = toPdfPoint(shape.midpoint.x, shape.midpoint.y);
                const labelSize = 12 * pixelToPdf;
                pdfLibPage.drawText(shape.label, {
                  x: midpoint.x - (shape.label.length * labelSize) / 4,
                  y: midpoint.y + labelSize / 2,
                  size: labelSize,
                  font,
                  color: opts.color,
                });
              }
              break;
            }
            case "angle": {
              const vertex = toPdfPoint(shape.vertex.x, shape.vertex.y);
              const pointA = toPdfPoint(shape.pointA.x, shape.pointA.y);
              const pointB = toPdfPoint(shape.pointB.x, shape.pointB.y);
              pdfLibPage.drawLine({
                start: vertex,
                end: pointA,
                color: opts.color,
                thickness: opts.thickness,
                dashArray: opts.dashArray,
              });
              pdfLibPage.drawLine({
                start: vertex,
                end: pointB,
                color: opts.color,
                thickness: opts.thickness,
                dashArray: opts.dashArray,
              });

              const steps = Math.max(6, Math.round(Math.abs(shape.sweep || 0) / 10));
              if (steps > 0 && shape.radius) {
                const arcPoints = [];
                for (let step = 0; step <= steps; step += 1) {
                  const theta = ((shape.startDeg || 0) + (shape.sweep || 0) * (step / steps)) * (Math.PI / 180);
                  const px = shape.vertex.x + Math.cos(theta) * shape.radius;
                  const py = shape.vertex.y + Math.sin(theta) * shape.radius;
                  arcPoints.push(toPdfPoint(px, py));
                }
                const arcPath = buildPathFromPoints(arcPoints);
                if (arcPath) {
                  pdfLibPage.drawSvgPath(arcPath, {
                    borderColor: opts.color,
                    borderWidth: Math.max(opts.thickness * 0.8, 0.35),
                  });
                }
              }

              if (shape.label) {
                const labelPosition = shape.labelPosition || {
                  x: shape.vertex.x,
                  y: shape.vertex.y,
                };
                const labelPoint = toPdfPoint(labelPosition.x, labelPosition.y);
                const labelSize = 12 * pixelToPdf;
                pdfLibPage.drawText(shape.label, {
                  x: labelPoint.x - (shape.label.length * labelSize) / 4,
                  y: labelPoint.y + labelSize / 2,
                  size: labelSize,
                  font,
                  color: opts.color,
                });
              }
              break;
            }
            default:
              break;
          }
        }
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
    notifyIfBusy,
    pageDimensions.height,
    pageDimensions.width,
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
    <div className="h-screen w-screen overflow-hidden flex flex-col bg-slate-950 text-slate-100 fixed inset-0">
      <header className="h-14 lg:h-16 flex items-center justify-between px-4 lg:px-6 border-b border-slate-900/80 bg-slate-950/70 backdrop-blur flex-shrink-0">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/file/${fileId}`)}
            data-testid="back-button"
            className="text-slate-200 hover:bg-slate-800"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <div className="h-6 w-px bg-slate-800 hidden sm:block" />
          <div>
            <h1 className="text-sm lg:text-base font-semibold">CAD Annotation</h1>
            <p className="text-[10px] lg:text-xs text-slate-400 max-w-xs truncate hidden sm:block">{file?.name}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 lg:gap-3 text-xs flex-wrap">
          <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900/60 border border-slate-800 uppercase tracking-wide">
            <span className="text-slate-400">Active</span>
            <span className="font-semibold text-slate-100 capitalize">{activeTool.replace("-", " ")}</span>
          </div>
          <div className="px-3 py-1 rounded-full bg-slate-900/60 border border-slate-800 text-slate-300">
            Zoom {Math.round(zoom * 100)}%
          </div>
          {canvasStatus.loading ? (
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/40 text-blue-200">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75 animate-ping" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-300" />
              </span>
              <span className="font-medium text-xs">{canvasStatus.message || "Loading document..."}</span>
            </div>
          ) : canvasStatus.message ? (
            <div className="px-3 py-1 rounded-full bg-slate-900/60 border border-slate-800 text-slate-300">
              {canvasStatus.message}
            </div>
          ) : null}
          <div
            className={`px-3 py-1 rounded-full border ${
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
          <div className="h-16 lg:h-18 px-4 lg:px-6 border-b border-slate-900 bg-slate-950/80 backdrop-blur flex items-center justify-between flex-shrink-0 overflow-x-auto">
            <div className="flex items-center gap-6">
              <div className="flex flex-col gap-1">
                <span className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Stroke Width</span>
                <div className="flex items-center gap-3">
                  <Slider
                    value={[strokeWidth]}
                    onValueChange={([value]) => setStrokeWidth(value)}
                    min={1}
                    max={18}
                    step={1}
                    disabled={controlsDisabled}
                    className="w-48 disabled:opacity-40"
                    data-testid="stroke-width-slider"
                    variant="contrast"
                  />
                  <span className="text-xs font-semibold w-10 text-center">{strokeWidth}px</span>
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <span className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Stroke Style</span>
                <div className="flex items-center gap-2">
                  {["solid", "dashed", "dotted"].map((style) => (
                    <Button
                      key={style}
                      size="sm"
                      variant={strokeStyle === style ? "default" : "outline"}
                      onClick={() => setStrokeStyle(style)}
                      disabled={controlsDisabled}
                      className="h-8 capitalize disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {style}
                    </Button>
                  ))}
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <span className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Stroke Color</span>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={strokeColor}
                    onChange={(e) => setStrokeColor(e.target.value)}
                    disabled={controlsDisabled}
                    className="w-10 h-10 rounded border border-slate-800 bg-slate-900 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
                    data-testid="stroke-color-picker"
                  />
                  <span className="text-xs font-semibold">{strokeColor}</span>
                </div>
              </div>

            <div className="flex flex-col gap-1">
              <span className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Measurement</span>
              <div className="flex items-center gap-3 text-xs text-slate-300">
                <label className="flex items-center gap-2 bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-2">
                  <span className="uppercase tracking-wider text-[10px] text-slate-400">Unit</span>
                  <select
                    value={measurementUnit}
                    onChange={(event) => setMeasurementUnit(event.target.value)}
                    className="bg-slate-900 text-blue-300 font-semibold uppercase tracking-wide focus:outline-none focus:ring-2 focus:ring-blue-500/70 rounded px-1 py-1"
                    disabled={controlsDisabled}
                  >
                    <option value="mm" className="text-slate-900">mm</option>
                    <option value="cm" className="text-slate-900">cm</option>
                    <option value="m" className="text-slate-900">m</option>
                  </select>
                </label>
                <label className="flex items-center gap-2 bg-slate-900/60 border border-slate-800 rounded-lg px-3 py-2">
                  <span className="uppercase tracking-wider text-[10px] text-slate-400">Scale</span>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={unitsPerPixel}
                    onChange={(event) => setUnitsPerPixel(Math.max(parseFloat(event.target.value) || 0, 0.0001))}
                    className="w-20 bg-slate-900 text-blue-300 font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/70 rounded px-1 py-1"
                    disabled={controlsDisabled}
                  />
                  <span className="text-slate-400 text-[10px] uppercase tracking-wider">per px</span>
                </label>
              </div>
            </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex flex-col items-end">
                <span className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Elements</span>
                <span className="text-sm font-semibold">{totalElements}</span>
              </div>
              <div className="flex flex-col items-end">
                <span className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Page</span>
                <span className="text-sm font-semibold">
                  {currentPage} / {numPages}
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

