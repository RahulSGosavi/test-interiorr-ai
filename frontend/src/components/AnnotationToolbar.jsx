import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  MousePointer,
  Minus,
  Square,
  Circle,
  Type,
  Pencil,
  Shapes,
  ArrowUpRight,
  Move,
  Copy,
  RotateCw,
  Expand,
  Hand,
  Undo2,
  Redo2,
  ZoomIn,
  ZoomOut,
  Maximize,
  Download,
  Save,
  ChevronLeft,
  ChevronRight,
  Eraser,
  Ruler,
  Compass
} from 'lucide-react';

const mainTools = [
  { id: 'select', icon: MousePointer, label: 'Select', shortcut: 'S' },
  { id: 'rectangle', icon: Square, label: 'Rectangle', shortcut: 'R' },
  { id: 'circle', icon: Circle, label: 'Ellipse', shortcut: 'C' },
  { id: 'line', icon: Minus, label: 'Line', shortcut: 'L' },
  { id: 'arrow', icon: ArrowUpRight, label: 'Arrow', shortcut: 'A' },
  { id: 'polygon', icon: Shapes, label: 'Polygon', shortcut: 'P' },
  { id: 'freehand', icon: Pencil, label: 'Free Draw', shortcut: 'F' },
  { id: 'text', icon: Type, label: 'Text', shortcut: 'T' },
  { id: 'eraser', icon: Eraser, label: 'Eraser', shortcut: 'E' },
  { id: 'angle', icon: Compass, label: 'Angle', shortcut: 'G' },
  { id: 'ruler', icon: Ruler, label: 'Measure', shortcut: 'U' },
];

const navigationTools = [
  { id: 'pan', icon: Hand, label: 'Pan Tool', shortcut: 'Space' },
  { id: 'move', icon: Move, label: 'Move Tool', shortcut: 'M' },
];

const AnnotationToolbar = ({
  activeTool,
  onToolSelect,
  onUndo,
  onRedo,
  onZoomIn,
  onZoomOut,
  onFitToScreen,
  onCopy,
  onRotate,
  onScale,
  onSave,
  onDownload,
  onPrevPage,
  onNextPage,
  currentPage,
  numPages,
  disabled = false
}) => {
  const renderToolButton = (tool) => {
    const Icon = tool.icon;
    const isActive = activeTool === tool.id;

    return (
      <Tooltip key={tool.id}>
        <TooltipTrigger asChild>
          <Button
            variant={isActive ? 'default' : 'outline'}
            size="sm"
            onClick={() => onToolSelect(tool.id)}
            disabled={disabled}
            className={`h-16 flex flex-col items-center justify-center gap-1 rounded-xl transition-all disabled:cursor-not-allowed disabled:opacity-50 ${
              isActive
                ? 'bg-blue-500/90 text-white shadow-lg shadow-blue-500/30 border-blue-400'
                : 'bg-slate-900/60 border-slate-700 text-slate-200 hover:text-white hover:bg-slate-800'
            }`}
            data-testid={`tool-${tool.id}`}
          >
            <Icon className="w-5 h-5" />
            <span className="text-[10px] font-medium leading-tight text-center">{tool.label}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">
          <div className="text-xs">
            <p className="font-semibold">{tool.label}</p>
            {tool.shortcut && (
              <p className="text-slate-400 font-normal">Shortcut: {tool.shortcut}</p>
            )}
          </div>
        </TooltipContent>
      </Tooltip>
    );
  };

  return (
    <TooltipProvider>
      <aside
        className="w-72 bg-slate-950 border-r border-slate-900 shadow-[0_40px_80px_rgba(8,15,35,0.65)] flex flex-col"
        data-testid="annotation-toolbar"
      >
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
          <section>
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500 mb-3">Draw Tools</p>
            <div className="grid grid-cols-3 gap-3">
              {mainTools.map(renderToolButton)}
              {navigationTools.map(renderToolButton)}
            </div>
          </section>

          <section className="space-y-3">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">History</p>
            <div className="grid grid-cols-2 gap-3">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onUndo}
                    disabled={disabled}
                    className="h-12 bg-slate-900/70 border-slate-800 text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                    data-testid="undo-button"
                  >
                    <Undo2 className="w-4 h-4 mr-2" />
                    Undo
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="font-normal">Undo (Ctrl+Z)</p>
                </TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onRedo}
                    disabled={disabled}
                    className="h-12 bg-slate-900/70 border-slate-800 text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                    data-testid="redo-button"
                  >
                    <Redo2 className="w-4 h-4 mr-2" />
                    Redo
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="font-normal">Redo (Ctrl+Y)</p>
                </TooltipContent>
              </Tooltip>
            </div>
          </section>

          <section className="space-y-3">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Transform</p>
            <div className="grid grid-cols-3 gap-3">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onCopy}
                    disabled={disabled}
                    className="h-12 bg-slate-900/70 border-slate-800 text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                    data-testid="copy-button"
                  >
                    <Copy className="w-4 h-4 mr-2" />
                    Copy
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="font-normal">Duplicate selection (Ctrl+D)</p>
                </TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onRotate}
                    disabled={disabled}
                    className="h-12 bg-slate-900/70 border-slate-800 text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                    data-testid="rotate-button"
                  >
                    <RotateCw className="w-4 h-4 mr-2" />
                    Rotate
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="font-normal">Rotate 15°</p>
                </TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={onScale}
                    disabled={disabled}
                    className="h-12 bg-slate-900/70 border-slate-800 text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                    data-testid="scale-button"
                  >
                    <Expand className="w-4 h-4 mr-2" />
                    Scale
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="font-normal">Scale up 10%</p>
                </TooltipContent>
              </Tooltip>
            </div>
          </section>

          <section className="space-y-3">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Zoom & Fit</p>
            <div className="grid grid-cols-3 gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={onZoomIn}
                disabled={disabled}
                className="h-12 bg-slate-900/70 border-slate-800 text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                data-testid="zoom-in-button"
              >
                <ZoomIn className="w-4 h-4 mr-2" />
                Zoom+
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={onZoomOut}
                disabled={disabled}
                className="h-12 bg-slate-900/70 border-slate-800 text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                data-testid="zoom-out-button"
              >
                <ZoomOut className="w-4 h-4 mr-2" />
                Zoom-
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={onFitToScreen}
                disabled={disabled}
                className="h-12 bg-slate-900/70 border-slate-800 text-slate-200 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                data-testid="fit-button"
              >
                <Maximize className="w-4 h-4 mr-2" />
                Fit
              </Button>
            </div>
          </section>

          <section className="space-y-3">
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Page Navigation</p>
            <div className="grid grid-cols-2 gap-3">
              <Button
                variant="outline"
                size="sm"
                onClick={onPrevPage}
                disabled={disabled || currentPage <= 1}
                className="h-12 bg-slate-900/70 border-slate-800 text-slate-200 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
                data-testid="toolbar-prev-page"
              >
                <ChevronLeft className="w-4 h-4 mr-2" />
                Prev
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={onNextPage}
                disabled={disabled || currentPage >= numPages}
                className="h-12 bg-slate-900/70 border-slate-800 text-slate-200 hover:bg-slate-800 disabled:opacity-40 disabled:cursor-not-allowed"
                data-testid="toolbar-next-page"
              >
                Next
                <ChevronRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
            <p className="text-xs text-slate-400 text-center">Page {currentPage} of {numPages}</p>
          </section>
        </div>

        <div className="px-4 py-5 border-t border-slate-900 space-y-3 bg-slate-950/95">
          <Button
            variant="outline"
            size="sm"
            onClick={onDownload}
            disabled={disabled}
            className="w-full h-12 bg-blue-600/90 border-blue-500 text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="download-pdf-button"
          >
            <Download className="w-4 h-4 mr-2" />
            Download PDF
          </Button>
          <Button
            size="sm"
            onClick={onSave}
            disabled={disabled}
            className="w-full h-12 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold shadow-lg shadow-emerald-500/25 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="save-annotations-button"
          >
            <Save className="w-4 h-4 mr-2" />
            Save Changes
          </Button>
        </div>
      </aside>
    </TooltipProvider>
  );
};

export default AnnotationToolbar;
