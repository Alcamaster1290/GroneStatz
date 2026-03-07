"use client";

import { TouchEvent, useEffect, useMemo, useState } from "react";

type WelcomeSlideshowProps = {
  open: boolean;
  onComplete: () => void;
};

type Slide = {
  title: string;
  bullets: string[];
  icon: string;
};

const SLIDES: Slide[] = [
  {
    title: "Bienvenido al Fantasy Liga 1 Peru 2026",
    bullets: [
      "Unete a una nueva forma de vivir la Liga 1 totalmente gratis.",
      "Compite cada jornada con datos reales.",
      "Arma tu equipo con 100 M y empieza a jugar."
    ],
    icon: "L1"
  },
  {
    title: "Como se suman los puntos",
    bullets: [
      "Gol +4, asistencia +3.",
      "Minutos jugados: hasta +2 por partido.",
      "Tarjetas restan puntos."
    ],
    icon: "PTS"
  },
  {
    title: "Torneo general",
    bullets: [
      "Todos los usuarios compiten en una tabla unica.",
      "Suma puntos jornada a jornada.",
      "Sube posiciones y gana reconocimiento."
    ],
    icon: "TOP"
  },
  {
    title: "Torneos privados",
    bullets: [
      "Crea ligas cerradas con amigos o comunidades.",
      "Comparte un codigo privado para unirte.",
      "El admin puede gestionar miembros."
    ],
    icon: "GRP"
  },
  {
    title: "Mercado dinamico",
    bullets: [
      "El valor de los jugadores sube o baja segun su rendimiento.",
      "Aprovecha los cambios de precio cada ronda.",
      "Planifica tus transferencias: son ilimitadas y sin costo."
    ],
    icon: "MKT"
  }
];

export default function WelcomeSlideshow({ open, onComplete }: WelcomeSlideshowProps) {
  const [index, setIndex] = useState(0);
  const [touchStart, setTouchStart] = useState<number | null>(null);

  useEffect(() => {
    if (!open) {
      setIndex(0);
      setTouchStart(null);
    }
  }, [open]);

  const slide = SLIDES[index];
  const isLast = index === SLIDES.length - 1;

  const canPrev = index > 0;
  const canNext = index < SLIDES.length - 1;

  const handleNext = () => {
    if (canNext) {
      setIndex((prev) => Math.min(prev + 1, SLIDES.length - 1));
    }
  };

  const handlePrev = () => {
    if (canPrev) {
      setIndex((prev) => Math.max(prev - 1, 0));
    }
  };

  const handleSkip = () => {
    setIndex(SLIDES.length - 1);
  };

  const handleTouchStart = (event: TouchEvent<HTMLDivElement>) => {
    setTouchStart(event.touches[0]?.clientX ?? null);
  };

  const handleTouchEnd = (event: TouchEvent<HTMLDivElement>) => {
    if (touchStart == null) return;
    const endX = event.changedTouches[0]?.clientX ?? touchStart;
    const delta = endX - touchStart;
    if (Math.abs(delta) < 40) return;
    if (delta < 0) {
      handleNext();
    } else {
      handlePrev();
    }
    setTouchStart(null);
  };

  const dots = useMemo(
    () =>
      SLIDES.map((_, dotIndex) => (
        <span
          key={dotIndex}
          className={
            "h-2 w-2 rounded-full transition " +
            (dotIndex === index ? "bg-accent" : "bg-white/20")
          }
        />
      )),
    [index]
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 px-4 py-6">
      <div
        className="ui-panel w-full max-w-md space-y-4 rounded-3xl p-5"
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        <div className="flex items-center justify-between">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 text-sm font-bold">
            {slide.icon}
          </div>
          <div className="flex gap-2">{dots}</div>
        </div>

        <div className="space-y-3">
          <h2 className="text-xl font-semibold text-ink">{slide.title}</h2>
          <ul className="space-y-2 text-sm text-muted">
            {slide.bullets.map((bullet) => (
              <li key={bullet} className="flex items-start gap-2">
                <span className="mt-1 h-2 w-2 rounded-full bg-accent" />
                <span>{bullet}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex items-center justify-between gap-2">
          <button
            onClick={handlePrev}
            disabled={!canPrev}
            className="ui-btn ui-btn-secondary px-4 py-2 text-xs disabled:opacity-40"
          >
            Anterior
          </button>
          <button onClick={handleSkip} className="text-xs text-muted underline">
            Saltar
          </button>
          <button
            onClick={handleNext}
            disabled={!canNext}
            className="ui-btn ui-btn-primary px-4 py-2 text-xs disabled:opacity-40"
          >
            Siguiente
          </button>
        </div>

        {isLast ? (
          <button onClick={onComplete} className="ui-btn ui-btn-primary w-full px-4 py-2 text-sm">
            Nombrar mi equipo
          </button>
        ) : null}
      </div>
    </div>
  );
}
