"use client";

import {
  STAGE_LABEL,
  STAGE_NOTE,
  STAGE_ORDER,
  isTerminal,
  stageIndex,
  type Stage,
} from "./stages";

/**
 * The pipeline rail.
 *
 * A horizontal ruled track with one node per stage, in the order the backend
 * performs them. A completed node is a filled dot; the current one has a ring;
 * future ones are hollow. The label of the current stage is the only thing in
 * bold, so the eye lands on where the file is rather than on all six at once.
 */
export function StageRail({ stage }: { stage: Stage }) {
  const current = stageIndex(stage);
  const failed = stage === "rechazado";

  return (
    <div>
      <ol className="flex items-start" role="list" aria-label="Progreso del procesado">
        {STAGE_ORDER.map((item, index) => {
          /*
            A finished pipeline marks its last station as done, not as current.
            Leaving "Listo" drawn as the in-flight node — an empty ring with a
            pulse — told the user the work was still running after it had
            finished, which is the opposite of what the note underneath said.
          */
          const complete = stage === "listo" && index <= current;
          const done = !failed && (index < current || complete);
          const active = !failed && index === current && !complete;
          const last = index === STAGE_ORDER.length - 1;

          return (
            <li key={item} className="flex min-w-0 flex-1 flex-col items-center">
              <div className="flex w-full items-center">
                <span
                  aria-hidden="true"
                  className={`h-px flex-1 ${
                    index === 0 ? "bg-transparent" : done || active ? "bg-forest/50" : "bg-rule"
                  }`}
                />
                <span
                  className={`grid size-3.5 shrink-0 place-items-center rounded-full border-2 transition-all duration-300 ${
                    failed
                      ? "border-rule bg-surface"
                      : done
                        ? "border-forest bg-forest"
                        : active
                          ? "border-forest bg-surface live-dot"
                          : "border-rule-strong bg-surface"
                  }`}
                />
                <span
                  aria-hidden="true"
                  className={`h-px flex-1 ${
                    last
                      ? "bg-transparent"
                      : done || active
                        ? "bg-forest/50"
                        : "bg-rule"
                  }`}
                />
              </div>
              <span
                className={`mt-2 px-0.5 text-center text-[0.625rem] leading-tight font-semibold uppercase tracking-[0.08em] ${
                  active ? "text-forest" : done ? "text-ink-soft" : "text-ink-faint"
                }`}
              >
                {STAGE_LABEL[item]}
              </span>
            </li>
          );
        })}
      </ol>

      <p
        aria-live="polite"
        className={`mt-3 text-center text-xs ${
          failed ? "text-wax-deep" : "text-ink-muted"
        }`}
      >
        {isTerminal(stage) && stage === "listo"
          ? STAGE_NOTE.listo
          : failed
            ? "El despacho ha rechazado el archivo."
            : STAGE_NOTE[stage]}
      </p>
    </div>
  );
}
