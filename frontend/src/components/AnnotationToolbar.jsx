import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import {
  MousePointer,
  Minus,
  Square,
  Circle,
  Type,
  Shapes,
  ArrowUpRight,
  Move,
  Hand,
  Undo2,
  Redo2,
  Ruler,
  Compass,
  Trash2
} from 'lucide-react';

// Custom Pencil Icon
const PencilIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
    <path d="m15 5 4 4" />
  </svg>
);

// Custom Eraser Icon
const EraserIcon = ({ className }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="m7 21-4.3-4.3c-1-1-1-2.5 0-3.4l9.6-9.6c1-1 2.5-1 3.4 0l5.6 5.6c1 1 1 2.5 0 3.4L13 21" />
    <path d="M22 21H7" />
    <path d="m5 11 9 9" />
  </svg>
);

const toolGroups = [
  {
    name: 'Select',
    tools: [
      { id: 'select', icon: MousePointer, label: 'Select', shortcut: 'S' },
      { id: 'move', icon: Move, label: 'Move', shortcut: 'M' },
      { id: 'pan', icon: Hand, label: 'Pan', shortcut: 'Space' },
    ]
  },
  {
    name: 'Draw',
    tools: [
      { id: 'rectangle', icon: Square, label: 'Rectangle', shortcut: 'R' },
      { id: 'circle', icon: Circle, label: 'Ellipse', shortcut: 'C' },
      { id: 'line', icon: Minus, label: 'Line', shortcut: 'L' },
      { id: 'arrow', icon: ArrowUpRight, label: 'Arrow', shortcut: 'A' },
      { id: 'polygon', icon: Shapes, label: 'Polygon', shortcut: 'P' },
    ]
  },
  {
    name: 'Annotate',
    tools: [
      { id: 'freehand', icon: PencilIcon, label: 'Pencil', shortcut: 'F' },
      { id: 'text', icon: Type, label: 'Text', shortcut: 'T' },
      { id: 'eraser', icon: EraserIcon, label: 'Eraser', shortcut: 'E' },
    ]
  },
  {
    name: 'Measure',
    tools: [
      { id: 'ruler', icon: Ruler, label: 'Measure', shortcut: 'U' },
      { id: 'angle', icon: Compass, label: 'Angle', shortcut: 'G' },
    ]
  },
];

const AnnotationToolbar = ({
  activeTool,
  onToolSelect,
  onUndo,
  onRedo,
  zoom = 1,
  currentPage = 1,
  numPages = 1,
  disabled = false
}) => {
  return (
    <TooltipProvider delayDuration={100}>
      <footer className="bg-gradient-to-t from-[#0d0f12] to-[#1a1d24] border-t border-[#2a2e38] px-4 py-2">
        <div className="flex items-center justify-center gap-2">
          {/* Undo/Redo */}
          <div className="flex items-center gap-1 px-2 py-1 bg-[#12141a] rounded-lg border border-[#2a2e38]">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onUndo}
                  disabled={disabled}
                  className="w-9 h-9 text-slate-400 hover:text-white hover:bg-[#2a2e38] disabled:opacity-30 rounded-md"
                >
                  <Undo2 className="w-4 h-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top" className="bg-[#1a1d24] border-[#3a3e48]">
                <p className="text-xs">Undo <span className="text-slate-500">Ctrl+Z</span></p>
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={onRedo}
                  disabled={disabled}
                  className="w-9 h-9 text-slate-400 hover:text-white hover:bg-[#2a2e38] disabled:opacity-30 rounded-md"
                >
                  <Redo2 className="w-4 h-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="top" className="bg-[#1a1d24] border-[#3a3e48]">
                <p className="text-xs">Redo <span className="text-slate-500">Ctrl+Y</span></p>
              </TooltipContent>
            </Tooltip>
          </div>

          <div className="w-px h-10 bg-[#2a2e38]" />

          {/* Tool Groups */}
          {toolGroups.map((group, groupIndex) => (
            <div key={group.name} className="flex items-center">
              <div className="flex flex-col items-center">
                <div className="flex items-center gap-0.5 px-2 py-1 bg-[#12141a] rounded-lg border border-[#2a2e38]">
                  {group.tools.map((tool) => {
                    const Icon = tool.icon;
                    const isActive = activeTool === tool.id;
                    
                    return (
                      <Tooltip key={tool.id}>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => onToolSelect(tool.id)}
                            disabled={disabled}
                            className={`w-10 h-10 relative transition-all rounded-md ${
                              isActive
                                ? 'bg-gradient-to-b from-[#0077ee] to-[#0055cc] text-white shadow-lg shadow-blue-500/20'
                                : 'text-slate-400 hover:text-white hover:bg-[#2a2e38]'
                            } disabled:opacity-30`}
                          >
                            <Icon className="w-4.5 h-4.5" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="bg-[#1a1d24] border-[#3a3e48]">
                          <p className="text-xs font-medium">{tool.label}</p>
                          <p className="text-[10px] text-slate-500">{tool.shortcut}</p>
                        </TooltipContent>
                      </Tooltip>
                    );
                  })}
                </div>
                <span className="text-[9px] text-slate-600 mt-1 font-medium tracking-wide">{group.name}</span>
              </div>
              {groupIndex < toolGroups.length - 1 && (
                <div className="w-px h-10 bg-[#2a2e38] mx-2" />
              )}
            </div>
          ))}

          <div className="w-px h-10 bg-[#2a2e38]" />

          {/* Delete */}
          <div className="flex flex-col items-center">
            <div className="px-2 py-1 bg-[#12141a] rounded-lg border border-[#2a2e38]">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => onToolSelect('delete')}
                    disabled={disabled}
                    className="w-10 h-10 text-red-400 hover:text-red-300 hover:bg-red-500/10 disabled:opacity-30 rounded-md"
                  >
                    <Trash2 className="w-4.5 h-4.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="top" className="bg-[#1a1d24] border-[#3a3e48]">
                  <p className="text-xs">Delete <span className="text-slate-500">Del</span></p>
                </TooltipContent>
              </Tooltip>
            </div>
            <span className="text-[9px] text-slate-600 mt-1 font-medium tracking-wide">Delete</span>
          </div>

          <div className="w-px h-10 bg-[#2a2e38]" />

          {/* Status Info */}
          <div className="flex items-center gap-3 px-3 py-1.5 bg-[#12141a] rounded-lg border border-[#2a2e38]">
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-slate-500">Zoom</span>
              <span className="text-[12px] font-mono font-semibold text-[#00aaff]">{Math.round(zoom * 100)}%</span>
            </div>
            <div className="w-px h-5 bg-[#2a2e38]" />
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-slate-500">Page</span>
              <span className="text-[12px] font-mono font-semibold text-white">{currentPage}/{numPages}</span>
            </div>
          </div>
        </div>
      </footer>
    </TooltipProvider>
  );
};

export default AnnotationToolbar;
