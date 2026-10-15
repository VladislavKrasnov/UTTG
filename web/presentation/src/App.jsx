import { useCallback, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import { SLIDES } from "./slides.jsx";

const STAGE_WIDTH = 1920;
const STAGE_HEIGHT = 1080;
const PROJECTION_QUERY = "(min-width: 900px) and (min-aspect-ratio: 5/4)";

function subscribeToProjection(callback) {
  const query = window.matchMedia(PROJECTION_QUERY);
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
}

const isProjection = () => window.matchMedia(PROJECTION_QUERY).matches;

function SlideBody({ index }) {
  const Slide = SLIDES[index].Component;
  return (
    <>
      <header className="slide-header">
        <span className="slide-brand">ЕШКТ</span>
        <span className="slide-number num">{String(index + 1).padStart(2, "0")}</span>
      </header>
      <Slide />
    </>
  );
}

function Reader() {
  return (
    <main className="reader">
      {SLIDES.map((slide, index) => (
        <section className="slide" id={String(index + 1)} key={slide.title} aria-label={slide.title}>
          <SlideBody index={index} />
        </section>
      ))}
    </main>
  );
}

function initialIndex() {
  const fromHash = Number.parseInt(window.location.hash.replace("#", ""), 10);
  return Number.isInteger(fromHash) && fromHash >= 1 && fromHash <= SLIDES.length ? fromHash - 1 : 0;
}

function useStageScale(ref) {
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const element = ref.current;
    const observer = new ResizeObserver(() => {
      setScale(Math.min(element.clientWidth / STAGE_WIDTH, element.clientHeight / STAGE_HEIGHT));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return scale;
}

function toggleFullscreen() {
  if (document.fullscreenElement) document.exitFullscreen?.();
  else document.documentElement.requestFullscreen?.().catch(() => undefined);
}

export default function App() {
  const projection = useSyncExternalStore(subscribeToProjection, isProjection);
  return projection ? <Projection /> : <Reader />;
}

function Projection() {
  const viewport = useRef(null);
  const scale = useStageScale(viewport);
  const [index, setIndex] = useState(initialIndex);

  const go = useCallback((target) => setIndex(Math.max(0, Math.min(SLIDES.length - 1, target))), []);

  useEffect(() => {
    window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}#${index + 1}`);
  }, [index]);

  useEffect(() => {
    const onKey = (event) => {
      const key = event.key.toLowerCase();
      if (["arrowright", "pagedown", " ", "enter"].includes(key)) {
        event.preventDefault();
        go(index + 1);
      } else if (["arrowleft", "pageup", "backspace"].includes(key)) go(index - 1);
      else if (key === "home") go(0);
      else if (key === "end") go(SLIDES.length - 1);
      else if (key === "f" || key === "а") toggleFullscreen();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, index]);

  return (
    <div className="app">
      <div className="viewport" ref={viewport}>
        <div
          className="stage"
          style={{ width: STAGE_WIDTH, height: STAGE_HEIGHT, transform: `translate(-50%, -50%) scale(${scale})` }}
        >
          <div className="slide" key={index}>
            <SlideBody index={index} />
          </div>
          <div className="progress" style={{ transform: `scaleX(${(index + 1) / SLIDES.length})` }} />
        </div>
        <button type="button" className="nav prev" onClick={() => go(index - 1)} aria-label="Предыдущий слайд" disabled={index === 0}>
          ‹
        </button>
        <button type="button" className="nav next" onClick={() => go(index + 1)} aria-label="Следующий слайд" disabled={index === SLIDES.length - 1}>
          ›
        </button>
      </div>
    </div>
  );
}
