"use client";

import { Contrast, Maximize2, MoveDiagonal, RotateCcw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button, IconButton } from "@/components/ui/button";
import { Spinner } from "@/components/ui/feedback";
import { cn } from "@/lib/format";
import type { Finding, ImagingStudy } from "@/lib/types";

/**
 * A DICOM film, displayed the way a radiologist expects: window and level by dragging, zoom and pan,
 * invert, and the model's attention as an optional overlay.
 *
 * The server sends the stored pixel values with an identity window (these films are 8-bit, so nothing is
 * lost); window and level are then applied here through a 256-entry lookup table, which is the same
 * transform the DICOM standard defines and is instant while dragging. The film starts at the window the
 * file itself carries, so the first view is the one the sending department chose.
 */
const RAMP = [
  [0, 0, 0, 0],
  [250, 204, 21, 90],
  [249, 115, 22, 150],
  [220, 38, 38, 205],
] as const;

function heat(value: number): [number, number, number, number] {
  const scaled = Math.max(0, Math.min(1, value)) * (RAMP.length - 1);
  const low = Math.floor(scaled), high = Math.min(RAMP.length - 1, low + 1), t = scaled - low;
  return [0, 1, 2, 3].map((c) => Math.round(RAMP[low][c] + (RAMP[high][c] - RAMP[low][c]) * t)) as
    [number, number, number, number];
}

export function FilmViewer({ study, finding, className }: {
  study: ImagingStudy; finding: Finding | null; className?: string;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const sourceRef = useRef<ImageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [center, setCenter] = useState(study.window_center);
  const [width, setWidth] = useState(study.window_width);
  const [invert, setInvert] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [overlay, setOverlay] = useState(true);
  const [size, setSize] = useState({ w: 0, h: 0 });

  // --- load the film once ------------------------------------------------------------------------
  useEffect(() => {
    let alive = true;
    const image = new Image();
    // The identity window: the browser receives the stored values, not a rendering decision.
    image.src = `/api/imaging/studies/${study.id}/image.png?center=127.5&width=256&max_side=1024`;
    image.onload = () => {
      if (!alive) return;
      const scratch = document.createElement("canvas");
      scratch.width = image.naturalWidth;
      scratch.height = image.naturalHeight;
      const ctx = scratch.getContext("2d", { willReadFrequently: true });
      if (!ctx) return setFailed(true);
      ctx.drawImage(image, 0, 0);
      sourceRef.current = ctx.getImageData(0, 0, scratch.width, scratch.height);
      setSize({ w: scratch.width, h: scratch.height });
      setLoading(false);
    };
    image.onerror = () => alive && (setFailed(true), setLoading(false));
    return () => { alive = false; };
  }, [study.id]);

  // --- window / level ----------------------------------------------------------------------------
  const draw = useCallback(() => {
    const source = sourceRef.current, canvas = canvasRef.current;
    if (!source || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const span = Math.max(width, 2);
    const low = center - 0.5 - (span - 1) / 2;
    const lut = new Uint8ClampedArray(256);
    for (let value = 0; value < 256; value++) {
      const scaled = Math.max(0, Math.min(1, (value - low) / (span - 1)));
      lut[value] = Math.round((invert ? 1 - scaled : scaled) * 255);
    }
    const out = ctx.createImageData(source.width, source.height);
    for (let i = 0; i < source.data.length; i += 4) {
      const shown = lut[source.data[i]];
      out.data[i] = out.data[i + 1] = out.data[i + 2] = shown;
      out.data[i + 3] = 255;
    }
    canvas.width = source.width;
    canvas.height = source.height;
    ctx.putImageData(out, 0, 0);
  }, [center, width, invert]);

  useEffect(() => { draw(); }, [draw, loading]);

  // --- the model's attention ---------------------------------------------------------------------
  useEffect(() => {
    const canvas = overlayRef.current;
    if (!canvas || !size.w) return;
    canvas.width = size.w;
    canvas.height = size.h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const map = finding?.attention;
    if (!overlay || !map?.length) return;
    // The map covers the whole film (the model sees the film squashed to a square), so it scales 1:1.
    const grid = document.createElement("canvas");
    grid.width = map[0].length;
    grid.height = map.length;
    const gctx = grid.getContext("2d");
    if (!gctx) return;
    const cells = gctx.createImageData(grid.width, grid.height);
    map.forEach((row, y) => row.forEach((value, x) => {
      const [r, g, b, a] = heat(value < 0.55 ? 0 : (value - 0.55) / 0.45);
      const at = (y * grid.width + x) * 4;
      cells.data[at] = r; cells.data[at + 1] = g; cells.data[at + 2] = b; cells.data[at + 3] = a;
    }));
    gctx.putImageData(cells, 0, 0);
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(grid, 0, 0, canvas.width, canvas.height);
  }, [finding, overlay, size]);

  // --- pointer: drag adjusts the window, shift-drag pans ------------------------------------------
  const drag = useRef<{ x: number; y: number; center: number; width: number; pan: { x: number; y: number };
    panning: boolean } | null>(null);

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (loading) return;
    (event.target as Element).setPointerCapture?.(event.pointerId);
    drag.current = { x: event.clientX, y: event.clientY, center, width, pan,
      panning: event.shiftKey || event.button === 1 };
  };
  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const from = drag.current;
    if (!from) return;
    const dx = event.clientX - from.x, dy = event.clientY - from.y;
    if (from.panning) {
      setPan({ x: from.pan.x + dx, y: from.pan.y + dy });
    } else {
      setWidth(Math.max(2, Math.round(from.width + dx)));   // right: wider window, less contrast
      setCenter(Math.round(from.center + dy));              // down: higher level, darker (as PACS viewers do)
    }
  };
  const onPointerUp = () => { drag.current = null; };

  const onWheel = (event: React.WheelEvent<HTMLDivElement>) => {
    if (loading) return;
    setZoom((z) => Math.max(1, Math.min(8, z * (event.deltaY < 0 ? 1.15 : 1 / 1.15))));
  };

  const reset = () => {
    setCenter(study.window_center);
    setWidth(study.window_width);
    setInvert(false);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div className={cn("overflow-hidden rounded-xl border border-line bg-panel shadow-e1", className)}>
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
        <span className="mr-auto flex items-center gap-1.5 text-[11px] text-muted">
          <MoveDiagonal className="h-3.5 w-3.5" aria-hidden />
          Drag to window · shift-drag to pan · scroll to zoom
        </span>
        {finding && (
          <Button size="sm" variant={overlay ? "primary" : "secondary"} onClick={() => setOverlay((v) => !v)}>
            <Sparkles className="h-3.5 w-3.5" aria-hidden /> {overlay ? "Hide" : "Show"} attention
          </Button>
        )}
        <Button size="sm" variant={invert ? "primary" : "secondary"} onClick={() => setInvert((v) => !v)}>
          <Contrast className="h-3.5 w-3.5" aria-hidden /> Invert
        </Button>
        <IconButton label="Fit to window" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>
          <Maximize2 className="h-4 w-4" />
        </IconButton>
        <IconButton label="Reset the view" onClick={reset}><RotateCcw className="h-4 w-4" /></IconButton>
      </div>

      <div className="relative select-none bg-black" style={{ aspectRatio: `${study.columns} / ${study.rows}` }}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp} onWheel={onWheel}
        role="img" aria-label={`${study.description ?? study.modality} for ${study.accession}`}>
        {loading && (
          <div className="absolute inset-0 grid place-items-center text-white/70"><Spinner label="Loading the film" /></div>
        )}
        {failed && (
          <p className="absolute inset-0 grid place-items-center px-6 text-center text-sm text-white/70">
            This film could not be loaded.
          </p>
        )}
        <div className="absolute inset-0 origin-center touch-none"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, cursor: zoom > 1 ? "grab" : "crosshair" }}>
          <canvas ref={canvasRef} className="absolute inset-0 h-full w-full object-contain" />
          <canvas ref={overlayRef} className="pointer-events-none absolute inset-0 h-full w-full object-contain"
            style={{ opacity: overlay ? 0.75 : 0 }} />
        </div>
        <div className="pointer-events-none absolute bottom-2 left-3 font-mono text-[10px] text-white/60">
          {study.view_position ?? study.modality} · {study.columns}×{study.rows}
        </div>
        <div className="pointer-events-none absolute bottom-2 right-3 font-mono text-[10px] text-white/60">
          W {Math.round(width)} · L {Math.round(center)}{zoom > 1 ? ` · ${zoom.toFixed(1)}×` : ""}
        </div>
      </div>
    </div>
  );
}
