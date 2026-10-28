import { useEffect, useRef } from "react";
export default function Background() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => { const cv = ref.current!, ctx = cv.getContext("2d")!; if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let w = 0, h = 0, raf = 0; const N = 38; const pts = Array.from({ length: N }, () => ({ x: Math.random(), y: Math.random(), vx: (Math.random() - .5) * .00012, vy: (Math.random() - .5) * .00012 }));
    const size = () => { w = cv.width = innerWidth; h = cv.height = innerHeight; }; size(); addEventListener("resize", size);
    const loop = () => { ctx.clearRect(0, 0, w, h); pts.forEach((p) => { p.x = (p.x + p.vx + 1) % 1; p.y = (p.y + p.vy + 1) % 1; });
      for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) { const dx = (pts[i].x - pts[j].x) * w, dy = (pts[i].y - pts[j].y) * h, d = Math.hypot(dx, dy); if (d < 170) { ctx.strokeStyle = `rgba(37,99,235,${.09 * (1 - d / 170)})`; ctx.beginPath(); ctx.moveTo(pts[i].x * w, pts[i].y * h); ctx.lineTo(pts[j].x * w, pts[j].y * h); ctx.stroke(); } }
      ctx.fillStyle = "rgba(37,99,235,.22)"; pts.forEach((p) => { ctx.beginPath(); ctx.arc(p.x * w, p.y * h, 2, 0, 7); ctx.fill(); }); raf = requestAnimationFrame(loop); };
    loop(); return () => { cancelAnimationFrame(raf); removeEventListener("resize", size); }; }, []);
  return <><div className="pointer-events-none fixed inset-0 -z-10 bg-gradient-to-br from-sky-50 via-white to-blue-100/60" /><canvas ref={ref} className="pointer-events-none fixed inset-0 -z-10" aria-hidden /></>;
}
