export const DEFAULT_GRID_SIZE = 10;
export const DEFAULT_STROKE_COLOR = "#f97316";
export const DEFAULT_STROKE_WIDTH = 2;

export const snapValue = (value, gridSize = DEFAULT_GRID_SIZE) =>
  Math.round(value / gridSize) * gridSize;

export const snapPoint = (point, gridSize = DEFAULT_GRID_SIZE) => ({
  x: snapValue(point.x, gridSize),
  y: snapValue(point.y, gridSize),
});

export const distanceBetween = (a, b) =>
  Math.hypot((b?.x ?? 0) - (a?.x ?? 0), (b?.y ?? 0) - (a?.y ?? 0));

export const midpoint = (a, b) => ({
  x: ((a?.x ?? 0) + (b?.x ?? 0)) / 2,
  y: ((a?.y ?? 0) + (b?.y ?? 0)) / 2,
});

export const angleRadians = (a, b) =>
  Math.atan2((b?.y ?? 0) - (a?.y ?? 0), (b?.x ?? 0) - (a?.x ?? 0));

export const angleDegrees = (a, b) => (angleRadians(a, b) * 180) / Math.PI;

export const toFixed = (value, digits = 2) =>
  Number.parseFloat(value ?? 0).toFixed(digits);

export const measurementLabel = (value) => `${toFixed(value, 2)} px`;

const ensurePoint = (point, fallback = { x: 0, y: 0 }) =>
  typeof point === "object" && point
    ? { x: Number(point.x) || 0, y: Number(point.y) || 0 }
    : { ...fallback };

const ensureColor = (color) =>
  typeof color === "string" && color.trim().length ? color : DEFAULT_STROKE_COLOR;

export const ensureLine = (line) => {
  if (!line) return null;
  if (line.start && line.end) {
    return {
      ...line,
      start: ensurePoint(line.start),
      end: ensurePoint(line.end),
      id: line.id ?? crypto.randomUUID?.() ?? `line-${Date.now()}`,
      strokeColor: ensureColor(line.strokeColor ?? line.color),
      strokeWidth: Number(line.strokeWidth) || DEFAULT_STROKE_WIDTH,
    };
  }

  if (Array.isArray(line.points) && line.points.length >= 4) {
    const [x1, y1, x2, y2] = line.points;
    return {
      ...line,
      start: ensurePoint({ x: x1, y: y1 }),
      end: ensurePoint({ x: x2, y: y2 }),
      id: line.id ?? crypto.randomUUID?.() ?? `line-${Date.now()}`,
      strokeColor: ensureColor(line.strokeColor ?? line.color),
      strokeWidth: Number(line.strokeWidth) || DEFAULT_STROKE_WIDTH,
    };
  }

  return null;
};

export const ensureArrow = (arrow) => {
  const normalized = ensureLine(arrow);
  if (!normalized) return null;
  return {
    ...normalized,
    pointerLength: arrow?.pointerLength ?? 16,
    pointerWidth: arrow?.pointerWidth ?? 12,
  };
};

export const ensureRectangle = (rect) => {
  if (!rect) return null;
  const id = rect.id ?? crypto.randomUUID?.() ?? `rect-${Date.now()}`;
  const rotation = Number(rect.rotation) || 0;

  if (rect.start && rect.end) {
    const start = ensurePoint(rect.start);
    const end = ensurePoint(rect.end);
    return {
      ...rect,
      id,
      x: Math.min(start.x, end.x),
      y: Math.min(start.y, end.y),
      width: Math.abs(end.x - start.x),
      height: Math.abs(end.y - start.y),
      rotation,
      strokeColor: ensureColor(rect.strokeColor ?? rect.color),
      strokeWidth: Number(rect.strokeWidth) || DEFAULT_STROKE_WIDTH,
    };
  }

  const hasWidthHeight =
    typeof rect.x === "number" &&
    typeof rect.y === "number" &&
    typeof rect.width === "number" &&
    typeof rect.height === "number";

  if (hasWidthHeight) {
    return {
      ...rect,
      id,
      x: Number(rect.x) || 0,
      y: Number(rect.y) || 0,
      width: Number(rect.width) || 0,
      height: Number(rect.height) || 0,
      rotation,
      strokeColor: ensureColor(rect.strokeColor ?? rect.color),
      strokeWidth: Number(rect.strokeWidth) || DEFAULT_STROKE_WIDTH,
    };
  }

  return null;
};

export const ensureCircle = (circle) => {
  if (!circle) return null;
  if (circle.center && typeof circle.radius === "number") {
    return {
      ...circle,
      center: ensurePoint(circle.center),
      radius: Math.max(Number(circle.radius) || 0, 0),
      id: circle.id ?? crypto.randomUUID?.() ?? `circle-${Date.now()}`,
      strokeColor: ensureColor(circle.strokeColor ?? circle.color),
      strokeWidth: Number(circle.strokeWidth) || DEFAULT_STROKE_WIDTH,
    };
  }

  if (
    typeof circle.x === "number" &&
    typeof circle.y === "number" &&
    typeof circle.radius === "number"
  ) {
    return {
      ...circle,
      center: ensurePoint({ x: circle.x, y: circle.y }),
      radius: Math.max(Number(circle.radius) || 0, 0),
      id: circle.id ?? crypto.randomUUID?.() ?? `circle-${Date.now()}`,
      strokeColor: ensureColor(circle.strokeColor ?? circle.color),
      strokeWidth: Number(circle.strokeWidth) || DEFAULT_STROKE_WIDTH,
    };
  }

  return null;
};

export const lineToKonva = (line) => {
  const normalized = ensureLine(line);
  if (!normalized) return null;
  const { start, end } = normalized;
  return {
    id: normalized.id,
    points: [start.x, start.y, end.x, end.y],
    stroke: normalized.strokeColor,
    strokeWidth: normalized.strokeWidth,
    lineCap: "round",
    lineJoin: "round",
    listening: true,
  };
};

export const arrowToKonva = (arrow) => {
  const normalized = ensureArrow(arrow);
  if (!normalized) return null;
  const { start, end } = normalized;
  return {
    id: normalized.id,
    points: [start.x, start.y, end.x, end.y],
    stroke: normalized.strokeColor,
    fill: normalized.strokeColor,
    strokeWidth: normalized.strokeWidth,
    pointerLength: normalized.pointerLength,
    pointerWidth: normalized.pointerWidth,
    listening: true,
  };
};

export const rectangleToKonva = (rect) => {
  const normalized = ensureRectangle(rect);
  if (!normalized) return null;
  return {
    id: normalized.id,
    x: normalized.x,
    y: normalized.y,
    width: normalized.width,
    height: normalized.height,
    rotation: normalized.rotation,
    stroke: normalized.strokeColor,
    strokeWidth: normalized.strokeWidth,
    listening: true,
  };
};

export const circleToKonva = (circle) => {
  const normalized = ensureCircle(circle);
  if (!normalized) return null;
  return {
    id: normalized.id,
    x: normalized.center.x,
    y: normalized.center.y,
    radius: normalized.radius,
    stroke: normalized.strokeColor,
    strokeWidth: normalized.strokeWidth,
    listening: true,
  };
};

export const rectSize = (rect) => {
  const normalized = ensureRectangle(rect);
  if (!normalized) return { width: 0, height: 0 };
  return {
    width: normalized.width,
    height: normalized.height,
  };
};

export const circleDiameter = (circle) => {
  const normalized = ensureCircle(circle);
  return normalized ? normalized.radius * 2 : 0;
};

export const buildGridLines = (width, height, gridSize = DEFAULT_GRID_SIZE) => {
  const vertical = [];
  const horizontal = [];
  for (let x = 0; x <= width; x += gridSize) {
    vertical.push({ points: [x, 0, x, height] });
  }
  for (let y = 0; y <= height; y += gridSize) {
    horizontal.push({ points: [0, y, width, y] });
  }
  return { vertical, horizontal };
};

export const getStageRelativeTransform = (node, stage) => {
  if (!node || !stage) return null;
  const absolute = node.getAbsoluteTransform().copy();
  const stageTransform = stage.getAbsoluteTransform().copy();
  const invertedStage = stageTransform.invert();
  return invertedStage.multiply(absolute);
};

export const applyTransformToPoint = (matrix, point) => {
  if (!matrix) return ensurePoint(point);
  return matrix.point(point);
};

export const transformLineGeometry = (line, node, stage) => {
  const normalized = ensureLine(line);
  if (!normalized) return null;
  const transform = getStageRelativeTransform(node, stage);
  if (!transform) return normalized;
  const transformedStart = applyTransformToPoint(transform, normalized.start);
  const transformedEnd = applyTransformToPoint(transform, normalized.end);
  return {
    ...normalized,
    start: transformedStart,
    end: transformedEnd,
  };
};

export const transformRectangleGeometry = (rect, node, stage) => {
  const normalized = ensureRectangle(rect);
  if (!normalized) return null;
  if (!node || !stage) return normalized;

  const width = node.width() * node.scaleX();
  const height = node.height() * node.scaleY();
  const position = node.absolutePosition();
  const stageTransform = stage.getAbsoluteTransform().copy();
  const invertedStage = stageTransform.invert();
  const topLeft = invertedStage.point(position);

  return {
    ...normalized,
    x: topLeft.x,
    y: topLeft.y,
    width,
    height,
    rotation: node.rotation(),
  };
};

export const transformCircleGeometry = (circle, node, stage) => {
  const normalized = ensureCircle(circle);
  if (!normalized) return null;
  const transform = getStageRelativeTransform(node, stage);
  if (!transform) return normalized;
  const center = applyTransformToPoint(transform, normalized.center);
  const radiusVector = applyTransformToPoint(transform, {
    x: normalized.center.x + normalized.radius,
    y: normalized.center.y,
  });
  const radius = Math.abs(radiusVector.x - center.x);
  return {
    ...normalized,
    center,
    radius,
  };
};

export const transformArrowGeometry = transformLineGeometry;

export const toSerializable = (shape) => {
  if (!shape) return shape;
  if (shape.start && shape.end) {
    return {
      id: shape.id,
      type: shape.type,
      start: shape.start,
      end: shape.end,
      strokeColor: shape.strokeColor ?? shape.color ?? DEFAULT_STROKE_COLOR,
      strokeWidth: shape.strokeWidth ?? DEFAULT_STROKE_WIDTH,
      pointerLength: shape.pointerLength,
      pointerWidth: shape.pointerWidth,
    };
  }
  if (shape.center && typeof shape.radius === "number") {
    return {
      id: shape.id,
      type: shape.type,
      center: shape.center,
      radius: shape.radius,
      strokeColor: shape.strokeColor ?? shape.color ?? DEFAULT_STROKE_COLOR,
      strokeWidth: shape.strokeWidth ?? DEFAULT_STROKE_WIDTH,
    };
  }
  if (
    typeof shape.x === "number" &&
    typeof shape.y === "number" &&
    typeof shape.width === "number" &&
    typeof shape.height === "number"
  ) {
    return {
      id: shape.id,
      type: shape.type,
      x: shape.x,
      y: shape.y,
      width: shape.width,
      height: shape.height,
      rotation: shape.rotation ?? 0,
      strokeColor: shape.strokeColor ?? shape.color ?? DEFAULT_STROKE_COLOR,
      strokeWidth: shape.strokeWidth ?? DEFAULT_STROKE_WIDTH,
    };
  }
  return shape;
};

export const buildDimensionData = (shape) => {
  if (!shape) return null;
  if (shape.start && shape.end && !shape.width && !shape.height) {
    const length = distanceBetween(shape.start, shape.end);
    const angle = angleDegrees(shape.start, shape.end);
    const anchor = midpoint(shape.start, shape.end);
    return {
      label: measurementLabel(length),
      length,
      angle,
      anchor,
    };
  }
  if (typeof shape.width === "number" && typeof shape.height === "number") {
    const anchor = {
      x: shape.x + shape.width / 2,
      y: shape.y + shape.height / 2,
    };
    return {
      label: `${measurementLabel(shape.width)} × ${measurementLabel(shape.height)}`,
      anchor,
      angle: shape.rotation ?? 0,
    };
  }
  if (shape.center && typeof shape.radius === "number") {
    const diameter = shape.radius * 2;
    return {
      label: `Ø ${measurementLabel(diameter)}`,
      length: diameter,
      angle: 0,
      anchor: { ...shape.center, y: shape.center.y - shape.radius },
    };
  }
  if (shape.start && shape.size) {
    const { size } = shape;
    return {
      label: `${measurementLabel(size.width)} × ${measurementLabel(size.height)}`,
      anchor: midpoint(shape.start, {
        x: shape.start.x + size.width,
        y: shape.start.y + size.height,
      }),
      angle: 0,
    };
  }
  return null;
};
