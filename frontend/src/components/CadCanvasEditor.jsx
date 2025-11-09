import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { Stage, Layer, Rect, Circle, Line, Arrow, Text, Image as KonvaImage, Transformer, Group, Arc } from "react-konva";
import useImage from "use-image";

const HISTORY_LIMIT = 50;
const ERASER_RADIUS = 28;

const strokePreset = (style) => {
  switch (style) {
    case "dashed":
      return [12, 8];
    case "dotted":
      return [4, 10];
    default:
      return [];
  }
};

const createId = (prefix) => (crypto.randomUUID ? crypto.randomUUID() : `${prefix}-${Date.now()}`);
const cloneShape = (shape) => ({
  ...shape,
  points: Array.isArray(shape.points) ? [...shape.points] : shape.points,
});
const cloneShapes = (shapes) => shapes.map(cloneShape);
const snapshotsEqual = (a, b) => {
  if (!a || !b) return false;
  return JSON.stringify(a) === JSON.stringify(b);
};

const BackgroundImage = ({ src, width, height }) => {
  const [image] = useImage(src);
  if (!image) return null;
  return <KonvaImage image={image} width={width} height={height} listening={false} />;
};

const CadCanvasEditor = forwardRef(
  (
    {
      pageImage,
      pageDimensions,
      pageState,
      onStateChange,
      activeTool,
      strokeColor,
      strokeWidth,
      strokeStyle,
      zoom,
      onZoomChange,
      disabled = false,
      measurementSettings,
    },
    ref
  ) => {
    const containerRef = useRef(null);
    const stageRef = useRef(null);
    const transformerRef = useRef(null);
    const pinchRef = useRef(null);
    const textAreaRef = useRef(null);

    const [shapes, setShapes] = useState(pageState?.shapes || []);
    const [stagePosition, setStagePosition] = useState(pageState?.stagePosition || { x: 0, y: 0 });
    const [selectedId, setSelectedId] = useState(null);
    const [draft, setDraft] = useState(null);
    const [polygonDraft, setPolygonDraft] = useState(null);
    const [isPanning, setIsPanning] = useState(false);
    const [hasAutoFit, setHasAutoFit] = useState(false);
    const [isErasing, setIsErasing] = useState(false);
    const [eraserCursor, setEraserCursor] = useState(null);
    const [angleDraft, setAngleDraft] = useState(null);
    const [rulerDraft, setRulerDraft] = useState(null);
    const [textEditor, setTextEditor] = useState(null);
    const [containerDimensions, setContainerDimensions] = useState({ width: 800, height: 600 });
    const historyRef = useRef({ undo: [], redo: [] });
    const shapesRef = useRef(shapes);
    const eraserRemovedRef = useRef(false);
    const eraserResultRef = useRef(null);
    const lastOutboundSnapshotRef = useRef(null);
    const prevPageStateRef = useRef(null);

    const dash = useMemo(() => strokePreset(strokeStyle), [strokeStyle]);
    const scale = zoom || 1;
    const measurementUnit = measurementSettings?.unit ?? "px";
    const unitsPerPixel = measurementSettings?.unitsPerPixel ?? 1;

    const fitStageToContainer = useCallback(() => {
      const container = containerRef.current;
      if (!container || !pageDimensions?.width || !pageDimensions?.height) return false;
      const rect = container.getBoundingClientRect();
      if (!rect.width || !rect.height) return false;

      const scaleX = rect.width / pageDimensions.width;
      const scaleY = rect.height / pageDimensions.height;
      const nextScale = Math.min(scaleX, scaleY);
      const fittedWidth = pageDimensions.width * nextScale;
      const fittedHeight = pageDimensions.height * nextScale;
      const nextPosition = {
        x: (rect.width - fittedWidth) / 2,
        y: (rect.height - fittedHeight) / 2,
      };

      onZoomChange?.(nextScale);
      setStagePosition(nextPosition);
      return true;
    }, [onZoomChange, pageDimensions?.height, pageDimensions?.width]);

    const applySnapshot = useCallback((snapshot) => {
      if (!snapshot) {
        setShapes([]);
        setStagePosition({ x: 0, y: 0 });
      } else {
        setShapes(snapshot.shapes || []);
        setStagePosition(snapshot.stagePosition || { x: 0, y: 0 });
      }
      setSelectedId(null);
      setDraft(null);
      setPolygonDraft(null);
    }, []);

    const createSnapshot = useCallback(
      (shapeList, position) => ({
        shapes: cloneShapes(shapeList),
        stagePosition: { x: position.x, y: position.y },
      }),
      []
    );

    const pushHistory = useCallback(
      (nextShapes, nextPosition = stagePosition) => {
        const snapshot = createSnapshot(nextShapes, nextPosition);
        const undoStack = historyRef.current.undo;
        const lastSnapshot = undoStack[undoStack.length - 1];
        if (lastSnapshot && snapshotsEqual(lastSnapshot, snapshot)) {
          return;
        }
        historyRef.current.undo = [...undoStack, snapshot].slice(-HISTORY_LIMIT);
        historyRef.current.redo = [];
        lastOutboundSnapshotRef.current = snapshot;
        onStateChange?.(snapshot);
      },
      [createSnapshot, onStateChange, stagePosition]
    );

    const commitShapes = useCallback(
      (nextShapes) => {
        setShapes(nextShapes);
        pushHistory(nextShapes, stagePosition);
      },
      [pushHistory, stagePosition]
    );

    useEffect(() => {
      if (pageState && lastOutboundSnapshotRef.current && snapshotsEqual(pageState, lastOutboundSnapshotRef.current)) {
        prevPageStateRef.current = pageState;
        return;
      }
      if (prevPageStateRef.current === pageState) {
        return;
      }
      prevPageStateRef.current = pageState;
      const baseShapes = pageState?.shapes || [];
      const baseStage = pageState?.stagePosition || { x: 0, y: 0 };
      const snapshot = createSnapshot(baseShapes, baseStage);
      setShapes(snapshot.shapes);
      setStagePosition(snapshot.stagePosition);
      setSelectedId(null);
      setDraft(null);
      setPolygonDraft(null);
      historyRef.current.undo = [snapshot];
      historyRef.current.redo = [];
      lastOutboundSnapshotRef.current = snapshot;
      eraserRemovedRef.current = false;
      eraserResultRef.current = null;
    }, [createSnapshot, pageState]);

    const formatDistance = useCallback(
      (distancePx) => {
        if (measurementUnit === "px") {
          return {
            label: `${distancePx.toFixed(1)} px`,
            displayValue: distancePx,
          };
        }
        const converted = distancePx * unitsPerPixel;
        return {
          label: `${converted.toFixed(2)} ${measurementUnit}`,
          displayValue: converted,
        };
      },
      [measurementUnit, unitsPerPixel]
    );

    useEffect(() => {
      const currentShapes = shapesRef.current;
      if (!currentShapes.length) return;
      let changed = false;
      const updated = currentShapes.map((shape) => {
        if (shape.type !== "ruler") return shape;
        const distancePx = Math.hypot(shape.end.x - shape.start.x, shape.end.y - shape.start.y);
        const { label, displayValue } = formatDistance(distancePx);
        if (
          shape.distancePx === distancePx &&
          shape.unit === measurementUnit &&
          shape.label === label &&
          shape.distance === displayValue
        ) {
          return shape;
        }
        changed = true;
        return {
          ...shape,
          distancePx,
          distance: displayValue,
          unit: measurementUnit,
          label,
        };
      });
      if (changed) {
        commitShapes(updated);
      }
    }, [commitShapes, formatDistance, measurementUnit, unitsPerPixel]);

    useEffect(() => {
      shapesRef.current = shapes;
    }, [shapes]);

    useEffect(() => {
      const updateContainerSize = () => {
        if (containerRef.current) {
          const rect = containerRef.current.getBoundingClientRect();
          setContainerDimensions({ width: rect.width, height: rect.height });
        }
      };

      updateContainerSize();
      window.addEventListener('resize', updateContainerSize);
      
      const resizeObserver = new ResizeObserver(updateContainerSize);
      if (containerRef.current) {
        resizeObserver.observe(containerRef.current);
      }

      return () => {
        window.removeEventListener('resize', updateContainerSize);
        resizeObserver.disconnect();
      };
    }, []);

    useEffect(() => {
      setHasAutoFit(false);
    }, [pageDimensions?.height, pageDimensions?.width, pageImage]);

    useEffect(() => {
      if (hasAutoFit) return;
      if (!pageImage || !pageDimensions?.width || !pageDimensions?.height) return;
      if (fitStageToContainer()) {
        setHasAutoFit(true);
      }
    }, [fitStageToContainer, hasAutoFit, pageDimensions?.height, pageDimensions?.width, pageImage]);

    useEffect(() => {
      if (!textEditor) return;
      const timer = requestAnimationFrame(() => {
        textAreaRef.current?.focus();
        textAreaRef.current?.select();
      });
      return () => cancelAnimationFrame(timer);
    }, [textEditor]);

    const getPointer = useCallback((stage) => {
      const pointer = stage.getPointerPosition();
      const position = stage.position();
      const scale = stage.scaleX();
      return {
        x: (pointer.x - position.x) / scale,
        y: (pointer.y - position.y) / scale,
      };
    }, []);

    const distanceToSegment = useCallback((px, py, x1, y1, x2, y2) => {
      const A = px - x1;
      const B = py - y1;
      const C = x2 - x1;
      const D = y2 - y1;

      const dot = A * C + B * D;
      const lenSq = C * C + D * D;
      let param = -1;
      if (lenSq !== 0) param = dot / lenSq;

      let xx;
      let yy;

      if (param < 0) {
        xx = x1;
        yy = y1;
      } else if (param > 1) {
        xx = x2;
        yy = y2;
      } else {
        xx = x1 + param * C;
        yy = y1 + param * D;
      }

      const dx = px - xx;
      const dy = py - yy;
      return Math.sqrt(dx * dx + dy * dy);
    }, []);

    const toDegrees = useCallback((rad) => (rad * 180) / Math.PI, []);
    const toRadians = useCallback((deg) => (deg * Math.PI) / 180, []);
    const normalizeDegrees = useCallback((deg) => {
      let value = deg % 360;
      if (value < 0) value += 360;
      return value;
    }, []);

    const isPointNearShape = useCallback(
      (shape, point, tolerance) => {
        switch (shape.type) {
          case "rect":
            return (
              point.x >= shape.x - tolerance &&
              point.x <= shape.x + shape.width + tolerance &&
              point.y >= shape.y - tolerance &&
              point.y <= shape.y + shape.height + tolerance
            );
          case "circle":
            return (
              Math.hypot(point.x - shape.x, point.y - shape.y) <= shape.radius + tolerance
            );
          case "line":
          case "arrow":
          case "free":
          case "polygon": {
            const points = shape.points || [];
            for (let i = 0; i < points.length - 2; i += 2) {
              const x1 = points[i];
              const y1 = points[i + 1];
              const x2 = points[i + 2];
              const y2 = points[i + 3];
              if (distanceToSegment(point.x, point.y, x1, y1, x2, y2) <= tolerance) {
                return true;
              }
            }
            return false;
          }
          case "ruler": {
            return (
              distanceToSegment(point.x, point.y, shape.start.x, shape.start.y, shape.end.x, shape.end.y) <=
              tolerance
            );
          }
          case "angle": {
            const hitsFirst =
              distanceToSegment(point.x, point.y, shape.vertex.x, shape.vertex.y, shape.pointA.x, shape.pointA.y) <=
              tolerance;
            const hitsSecond =
              distanceToSegment(point.x, point.y, shape.vertex.x, shape.vertex.y, shape.pointB.x, shape.pointB.y) <=
              tolerance;
            return hitsFirst || hitsSecond;
          }
          case "text": {
            const width = (shape.text?.length || 4) * (shape.fontSize || 18) * 0.6;
            const height = (shape.fontSize || 18) * 1.2;
            return (
              point.x >= shape.x - tolerance &&
              point.x <= shape.x + width + tolerance &&
              point.y >= shape.y - tolerance &&
              point.y <= shape.y + height + tolerance
            );
          }
          default:
            return false;
        }
      },
      [distanceToSegment]
    );

    const eraseAtPoint = useCallback(
      (point) => {
        const tolerance = ERASER_RADIUS / scale;
        setShapes((prevShapes) => {
          const nextShapes = prevShapes.filter((shape) => !isPointNearShape(shape, point, tolerance));
          if (nextShapes.length !== prevShapes.length) {
            eraserRemovedRef.current = true;
            eraserResultRef.current = nextShapes;
            return nextShapes;
          }
          return prevShapes;
        });
      },
      [isPointNearShape, scale]
    );

    const updateShapeById = useCallback(
      (id, updater) => {
        const next = shapes.map((shape) => (shape.id === id ? updater(shape) : shape));
        commitShapes(next);
      },
      [commitShapes, shapes]
    );

    const openTextEditor = useCallback(
      ({ id, x, y, value = "", fontSize = 18, stroke }) => {
        setTextEditor({
          id,
          x,
          y,
          value,
          fontSize,
          stroke,
          isNew: !shapes.find((shape) => shape.id === id),
        });
        setSelectedId(id);
      },
      [setSelectedId, setTextEditor, shapes]
    );

    const commitTextEditor = useCallback(
      (value) => {
        if (!textEditor) return;
        const trimmed = value?.trim?.() ?? "";
        const normalizedValue = value || "";

        if (textEditor.isNew) {
          if (!trimmed) {
            setTextEditor(null);
            return;
          }
          const newShape = {
            id: textEditor.id,
            type: "text",
            text: normalizedValue,
            x: textEditor.x,
            y: textEditor.y,
            fontSize: textEditor.fontSize,
            stroke: textEditor.stroke || strokeColor,
            strokeWidth,
            dash,
          };
          commitShapes([...shapes, newShape]);
          setSelectedId(textEditor.id);
        } else {
          if (!trimmed) {
            commitShapes(shapes.filter((shape) => shape.id !== textEditor.id));
          } else {
            updateShapeById(textEditor.id, (shape) => ({
              ...shape,
              text: normalizedValue,
            }));
          }
        }
        setTextEditor(null);
      },
      [commitShapes, dash, setSelectedId, shapes, strokeColor, strokeWidth, textEditor, updateShapeById]
    );

    const textEditorStyle = useMemo(() => {
      if (!textEditor) return null;
      return {
        top: stagePosition.y + textEditor.y * scale,
        left: stagePosition.x + textEditor.x * scale,
        transform: `scale(${scale})`,
        transformOrigin: "top left",
      };
    }, [scale, stagePosition.x, stagePosition.y, textEditor]);

    const handleAnglePoint = useCallback(
      (point) => {
        if (!angleDraft) {
          setAngleDraft({
            id: createId("angle"),
            vertex: point,
            cursor: point,
          });
          return;
        }
        if (!angleDraft.first) {
          setAngleDraft({
            ...angleDraft,
            first: point,
            cursor: point,
          });
          return;
        }

        const vertex = angleDraft.vertex;
        const pointA = angleDraft.first;
        const pointB = point;

        const vectorA = { x: pointA.x - vertex.x, y: pointA.y - vertex.y };
        const vectorB = { x: pointB.x - vertex.x, y: pointB.y - vertex.y };
        const lengthA = Math.hypot(vectorA.x, vectorA.y);
        const lengthB = Math.hypot(vectorB.x, vectorB.y);

        if (!lengthA || !lengthB) {
          setAngleDraft(null);
          return;
        }

        const dot = vectorA.x * vectorB.x + vectorA.y * vectorB.y;
        const clamped = Math.min(Math.max(dot / (lengthA * lengthB), -1), 1);
        const angleRad = Math.acos(clamped);
        const angleDeg = toDegrees(angleRad);

        const startDeg = normalizeDegrees(toDegrees(Math.atan2(vectorA.y, vectorA.x)));
        const endDeg = normalizeDegrees(toDegrees(Math.atan2(vectorB.y, vectorB.x)));
        let sweep = endDeg - startDeg;
        if (sweep <= 0) sweep += 360;

        const radius = Math.min(lengthA, lengthB) * 0.35;
        const midAngle = toRadians(startDeg + sweep / 2);
        const labelPosition = {
          x: vertex.x + Math.cos(midAngle) * (radius + 24),
          y: vertex.y + Math.sin(midAngle) * (radius + 24),
        };

        const newShape = {
          id: angleDraft.id,
          type: "angle",
          vertex,
          pointA,
          pointB,
          stroke: strokeColor,
          strokeWidth,
          dash,
          angle: angleDeg,
          startDeg,
          sweep,
          radius,
          label: `${angleDeg.toFixed(1)}°`,
          labelPosition,
        };

        setAngleDraft(null);
        commitShapes([...shapes, newShape]);
      },
      [angleDraft, commitShapes, dash, normalizeDegrees, shapes, strokeColor, strokeWidth, toDegrees, toRadians]
    );

    const handleRulerPoint = useCallback(
      (point) => {
        if (!rulerDraft) {
          setRulerDraft({
            id: createId("ruler"),
            start: point,
            cursor: point,
          });
          return;
        }

        const start = rulerDraft.start;
        const end = point;
        const distancePx = Math.hypot(end.x - start.x, end.y - start.y);
        const { label, displayValue } = formatDistance(distancePx);
        const midpoint = {
          x: (start.x + end.x) / 2,
          y: (start.y + end.y) / 2,
        };

        const newShape = {
          id: rulerDraft.id,
          type: "ruler",
          start,
          end,
          stroke: strokeColor,
          strokeWidth,
          dash,
          distancePx,
          distance: displayValue,
          unit: measurementUnit,
          label,
          midpoint,
        };

        setRulerDraft(null);
        commitShapes([...shapes, newShape]);
      },
      [commitShapes, dash, formatDistance, measurementUnit, rulerDraft, shapes, strokeColor, strokeWidth]
    );
    const beginDraft = useCallback(
      (stage) => {
        const point = getPointer(stage);
        const base = {
          id: createId(activeTool),
          stroke: strokeColor,
          strokeWidth,
          dash,
        };

        switch (activeTool) {
          case "rectangle":
            setDraft({
              type: "rect",
              origin: point,
              shape: { ...base, x: point.x, y: point.y, width: 0, height: 0 },
            });
            break;
          case "circle":
            setDraft({
              type: "circle",
              origin: point,
              shape: { ...base, x: point.x, y: point.y, radius: 0 },
            });
            break;
        case "line":
          case "arrow":
            setDraft({
              type: activeTool,
              shape: { ...base, x: 0, y: 0, points: [point.x, point.y, point.x, point.y] },
            });
            break;
        case "freehand":
            setDraft({
              type: "free",
              shape: {
                ...base,
                x: 0,
                y: 0,
                tension: 0,
                lineCap: "round",
                lineJoin: "round",
                points: [point.x, point.y],
              },
            });
            break;
        case "text":
          openTextEditor({
            id: base.id,
            x: point.x,
            y: point.y,
            fontSize: 18,
            stroke: strokeColor,
            value: "",
          });
          break;
        case "polygon":
          setPolygonDraft((prev) => {
            const points = prev ? [...prev.points, point] : [point];
            return { id: prev?.id || base.id, base, points };
          });
          break;
        case "eraser":
          eraserRemovedRef.current = false;
          eraserResultRef.current = null;
          setIsErasing(true);
          setEraserCursor(point);
          eraseAtPoint(point);
          break;
        default:
          break;
        }
      },
      [activeTool, commitShapes, dash, eraseAtPoint, openTextEditor, shapes, strokeColor, strokeWidth]
    );

    const updateDraft = useCallback(
      (stage) => {
        const point = getPointer(stage);
        setDraft((prev) => {
          if (!prev) return prev;
          const { shape } = prev;
          switch (prev.type) {
            case "rect":
              return {
                ...prev,
                shape: {
                  ...shape,
                  x: Math.min(prev.origin.x, point.x),
                  y: Math.min(prev.origin.y, point.y),
                  width: Math.abs(point.x - prev.origin.x),
                  height: Math.abs(point.y - prev.origin.y),
                },
              };
            case "circle":
              return {
                ...prev,
                shape: {
                  ...shape,
                  radius: Math.sqrt((point.x - prev.origin.x) ** 2 + (point.y - prev.origin.y) ** 2),
                },
              };
            case "line":
            case "arrow":
              return {
                ...prev,
                shape: {
                  ...shape,
                  points: [shape.points[0], shape.points[1], point.x, point.y],
                },
              };
            case "free":
              return {
                ...prev,
                shape: {
                  ...shape,
                  points: [...shape.points, point.x, point.y],
                },
              };
            default:
              return prev;
          }
        });
      },
      [getPointer]
    );

    const finishDraft = useCallback(() => {
      if (!draft) return;
      switch (draft.type) {
        case "rect":
          if (draft.shape.width > 2 && draft.shape.height > 2) {
            commitShapes([...shapes, { type: "rect", ...draft.shape }]);
          }
          break;
        case "circle":
          if (draft.shape.radius > 1) commitShapes([...shapes, { type: "circle", ...draft.shape }]);
          break;
        case "line":
        case "arrow":
          commitShapes([...shapes, { type: draft.type, ...draft.shape }]);
          break;
        case "free":
          if (draft.shape.points.length > 4) commitShapes([...shapes, { type: "free", ...draft.shape }]);
          break;
        default:
          break;
      }
      setDraft(null);
    }, [commitShapes, draft, shapes]);

    const handleStagePointerDown = useCallback(
      (evt) => {
        if (disabled) return;
        if (textEditor) {
          commitTextEditor(textAreaRef.current?.value ?? textEditor.value);
          return;
        }
        const stage = stageRef.current;
        if (!stage) return;
        const targetIsStage = evt.target === stage;
        if (activeTool === "select" || activeTool === "move") {
          if (targetIsStage) setSelectedId(null);
          return;
        }
        if (activeTool === "pan") {
          setIsPanning(true);
          const pointer = stage.getPointerPosition();
          pinchRef.current = {
            origin: { x: pointer.x - stagePosition.x, y: pointer.y - stagePosition.y },
          };
          return;
        }
        if (activeTool === "angle") {
          const point = getPointer(stage);
          handleAnglePoint(point);
          return;
        }
        if (activeTool === "ruler") {
          const point = getPointer(stage);
          handleRulerPoint(point);
          return;
        }
        beginDraft(stage);
      },
      [activeTool, beginDraft, commitTextEditor, disabled, getPointer, handleAnglePoint, handleRulerPoint, stagePosition.x, stagePosition.y, textEditor]
    );

    const handleStagePointerMove = useCallback(
      (evt) => {
        if (disabled) return;
        const stage = stageRef.current;
        if (!stage) return;

        if (!disabled && activeTool === "eraser") {
          setEraserCursor(getPointer(stage));
        } else if (eraserCursor) {
          setEraserCursor(null);
        }

        if (evt.evt.touches && evt.evt.touches.length === 2) {
          const [touch1, touch2] = evt.evt.touches;
          const distance = Math.hypot(touch1.clientX - touch2.clientX, touch1.clientY - touch2.clientY);
          if (!pinchRef.current?.dist) {
            pinchRef.current = { dist: distance, scale: scale, origin: pinchRef.current?.origin };
          } else {
            const nextScale = Math.min(Math.max((distance / pinchRef.current.dist) * pinchRef.current.scale, 0.2), 6);
            onZoomChange?.(nextScale);
          }
          return;
        }

        if (isPanning) {
          const pointer = stage.getPointerPosition();
          const origin = pinchRef.current?.origin || { x: 0, y: 0 };
          setStagePosition({
            x: pointer.x - origin.x,
            y: pointer.y - origin.y,
          });
          return;
        }

        if (activeTool === "angle" && angleDraft) {
          const pointer = getPointer(stage);
          setAngleDraft((prev) => {
            if (!prev) return prev;
            if (
              prev.cursor &&
              Math.abs(prev.cursor.x - pointer.x) < 0.5 &&
              Math.abs(prev.cursor.y - pointer.y) < 0.5
            ) {
              return prev;
            }
            return { ...prev, cursor: pointer };
          });
        }

        if (activeTool === "ruler" && rulerDraft) {
          const pointer = getPointer(stage);
          setRulerDraft((prev) => {
            if (!prev) return prev;
            if (
              prev.cursor &&
              Math.abs(prev.cursor.x - pointer.x) < 0.5 &&
              Math.abs(prev.cursor.y - pointer.y) < 0.5
            ) {
              return prev;
            }
            return { ...prev, cursor: pointer };
          });
        }

        if (isErasing) {
          const point = getPointer(stage);
          eraseAtPoint(point);
          return;
        }

        if (draft) {
          updateDraft(stage);
        }
      },
      [activeTool, angleDraft, disabled, draft, eraseAtPoint, eraserCursor, getPointer, isErasing, isPanning, onZoomChange, rulerDraft, scale, updateDraft]
    );

    const handleStagePointerUp = useCallback(() => {
      setEraserCursor(null);
      if (isPanning) {
        setIsPanning(false);
        pinchRef.current = null;
        pushHistory(shapesRef.current, stagePosition);
        return;
      }
      if (isErasing) {
        setIsErasing(false);
        if (eraserRemovedRef.current) {
          const resultShapes = eraserResultRef.current ?? shapesRef.current;
          pushHistory(resultShapes, stagePosition);
          eraserRemovedRef.current = false;
        }
        eraserResultRef.current = null;
        return;
      }
      if (draft) {
        finishDraft();
      }
    }, [draft, finishDraft, isErasing, isPanning, pushHistory, stagePosition]);

    const handleStageClick = useCallback(
      (evt) => {
        if (disabled) return;
        const stage = stageRef.current;
        if (!stage || (activeTool !== "select" && activeTool !== "move")) return;
        if (evt.target === stage) {
          setSelectedId(null);
          return;
        }
        const node = evt.target;
        if (node && node.id()) {
          setSelectedId(node.id());
        }
      },
      [activeTool, disabled]
    );

    const handleDoubleClick = useCallback(
      (evt) => {
        if (disabled) return;
        if (activeTool === "select") {
          const node = evt?.target;
          if (!node) return;
          const id = node.id?.();
          if (!id) return;
          const shape = shapes.find((s) => s.id === id);
          if (shape?.type === "text") {
            openTextEditor({
              id: shape.id,
              x: shape.x,
              y: shape.y,
              value: shape.text || "",
              fontSize: shape.fontSize || 18,
              stroke: shape.stroke,
            });
          }
        }
      },
      [activeTool, disabled, openTextEditor, shapes]
    );

    const handleWheel = useCallback(
      (evt) => {
        if (disabled) return;
        evt.evt.preventDefault();
        const stage = stageRef.current;
        if (!stage) return;
        const direction = evt.evt.deltaY > 0 ? -1 : 1;
        const scaleBy = 1.1;
        const oldScale = scale;
        const pointer = stage.getPointerPosition();
        const mousePointTo = {
          x: (pointer.x - stagePosition.x) / oldScale,
          y: (pointer.y - stagePosition.y) / oldScale,
        };
        const newScale = direction > 0 ? oldScale * scaleBy : oldScale / scaleBy;
        const clamped = Math.min(Math.max(newScale, 0.2), 6);
        onZoomChange?.(clamped);
        const newPos = {
          x: pointer.x - mousePointTo.x * clamped,
          y: pointer.y - mousePointTo.y * clamped,
        };
        setStagePosition(newPos);
      },
      [disabled, onZoomChange, scale, stagePosition.x, stagePosition.y]
    );

    useEffect(() => {
      if (activeTool !== "polygon") {
        setPolygonDraft(null);
      }
      if (activeTool !== "select") {
        setSelectedId(null);
      }
      if (activeTool !== "angle") {
        setAngleDraft(null);
      }
      if (activeTool !== "ruler") {
        setRulerDraft(null);
      }
      if (activeTool !== "eraser") {
        setIsErasing(false);
        setEraserCursor(null);
      }
    }, [activeTool]);

    useImperativeHandle(
      ref,
      () => ({
        exportState: () => ({ shapes, stagePosition }),
        importState: (snapshot) => applySnapshot(snapshot),
        undo: () => {
          if (historyRef.current.undo.length <= 1) return false;
          const current = historyRef.current.undo.pop();
          historyRef.current.redo.push(current);
          const prev = historyRef.current.undo[historyRef.current.undo.length - 1];
          applySnapshot(prev);
          onStateChange?.(prev);
          return true;
        },
        redo: () => {
          const snapshot = historyRef.current.redo.pop();
          if (!snapshot) return false;
          historyRef.current.undo.push(snapshot);
          applySnapshot(snapshot);
          onStateChange?.(snapshot);
          return true;
        },
        duplicateSelection: () => {
          if (!selectedId) return false;
          const shape = shapes.find((s) => s.id === selectedId);
          if (!shape) return false;
          if (shape.type === "ruler") {
            const dx = 20;
            const dy = 20;
            const clone = {
              ...shape,
              id: createId(shape.type),
              start: { x: shape.start.x + dx, y: shape.start.y + dy },
              end: { x: shape.end.x + dx, y: shape.end.y + dy },
              midpoint: { x: shape.midpoint.x + dx, y: shape.midpoint.y + dy },
            };
            commitShapes([...shapes, clone]);
            setSelectedId(clone.id);
            return true;
          }
          if (shape.type === "angle") {
            const dx = 20;
            const dy = 20;
            const clone = {
              ...shape,
              id: createId(shape.type),
              vertex: { x: shape.vertex.x + dx, y: shape.vertex.y + dy },
              pointA: { x: shape.pointA.x + dx, y: shape.pointA.y + dy },
              pointB: { x: shape.pointB.x + dx, y: shape.pointB.y + dy },
              labelPosition: shape.labelPosition
                ? { x: shape.labelPosition.x + dx, y: shape.labelPosition.y + dy }
                : undefined,
            };
            commitShapes([...shapes, clone]);
            setSelectedId(clone.id);
            return true;
          }
          const clone = {
            ...shape,
            id: createId(shape.type),
            x: (shape.x || 0) + 20,
            y: (shape.y || 0) + 20,
            points: shape.points
              ? shape.points.map((value, index) => value + (index % 2 === 0 ? 20 : 20))
              : shape.points,
          };
          commitShapes([...shapes, clone]);
          setSelectedId(clone.id);
          return true;
        },
        rotateSelection: (deg = 15) => {
          if (!selectedId) return false;
          updateShapeById(selectedId, (shape) => ({
            ...shape,
            rotation: (shape.rotation || 0) + deg,
          }));
          return true;
        },
        scaleSelection: (factor = 1.1) => {
          if (!selectedId) return false;
          const shape = shapes.find((s) => s.id === selectedId);
          if (shape?.type === "ruler" || shape?.type === "angle") {
            return false;
          }
          updateShapeById(selectedId, (shape) => ({
            ...shape,
            scaleX: (shape.scaleX || 1) * factor,
            scaleY: (shape.scaleY || 1) * factor,
          }));
          return true;
        },
        deleteSelection: () => {
          if (!selectedId) return false;
          commitShapes(shapes.filter((shape) => shape.id !== selectedId));
          setSelectedId(null);
          return true;
        },
        fitToScreen: () => fitStageToContainer(),
        toDataURL: () => stageRef.current?.toDataURL({ pixelRatio: 2 }) ?? null,
      }),
      [applySnapshot, commitShapes, fitStageToContainer, onStateChange, onZoomChange, pageDimensions?.width, selectedId, shapes, stagePosition, updateShapeById]
    );

    useEffect(() => {
      const stage = stageRef.current;
      const transformer = transformerRef.current;
      if (!stage || !transformer) return;
      if (activeTool !== "select" || !selectedId) {
        transformer.nodes([]);
        transformer.getLayer()?.batchDraw();
        return;
      }
      const node = stage.findOne(`#${selectedId}`);
      if (node) {
        transformer.nodes([node]);
        transformer.getLayer()?.batchDraw();
      }
    }, [activeTool, selectedId, shapes]);

    const handleDragEnd = useCallback(
      (id, evt) => {
        const { x, y } = evt.target.position();
        updateShapeById(id, (shape) => ({
          ...shape,
          x,
          y,
        }));
      },
      [updateShapeById]
    );

    const handleTransformEnd = useCallback(
      (id, evt) => {
        const node = evt.target;
        const scaleX = node.scaleX();
        const scaleY = node.scaleY();
        updateShapeById(id, (shape) => {
          const next = {
            ...shape,
            x: node.x(),
            y: node.y(),
            rotation: node.rotation(),
          };
          if (shape.type === "rect") {
            next.width = node.width() * scaleX;
            next.height = node.height() * scaleY;
          } else if (shape.type === "circle") {
            next.radius = node.radius() * ((scaleX + scaleY) / 2);
          } else if (shape.type === "text") {
            next.fontSize = node.fontSize() * scaleX;
          } else {
            next.scaleX = (shape.scaleX || 1) * scaleX;
            next.scaleY = (shape.scaleY || 1) * scaleY;
          }
          node.scaleX(1);
          node.scaleY(1);
          return next;
        });
      },
      [updateShapeById]
    );

    const handleMeasurementDragEnd = useCallback(
      (id, evt) => {
        const dx = evt.target.x();
        const dy = evt.target.y();
        evt.target.position({ x: 0, y: 0 });
        updateShapeById(id, (shape) => {
          if (shape.type === "ruler") {
            const start = { x: shape.start.x + dx, y: shape.start.y + dy };
            const end = { x: shape.end.x + dx, y: shape.end.y + dy };
            const midpoint = { x: shape.midpoint.x + dx, y: shape.midpoint.y + dy };
            return { ...shape, start, end, midpoint };
          }
          if (shape.type === "angle") {
            const vertex = { x: shape.vertex.x + dx, y: shape.vertex.y + dy };
            const pointA = { x: shape.pointA.x + dx, y: shape.pointA.y + dy };
            const pointB = { x: shape.pointB.x + dx, y: shape.pointB.y + dy };
            const labelPosition = {
              x: (shape.labelPosition?.x ?? vertex.x) + dx,
              y: (shape.labelPosition?.y ?? vertex.y) + dy,
            };
            return { ...shape, vertex, pointA, pointB, labelPosition };
          }
          return shape;
        });
      },
      [updateShapeById]
    );

    const renderedShapes = useMemo(
      () =>
        shapes.map((shape) => {
          if (shape.type === "ruler") {
            const draggable = !disabled && (activeTool === "select" || activeTool === "move");
            return (
              <Group
                key={shape.id}
                id={shape.id}
                listening={!disabled}
                draggable={draggable}
                onDragEnd={(evt) => handleMeasurementDragEnd(shape.id, evt)}
              >
                <Line
                  stroke={shape.stroke}
                  strokeWidth={shape.strokeWidth}
                  dash={shape.dash}
                  points={[shape.start.x, shape.start.y, shape.end.x, shape.end.y]}
                  hitStrokeWidth={Math.max(shape.strokeWidth * 4, 24)}
                />
                <Circle x={shape.start.x} y={shape.start.y} radius={6} fill={shape.stroke} opacity={0.85} />
                <Circle x={shape.end.x} y={shape.end.y} radius={6} fill={shape.stroke} opacity={0.85} />
                <Text
                  text={shape.label}
                  x={shape.midpoint.x - 80}
                  y={shape.midpoint.y - 32}
                  width={160}
                  align="center"
                  fontSize={14}
                  fontStyle="600"
                  fill={shape.stroke}
                  listening={false}
                />
              </Group>
            );
          }

          if (shape.type === "angle") {
            const draggable = !disabled && (activeTool === "select" || activeTool === "move");
            return (
              <Group
                key={shape.id}
                id={shape.id}
                listening={!disabled}
                draggable={draggable}
                onDragEnd={(evt) => handleMeasurementDragEnd(shape.id, evt)}
              >
                <Line
                  stroke={shape.stroke}
                  strokeWidth={shape.strokeWidth}
                  dash={shape.dash}
                  points={[shape.vertex.x, shape.vertex.y, shape.pointA.x, shape.pointA.y]}
                  hitStrokeWidth={Math.max(shape.strokeWidth * 4, 24)}
                />
                <Line
                  stroke={shape.stroke}
                  strokeWidth={shape.strokeWidth}
                  dash={shape.dash}
                  points={[shape.vertex.x, shape.vertex.y, shape.pointB.x, shape.pointB.y]}
                  hitStrokeWidth={Math.max(shape.strokeWidth * 4, 24)}
                />
                <Arc
                  x={shape.vertex.x}
                  y={shape.vertex.y}
                  innerRadius={Math.max(shape.radius - 3, 2)}
                  outerRadius={shape.radius + 3}
                  angle={shape.sweep}
                  rotation={shape.startDeg}
                  stroke={shape.stroke}
                  strokeWidth={1.5}
                  listening={false}
                />
                <Circle x={shape.vertex.x} y={shape.vertex.y} radius={6} fill={shape.stroke} opacity={0.9} />
                <Text
                  text={shape.label}
                  x={(shape.labelPosition?.x ?? shape.vertex.x) - 80}
                  y={(shape.labelPosition?.y ?? shape.vertex.y) - 16}
                  width={160}
                  align="center"
                  fontSize={14}
                  fontStyle="600"
                  fill={shape.stroke}
                  listening={false}
                />
              </Group>
            );
          }

          const common = {
            id: shape.id,
            stroke: shape.stroke,
            strokeWidth: shape.strokeWidth,
            dash: shape.dash,
            listening: !disabled && activeTool !== "pan",
            draggable: !disabled && (activeTool === "select" || activeTool === "move"),
            onDragEnd: (evt) => handleDragEnd(shape.id, evt),
            onTransformEnd: (evt) => handleTransformEnd(shape.id, evt),
            rotation: shape.rotation || 0,
            scaleX: shape.scaleX || 1,
            scaleY: shape.scaleY || 1,
          };
          switch (shape.type) {
            case "rect":
              return <Rect key={shape.id} {...common} x={shape.x} y={shape.y} width={shape.width} height={shape.height} />;
            case "circle":
              return <Circle key={shape.id} {...common} x={shape.x} y={shape.y} radius={shape.radius} />;
            case "line":
              return (
                <Line
                  key={shape.id}
                  {...common}
                  x={shape.x || 0}
                  y={shape.y || 0}
                  points={shape.points}
                  hitStrokeWidth={Math.max(shape.strokeWidth * 4, 20)}
                />
              );
            case "arrow":
              return (
                <Arrow
                  key={shape.id}
                  {...common}
                  x={shape.x || 0}
                  y={shape.y || 0}
                  points={shape.points}
                  pointerWidth={14}
                  pointerLength={18}
                  hitStrokeWidth={Math.max(shape.strokeWidth * 4, 24)}
                />
              );
            case "free":
              return (
                <Line
                  key={shape.id}
                  {...common}
                  x={shape.x || 0}
                  y={shape.y || 0}
                  points={shape.points}
                  lineCap="round"
                  lineJoin="round"
                  hitStrokeWidth={Math.max(shape.strokeWidth * 4, 24)}
                />
              );
            case "polygon":
              return (
                <Line
                  key={shape.id}
                  {...common}
                  x={shape.x || 0}
                  y={shape.y || 0}
                  points={shape.points}
                  closed
                  hitStrokeWidth={Math.max(shape.strokeWidth * 4, 24)}
                />
              );
            case "text":
              return (
                <Text
                  key={shape.id}
                  {...common}
                  x={shape.x}
                  y={shape.y}
                  text={shape.text}
                  fontSize={shape.fontSize || 18}
                  fill={shape.stroke}
                />
              );
            default:
              return null;
          }
        }),
      [activeTool, disabled, handleDragEnd, handleMeasurementDragEnd, handleTransformEnd, shapes]
    );

    if (!pageImage || !pageDimensions?.width) {
      return (
        <div ref={containerRef} className="flex h-full w-full items-center justify-center bg-slate-950 text-slate-300">
          Loading…
        </div>
      );
    }

    return (
      <div ref={containerRef} className="relative h-full w-full overflow-hidden bg-slate-950">
        <Stage
          ref={stageRef}
          width={containerDimensions.width}
          height={containerDimensions.height}
          scaleX={scale}
          scaleY={scale}
          x={stagePosition.x}
          y={stagePosition.y}
          onWheel={handleWheel}
          onMouseDown={handleStagePointerDown}
          onTouchStart={handleStagePointerDown}
          onMouseMove={handleStagePointerMove}
          onTouchMove={handleStagePointerMove}
          onMouseUp={handleStagePointerUp}
          onTouchEnd={handleStagePointerUp}
          onClick={handleStageClick}
          onTap={handleStageClick}
          onDblClick={handleDoubleClick}
          onDoubleTap={handleDoubleClick}
        >
          <Layer listening={false}>
            <BackgroundImage src={pageImage} width={pageDimensions.width} height={pageDimensions.height} />
          </Layer>
          <Layer>
            {renderedShapes}
            {polygonDraft && (
              <Line
                points={polygonDraft.points.flatMap((p) => [p.x, p.y])}
                stroke={polygonDraft.base.stroke}
                strokeWidth={polygonDraft.base.strokeWidth}
                dash={polygonDraft.base.dash}
              />
            )}
            {rulerDraft && rulerDraft.start && rulerDraft.cursor && (
              <>
                <Line
                  points={[rulerDraft.start.x, rulerDraft.start.y, rulerDraft.cursor.x, rulerDraft.cursor.y]}
                  stroke={strokeColor}
                  strokeWidth={strokeWidth}
                  dash={dash}
                  listening={false}
                />
                {(() => {
                  const distancePx = Math.hypot(rulerDraft.cursor.x - rulerDraft.start.x, rulerDraft.cursor.y - rulerDraft.start.y);
                  const { label } = formatDistance(distancePx);
                  const midpoint = {
                    x: (rulerDraft.start.x + rulerDraft.cursor.x) / 2,
                    y: (rulerDraft.start.y + rulerDraft.cursor.y) / 2,
                  };
                  return (
                    <Text
                      text={label}
                      x={midpoint.x - 80}
                      y={midpoint.y - 32}
                      width={160}
                      align="center"
                      fontSize={14}
                      fontStyle="600"
                      fill={strokeColor}
                      listening={false}
                    />
                  );
                })()}
              </>
            )}
            {angleDraft && (
              <>
                {angleDraft.cursor && (
                  <Line
                    points={[
                      angleDraft.vertex.x,
                      angleDraft.vertex.y,
                      (angleDraft.first ?? angleDraft.cursor).x,
                      (angleDraft.first ?? angleDraft.cursor).y,
                    ]}
                    stroke={strokeColor}
                    strokeWidth={strokeWidth}
                    dash={dash}
                    listening={false}
                  />
                )}
                {angleDraft.first && angleDraft.cursor && (
                  <Line
                    points={[angleDraft.vertex.x, angleDraft.vertex.y, angleDraft.cursor.x, angleDraft.cursor.y]}
                    stroke={strokeColor}
                    strokeWidth={strokeWidth}
                    dash={dash}
                    listening={false}
                  />
                )}
                <Circle x={angleDraft.vertex.x} y={angleDraft.vertex.y} radius={5} fill={strokeColor} opacity={0.9} listening={false} />
              </>
            )}
            {draft &&
              (() => {
                const { shape } = draft;
                const common = { stroke: shape.stroke, strokeWidth: shape.strokeWidth, dash: shape.dash };
                switch (draft.type) {
                  case "rect":
                    return <Rect {...common} x={shape.x} y={shape.y} width={shape.width} height={shape.height} />;
                  case "circle":
                    return <Circle {...common} x={shape.x} y={shape.y} radius={shape.radius} />;
                  case "line":
                    return <Line {...common} points={shape.points} />;
                  case "arrow":
                    return <Arrow {...common} points={shape.points} pointerWidth={14} pointerLength={18} />;
                  case "free":
                    return <Line {...common} points={shape.points} lineCap="round" lineJoin="round" />;
                  default:
                    return null;
                }
              })()}
            {eraserCursor && activeTool === "eraser" && (
              <Circle
                x={eraserCursor.x}
                y={eraserCursor.y}
                radius={ERASER_RADIUS}
                stroke="#f97316"
                strokeWidth={1.5}
                dash={[6, 6]}
                listening={false}
              />
            )}
            <Transformer ref={transformerRef} rotateEnabled flipEnabled={false} />
          </Layer>
        </Stage>
        {textEditor && textEditorStyle && (
          <textarea
            ref={textAreaRef}
            defaultValue={textEditor.value}
            className="absolute rounded-lg border border-slate-500/60 bg-slate-900/95 text-slate-100 shadow-lg focus:outline-none focus:ring-2 focus:ring-blue-500/70"
            style={{
              top: `${textEditorStyle.top}px`,
              left: `${textEditorStyle.left}px`,
              transform: textEditorStyle.transform,
              transformOrigin: textEditorStyle.transformOrigin,
              width: 220,
              minHeight: 48,
              padding: 12,
              fontSize: `${textEditor.fontSize}px`,
              lineHeight: 1.4,
              zIndex: 20,
              resize: "both",
            }}
            onBlur={(event) => commitTextEditor(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                commitTextEditor(event.currentTarget.value);
              }
              if (event.key === "Escape") {
                event.preventDefault();
                setTextEditor(null);
              }
            }}
          />
        )}
      </div>
    );
  }
);

CadCanvasEditor.displayName = "CadCanvasEditor";

export default CadCanvasEditor;

