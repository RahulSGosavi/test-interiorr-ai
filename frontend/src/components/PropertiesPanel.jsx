import { Button } from '@/components/ui/button';
import { Slider } from '@/components/ui/slider';
import {
  Layers,
  Plus,
  Eye,
  EyeOff,
  ZoomIn,
  ZoomOut,
  Maximize,
  ChevronLeft,
  ChevronRight,
  Download,
  Save,
  Copy,
  RotateCw,
  Expand,
  RotateCcw,
  Settings2
} from 'lucide-react';

const PropertiesPanel = ({
  // Stroke settings
  strokeWidth,
  setStrokeWidth,
  strokeColor,
  setStrokeColor,
  strokeStyle,
  setStrokeStyle,
  // Measurement
  measurementUnit,
  setMeasurementUnit,
  unitsPerPixel,
  setUnitsPerPixel,
  // Layers
  layers,
  activeLayerId,
  onAddLayer,
  onSelectLayer,
  onToggleLayerVisibility,
  // Zoom & Navigation
  zoom,
  onZoomIn,
  onZoomOut,
  onFitToScreen,
  // Page
  currentPage,
  numPages,
  onPrevPage,
  onNextPage,
  rotation,
  onRotatePage,
  // Actions
  onCopy,
  onRotate,
  onScale,
  onSave,
  onDownload,
  // State
  isSaved,
  isAutoSaving,
  disabled = false,
  totalElements = 0
}) => {
  return (
    <aside className="w-64 bg-[#1a1d24] border-l border-[#2a2e38] flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-3 py-2 border-b border-[#2a2e38] flex items-center gap-2">
        <Settings2 className="w-4 h-4 text-[#00aaff]" />
        <span className="text-xs font-semibold text-white uppercase tracking-wider">Properties</span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Stroke Section */}
        <section className="p-3 border-b border-[#2a2e38]">
          <h3 className="text-[10px] uppercase tracking-wider text-slate-500 mb-3 font-semibold">Stroke</h3>
          
          {/* Width - Advanced Control */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-slate-400">Width</span>
              <div className="flex items-center gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setStrokeWidth(Math.max(1, strokeWidth - 1))}
                  disabled={disabled || strokeWidth <= 1}
                  className="w-5 h-5 text-slate-400 hover:text-white hover:bg-[#2a2e38] disabled:opacity-30"
                >
                  <span className="text-sm font-bold">−</span>
                </Button>
                <input
                  type="number"
                  value={strokeWidth}
                  onChange={(e) => {
                    const val = parseInt(e.target.value) || 1;
                    setStrokeWidth(Math.min(50, Math.max(1, val)));
                  }}
                  disabled={disabled}
                  className="w-12 h-6 bg-[#2a2e38] border border-[#3a3e48] rounded text-center text-[11px] text-[#00aaff] font-mono focus:outline-none focus:border-[#00aaff] disabled:opacity-50"
                />
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setStrokeWidth(Math.min(50, strokeWidth + 1))}
                  disabled={disabled || strokeWidth >= 50}
                  className="w-5 h-5 text-slate-400 hover:text-white hover:bg-[#2a2e38] disabled:opacity-30"
                >
                  <span className="text-sm font-bold">+</span>
                </Button>
              </div>
            </div>
            <Slider
              value={[strokeWidth]}
              onValueChange={([value]) => setStrokeWidth(value)}
              min={1}
              max={50}
              step={1}
              disabled={disabled}
              className="w-full mb-2"
            />
            {/* Preset sizes */}
            <div className="flex gap-1 flex-wrap">
              {[1, 2, 3, 5, 8, 12, 18, 24].map((size) => (
                <button
                  key={size}
                  onClick={() => setStrokeWidth(size)}
                  disabled={disabled}
                  className={`h-7 min-w-[32px] px-2 rounded text-[10px] font-medium transition-all ${
                    strokeWidth === size
                      ? 'bg-[#0066cc] text-white'
                      : 'bg-[#2a2e38] text-slate-400 hover:text-white hover:bg-[#3a3e48]'
                  } disabled:opacity-50`}
                >
                  {size}
                </button>
              ))}
            </div>
            {/* Visual preview */}
            <div className="mt-3 p-2 bg-[#12141a] rounded border border-[#2a2e38]">
              <div className="flex items-center justify-center h-8">
                <div 
                  className="rounded-full transition-all"
                  style={{ 
                    width: `${Math.min(strokeWidth * 3, 100)}px`,
                    height: `${strokeWidth}px`,
                    backgroundColor: strokeColor,
                  }}
                />
              </div>
            </div>
          </div>

          {/* Color */}
          <div className="mb-4">
            <span className="text-[10px] text-slate-400 block mb-2">Color</span>
            <div className="flex items-center gap-2 mb-2">
              <div 
                className="w-8 h-8 rounded border border-[#3a3e48]"
                style={{ backgroundColor: strokeColor }}
              />
              <input
                type="text"
                value={strokeColor}
                onChange={(e) => setStrokeColor(e.target.value)}
                disabled={disabled}
                className="flex-1 h-7 bg-[#2a2e38] border border-[#3a3e48] rounded text-[11px] text-white px-2 font-mono uppercase focus:outline-none focus:border-[#00aaff] disabled:opacity-50"
              />
            </div>
            {/* Color Swatches */}
            <div className="grid grid-cols-8 gap-1">
              {[
                '#FF0000', '#FF6B00', '#FFD700', '#00FF00', 
                '#00FFFF', '#0066FF', '#8B00FF', '#FF00FF',
                '#FFFFFF', '#CCCCCC', '#888888', '#444444',
                '#000000', '#8B4513', '#FF69B4', '#3B82F6'
              ].map((color) => (
                <button
                  key={color}
                  onClick={() => setStrokeColor(color)}
                  disabled={disabled}
                  className={`w-6 h-6 rounded border transition-all hover:scale-110 disabled:opacity-50 ${
                    strokeColor.toUpperCase() === color ? 'border-white ring-1 ring-white' : 'border-[#3a3e48]'
                  }`}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>

          {/* Style */}
          <div>
            <span className="text-[10px] text-slate-400 block mb-2">Style</span>
            <div className="flex gap-1">
              {['solid', 'dashed', 'dotted'].map((style) => (
                <Button
                  key={style}
                  size="sm"
                  variant={strokeStyle === style ? 'default' : 'ghost'}
                  onClick={() => setStrokeStyle(style)}
                  disabled={disabled}
                  className={`flex-1 h-7 text-[10px] capitalize ${
                    strokeStyle === style
                      ? 'bg-[#0066cc] text-white'
                      : 'text-slate-400 hover:text-white hover:bg-[#2a2e38]'
                  }`}
                >
                  {style}
                </Button>
              ))}
            </div>
          </div>
        </section>

        {/* Measurement Section */}
        <section className="p-3 border-b border-[#2a2e38]">
          <h3 className="text-[10px] uppercase tracking-wider text-slate-500 mb-3 font-semibold">Measurement</h3>
          
          {/* Unit Selection */}
          <div className="mb-3">
            <span className="text-[10px] text-slate-400 block mb-2">Unit</span>
            <div className="flex gap-1">
              {[
                { value: 'mm', label: 'mm' },
                { value: 'cm', label: 'cm' },
                { value: 'm', label: 'm' },
                { value: 'in', label: 'in' },
                { value: 'ft', label: 'ft' },
              ].map((unit) => (
                <button
                  key={unit.value}
                  onClick={() => setMeasurementUnit(unit.value)}
                  disabled={disabled}
                  className={`flex-1 h-7 rounded text-[10px] font-medium transition-all ${
                    measurementUnit === unit.value
                      ? 'bg-[#0066cc] text-white'
                      : 'bg-[#2a2e38] text-slate-400 hover:text-white hover:bg-[#3a3e48]'
                  } disabled:opacity-50`}
                >
                  {unit.label}
                </button>
              ))}
            </div>
          </div>

          {/* Scale Control */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-slate-400">Scale (units/px)</span>
              <div className="flex items-center gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setUnitsPerPixel(Math.max(0.001, parseFloat((unitsPerPixel - 0.01).toFixed(3))))}
                  disabled={disabled}
                  className="w-5 h-5 text-slate-400 hover:text-white hover:bg-[#2a2e38] disabled:opacity-30"
                >
                  <span className="text-sm font-bold">−</span>
                </Button>
                <input
                  type="number"
                  min="0.001"
                  step="0.01"
                  value={unitsPerPixel}
                  onChange={(e) => setUnitsPerPixel(Math.max(parseFloat(e.target.value) || 0.001, 0.001))}
                  disabled={disabled}
                  className="w-16 h-6 bg-[#2a2e38] border border-[#3a3e48] rounded text-center text-[11px] text-[#00aaff] font-mono focus:outline-none focus:border-[#00aaff] disabled:opacity-50"
                />
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => setUnitsPerPixel(parseFloat((unitsPerPixel + 0.01).toFixed(3)))}
                  disabled={disabled}
                  className="w-5 h-5 text-slate-400 hover:text-white hover:bg-[#2a2e38] disabled:opacity-30"
                >
                  <span className="text-sm font-bold">+</span>
                </Button>
              </div>
            </div>
            <Slider
              value={[unitsPerPixel * 100]}
              onValueChange={([value]) => setUnitsPerPixel(value / 100)}
              min={1}
              max={100}
              step={1}
              disabled={disabled}
              className="w-full"
            />
          </div>

          {/* Preset scales */}
          <div className="flex gap-1 flex-wrap">
            {[
              { value: 0.01, label: '1:100' },
              { value: 0.05, label: '1:20' },
              { value: 0.1, label: '1:10' },
              { value: 0.5, label: '1:2' },
              { value: 1, label: '1:1' },
            ].map((preset) => (
              <button
                key={preset.value}
                onClick={() => setUnitsPerPixel(preset.value)}
                disabled={disabled}
                className={`h-6 px-2 rounded text-[9px] font-medium transition-all ${
                  unitsPerPixel === preset.value
                    ? 'bg-[#0066cc] text-white'
                    : 'bg-[#2a2e38] text-slate-400 hover:text-white hover:bg-[#3a3e48]'
                } disabled:opacity-50`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </section>

        {/* Layers Section */}
        <section className="p-3 border-b border-[#2a2e38]">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold flex items-center gap-1.5">
              <Layers className="w-3 h-3" />
              Layers
            </h3>
            <Button
              size="icon"
              variant="ghost"
              onClick={onAddLayer}
              disabled={disabled}
              className="w-6 h-6 text-slate-400 hover:text-[#00aaff] hover:bg-[#2a2e38]"
            >
              <Plus className="w-3.5 h-3.5" />
            </Button>
          </div>
          
          <div className="space-y-1">
            {layers?.items?.map((layer) => (
              <div
                key={layer.id}
                className={`flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer transition-colors ${
                  layer.id === activeLayerId
                    ? 'bg-[#0066cc]/20 border border-[#0066cc]/50'
                    : 'hover:bg-[#2a2e38] border border-transparent'
                }`}
                onClick={() => onSelectLayer(layer.id)}
              >
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleLayerVisibility(layer.id);
                  }}
                  disabled={disabled}
                  className="w-5 h-5 p-0 text-slate-400 hover:text-white"
                >
                  {layer.visible ? (
                    <Eye className="w-3 h-3" />
                  ) : (
                    <EyeOff className="w-3 h-3 text-slate-600" />
                  )}
                </Button>
                <span className={`text-[11px] flex-1 ${
                  layer.id === activeLayerId ? 'text-white font-medium' : 'text-slate-300'
                }`}>
                  {layer.name}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Transform Actions */}
        <section className="p-3 border-b border-[#2a2e38]">
          <h3 className="text-[10px] uppercase tracking-wider text-slate-500 mb-3 font-semibold">Transform</h3>
          <div className="grid grid-cols-3 gap-1">
            <Button
              size="sm"
              variant="ghost"
              onClick={onCopy}
              disabled={disabled}
              className="h-8 text-slate-400 hover:text-white hover:bg-[#2a2e38] flex flex-col gap-0.5"
            >
              <Copy className="w-3.5 h-3.5" />
              <span className="text-[8px]">Copy</span>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={onRotate}
              disabled={disabled}
              className="h-8 text-slate-400 hover:text-white hover:bg-[#2a2e38] flex flex-col gap-0.5"
            >
              <RotateCw className="w-3.5 h-3.5" />
              <span className="text-[8px]">Rotate</span>
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={onScale}
              disabled={disabled}
              className="h-8 text-slate-400 hover:text-white hover:bg-[#2a2e38] flex flex-col gap-0.5"
            >
              <Expand className="w-3.5 h-3.5" />
              <span className="text-[8px]">Scale</span>
            </Button>
          </div>
        </section>

        {/* View Section */}
        <section className="p-3 border-b border-[#2a2e38]">
          <h3 className="text-[10px] uppercase tracking-wider text-slate-500 mb-3 font-semibold">View</h3>
          
          {/* Zoom - Advanced */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-slate-400">Zoom</span>
              <div className="flex items-center gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={onZoomOut}
                  disabled={disabled}
                  className="w-6 h-6 text-slate-400 hover:text-white hover:bg-[#2a2e38]"
                >
                  <ZoomOut className="w-3.5 h-3.5" />
                </Button>
                <span className="text-[12px] font-mono text-[#00aaff] w-14 text-center font-semibold">{Math.round(zoom * 100)}%</span>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={onZoomIn}
                  disabled={disabled}
                  className="w-6 h-6 text-slate-400 hover:text-white hover:bg-[#2a2e38]"
                >
                  <ZoomIn className="w-3.5 h-3.5" />
                </Button>
              </div>
            </div>
            {/* Zoom presets */}
            <div className="flex gap-1 flex-wrap mb-2">
              {[25, 50, 75, 100, 150, 200].map((percent) => (
                <button
                  key={percent}
                  onClick={() => onZoomIn && onZoomOut && (() => {
                    // This is a workaround - ideally we'd have a setZoom prop
                    const targetZoom = percent / 100;
                    const currentZoom = zoom;
                    if (targetZoom > currentZoom) {
                      for (let i = 0; i < Math.ceil((targetZoom - currentZoom) / 0.15); i++) onZoomIn();
                    } else {
                      for (let i = 0; i < Math.ceil((currentZoom - targetZoom) / 0.15); i++) onZoomOut();
                    }
                  })()}
                  disabled={disabled}
                  className={`flex-1 h-6 rounded text-[9px] font-medium transition-all ${
                    Math.round(zoom * 100) === percent
                      ? 'bg-[#0066cc] text-white'
                      : 'bg-[#2a2e38] text-slate-400 hover:text-white hover:bg-[#3a3e48]'
                  } disabled:opacity-50`}
                >
                  {percent}%
                </button>
              ))}
            </div>
            <Button
              variant="ghost"
              onClick={onFitToScreen}
              disabled={disabled}
              className="w-full h-7 text-[10px] bg-[#2a2e38] text-slate-300 hover:text-white hover:bg-[#3a3e48]"
            >
              <Maximize className="w-3 h-3 mr-1.5" />
              Fit to Screen
            </Button>
          </div>

          {/* Page Navigation */}
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] text-slate-400">Page</span>
            <div className="flex items-center gap-1">
              <Button
                size="icon"
                variant="ghost"
                onClick={onPrevPage}
                disabled={disabled || currentPage <= 1}
                className="w-6 h-6 text-slate-400 hover:text-white hover:bg-[#2a2e38] disabled:opacity-30"
              >
                <ChevronLeft className="w-3 h-3" />
              </Button>
              <span className="text-[11px] font-mono text-white w-12 text-center">{currentPage}/{numPages}</span>
              <Button
                size="icon"
                variant="ghost"
                onClick={onNextPage}
                disabled={disabled || currentPage >= numPages}
                className="w-6 h-6 text-slate-400 hover:text-white hover:bg-[#2a2e38] disabled:opacity-30"
              >
                <ChevronRight className="w-3 h-3" />
              </Button>
            </div>
          </div>

          {/* Rotation */}
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400">Rotation</span>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono text-white">{rotation}°</span>
              <Button
                size="icon"
                variant="ghost"
                onClick={onRotatePage}
                disabled={disabled}
                className="w-6 h-6 text-slate-400 hover:text-white hover:bg-[#2a2e38]"
              >
                <RotateCcw className="w-3 h-3" />
              </Button>
            </div>
          </div>
        </section>

        {/* Stats */}
        <section className="p-3">
          <h3 className="text-[10px] uppercase tracking-wider text-slate-500 mb-2 font-semibold">Statistics</h3>
          <div className="grid grid-cols-2 gap-2 text-[10px]">
            <div className="bg-[#2a2e38] rounded px-2 py-1.5">
              <span className="text-slate-500 block">Elements</span>
              <span className="text-white font-mono">{totalElements}</span>
            </div>
            <div className="bg-[#2a2e38] rounded px-2 py-1.5">
              <span className="text-slate-500 block">Layers</span>
              <span className="text-white font-mono">{layers?.items?.length || 0}</span>
            </div>
          </div>
        </section>
      </div>

      {/* Footer Actions */}
      <div className="p-3 border-t border-[#2a2e38] space-y-2">
        {/* Status */}
        <div className="flex items-center justify-center gap-2 text-[10px] mb-2">
          <span className={`flex items-center gap-1.5 px-2 py-1 rounded ${
            isSaved
              ? 'bg-emerald-500/10 text-emerald-400'
              : 'bg-amber-500/10 text-amber-400'
          }`}>
            <span className={`w-1.5 h-1.5 rounded-full ${isSaved ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'}`} />
            {isSaved ? 'Saved' : isAutoSaving ? 'Saving...' : 'Unsaved'}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Button
            onClick={onDownload}
            disabled={disabled}
            className="h-9 bg-[#2a2e38] hover:bg-[#3a3e48] text-white text-[11px] border border-[#3a3e48]"
          >
            <Download className="w-3.5 h-3.5 mr-1.5" />
            Export
          </Button>
          <Button
            onClick={onSave}
            disabled={disabled}
            className="h-9 bg-[#0066cc] hover:bg-[#0077ee] text-white text-[11px]"
          >
            <Save className="w-3.5 h-3.5 mr-1.5" />
            Save
          </Button>
        </div>
      </div>
    </aside>
  );
};

export default PropertiesPanel;

