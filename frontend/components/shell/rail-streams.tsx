"use client";

import { useEffect, useRef } from "react";

/**
 * Ambient background for the sidebar, from the Stitch design: thin emerald lines drifting slowly down,
 * breathing in brightness, with a slight parallax toward the pointer. The Stitch export drew this with
 * Three.js; the same perspective projection is done here on a 2D canvas so every signed-in screen does
 * not load a 3D library for a decorative layer. Under reduced motion it draws a single still frame.
 */

const COUNT = 38;
const SHADES = ["16,185,129", "34,197,94", "52,211,153", "5,150,105", "110,231,183"];
const CAMERA_Z = 10;
const HALF_FOV = Math.tan(((55 / 2) * Math.PI) / 180);

interface Stream { x: number; y: number; z: number; length: number; speed: number; opacity: number; phase: number; pulse: number; shade: string }

function makeStream(): Stream {
  return {
    x: (Math.random() - 0.5) * 6.2 + 0.2,
    y: (Math.random() - 0.5) * 22,
    z: (Math.random() - 0.5) * 4,
    length: 2.5 + Math.random() * 4.5,
    speed: 0.35 + Math.random() * 0.75,
    opacity: 0.15 + Math.random() * 0.45,
    phase: Math.random() * Math.PI * 2,
    pulse: 0.8 + Math.random() * 1.2,
    shade: SHADES[Math.floor(Math.random() * SHADES.length)],
  };
}

export function RailStreams() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const streams = Array.from({ length: COUNT }, makeStream);
    const still = window.matchMedia("(prefers-reduced-motion: reduce)");
    let width = 0, height = 0, dpr = 1;
    let target = { x: 0, y: 0 };
    const tilt = { x: 0, y: 0 };
    let frame = 0;
    let last = performance.now();
    const start = last;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    // Perspective camera at z = 10 looking down -z, with the group rotated by the pointer tilt.
    const project = (x: number, y: number, z: number) => {
      const cy = Math.cos(tilt.y), sy = Math.sin(tilt.y), cx = Math.cos(tilt.x), sx = Math.sin(tilt.x);
      const x1 = x * cy + z * sy;
      const z1 = -x * sy + z * cy;
      const y2 = y * cx - z1 * sx;
      const z2 = y * sx + z1 * cx;
      const depth = CAMERA_Z - z2;
      const aspect = width / height || 1;
      return {
        sx: (x1 / (depth * HALF_FOV * aspect) + 1) * 0.5 * width,
        sy: (1 - y2 / (depth * HALF_FOV)) * 0.5 * height,
      };
    };

    const draw = (now: number) => {
      const elapsed = (now - start) / 1000;
      ctx.clearRect(0, 0, width, height);
      ctx.lineWidth = 1 / dpr;
      for (const s of streams) {
        const a = project(s.x, s.y - s.length / 2, s.z);
        const b = project(s.x, s.y + s.length / 2, s.z);
        const alpha = s.opacity * (0.7 + 0.3 * Math.sin(elapsed * s.pulse + s.phase));
        ctx.strokeStyle = `rgba(${s.shade},${alpha.toFixed(3)})`;
        ctx.beginPath();
        ctx.moveTo(a.sx, a.sy);
        ctx.lineTo(b.sx, b.sy);
        ctx.stroke();
      }
    };

    const tick = (now: number) => {
      // Time-based so the drift is the same speed on 60 Hz and 120 Hz screens.
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      for (const s of streams) {
        s.y -= s.speed * 1.08 * dt;
        if (s.y < -12) {
          s.y = 12;
          s.x = (Math.random() - 0.5) * 6.2 + 0.2;
        }
      }
      const ease = 1 - Math.pow(0.97, dt * 60);
      tilt.y += (target.x * 0.25 - tilt.y) * ease;
      tilt.x += (target.y * 0.15 - tilt.x) * ease;
      draw(now);
      frame = requestAnimationFrame(tick);
    };

    const onPointer = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      target = {
        x: ((e.clientX - rect.left) / (rect.width || 256) - 0.5) * 0.4,
        y: ((e.clientY - rect.top) / (rect.height || 900) - 0.5) * 0.4,
      };
    };

    const run = () => {
      cancelAnimationFrame(frame);
      if (still.matches) {
        draw(start);
        return;
      }
      last = performance.now();
      frame = requestAnimationFrame(tick);
    };

    resize();
    run();
    const observer = new ResizeObserver(() => { resize(); if (still.matches) draw(start); });
    observer.observe(canvas);
    window.addEventListener("pointermove", onPointer, { passive: true });
    still.addEventListener("change", run);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("pointermove", onPointer);
      still.removeEventListener("change", run);
    };
  }, []);

  return <canvas ref={canvasRef} aria-hidden className="pointer-events-none absolute inset-0 h-full w-full" />;
}
