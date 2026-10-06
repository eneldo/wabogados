"use client";

import { useState } from "react";

import { Reveal } from "./reveal";
import { SiteDialog } from "./site-dialog";

/**
 * Legal news.
 *
 * These are **example contents, not published articles**. The copy says so in
 * the card, in the dialog and in the note beneath the grid, because a heading
 * that reads like legal advice on a firm's own site is advice the firm has not
 * given.
 */

type Article = {
  kicker: string;
  title: string;
  summary: string;
  body: string;
};

const ARTICLES: Article[] = [
  {
    kicker: "Empresa",
    title: "Prevención jurídica: decisiones mejor informadas.",
    summary:
      "Cómo organizar las consultas y documentos antes de tomar una decisión empresarial.",
    body: "Un espacio de ejemplo para futuros artículos de la firma. Una consulta puede prepararse reuniendo antecedentes, contratos, fechas relevantes y preguntas concretas. El equipo jurídico podrá valorar esos documentos y proponer los pasos siguientes.",
  },
  {
    kicker: "Contratos",
    title: "Antes de firmar, tenga una ruta clara.",
    summary:
      "Una lista inicial de asuntos que conviene revisar con su asesor jurídico.",
    body: "Contenido editorial de ejemplo. Prepare las dudas sobre el objeto del contrato, las obligaciones, los plazos y los documentos anexos para revisarlas con su asesor. El contenido definitivo será aprobado por la firma.",
  },
  {
    kicker: "Portal digital",
    title: "Su expediente, organizado y a su alcance.",
    summary:
      "Una nueva forma de consultar novedades y comunicarse con su equipo.",
    body: "El portal propuesto reunirá expedientes, actuaciones, documentos, evidencias, agenda y mensajería. Cada usuario consultará la información habilitada según su rol y su relación con el expediente.",
  },
];

export function NewsSection() {
  const [open, setOpen] = useState<Article | null>(null);

  return (
    <section id="actualidad" className="site-section">
      <div className="wrap">
        <div className="grid gap-8 lg:grid-cols-[1.15fr_1fr] lg:items-end">
          <div>
            <Reveal>
              <p className="site-eyebrow">Actualidad jurídica</p>
            </Reveal>
            <Reveal delay={70}>
              <h2 className="site-display site-section-title mt-5">
                Información que orienta.
              </h2>
            </Reveal>
          </div>
          <Reveal delay={140}>
            <p className="site-body">
              Un espacio editorial para compartir análisis y contenidos de interés.
            </p>
          </Reveal>
        </div>

        <div className="mt-14 grid gap-x-8 gap-y-12 sm:grid-cols-3">
          {ARTICLES.map((article, index) => (
            <Reveal key={article.title} delay={index * 90} as="article" className="h-full">
              <div className="flex h-full flex-col">
                <p className="site-eyebrow">{article.kicker}</p>
                <h3 className="site-display mt-5 text-xl leading-snug sm:text-[1.4rem]">
                  {article.title}
                </h3>
                <p className="site-body-sm mt-3.5 flex-1">{article.summary}</p>
                <button
                  type="button"
                  onClick={() => setOpen(article)}
                  className="service-link mt-6 self-start border-0 bg-transparent p-0"
                >
                  Leer contenido de ejemplo <span aria-hidden="true">↗</span>
                </button>
              </div>
            </Reveal>
          ))}
        </div>

        <Reveal delay={120}>
          <p className="site-note mt-14">
            <span className="pending-tag mr-3">Pendiente de aprobación</span>
            Los textos anteriores son <strong>contenidos de muestra</strong>, no
            publicaciones de la firma. No constituyen asesoramiento jurídico y no
            se publicarán hasta su revisión y aprobación.
          </p>
        </Reveal>
      </div>

      <SiteDialog
        open={open !== null}
        onClose={() => setOpen(null)}
        label="Contenido de muestra"
      >
        {open ? (
          <>
            <p className="site-eyebrow">Contenido de muestra</p>
            <h2 className="site-display mt-5 text-3xl">{open.title}</h2>
            <p className="site-body mt-5">{open.body}</p>
            <p className="site-note mt-7">
              Texto de ejemplo pendiente de aprobación por la firma.
            </p>
          </>
        ) : null}
      </SiteDialog>
    </section>
  );
}
