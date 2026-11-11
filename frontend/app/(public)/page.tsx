import Image from "next/image";
import Link from "next/link";

import { ColumnsIllustration } from "@/components/public/columns-illustration";
import { apiFetchOr } from "@/lib/api";
import { landingFor } from "@/lib/landing";
import { requireSession } from "@/lib/session-guard";
import type { LegalAreaOption } from "@/lib/types";
import { ContactForm } from "@/components/public/contact-form";
import { NewsSection } from "@/components/public/news-section";
import { Parallax } from "@/components/public/parallax";
import { Reveal } from "@/components/public/reveal";
import { SiteFooter, SiteHeader } from "@/components/public/site-header";

/**
 * The public site.
 *
 * `WABOGADOS_web.html` is the composition reference. The supplied logo and
 * `wabogado-2.jpg` now define the corporate palette. What is improved is the
 * craft: a fluid type scale so the page is composed at every width rather than
 * tolerated at small ones, and motion that gives the page a pulse without
 * moving anything the reader needs to read.
 *
 * The identity of the firm comes from `WABOGADOS_recursos` and from
 * wabogados.co: real names, real roles, real photographs, the practice areas
 * the firm itself lists, and its published address, phone and opening hours.
 *
 * What is **not** on the page is what nobody has supplied:
 *
 * 1. "Portal privado" opens the real login, not a mock-up.
 * 2. No credential, no years of practice, no case record, no award and no
 *    client testimonial. The three testimonials on the firm's own site are
 *    theme demonstration copy about web development, not clients, so they were
 *    left out.
 * 3. No email address. The firm publishes it behind Cloudflare's email
 *    protection, so it is not in the page source and is not guessed.
 * 4. The consultation form uses the real API; legal copy still awaits the
 *    firm's approval, so the pending notices are retained.
 */

/*
  The firm's own practice areas, with the wording it uses for them. Seven, not
  the four the reference mock had: the reference is a layout reference, and
  dropping three areas the firm actually practises would be trimming the firm's
  offer to fit the design.
*/
const GLYPHS = ["⚖", "⌂", "▥", "▤", "◈", "◉", "❖", "§", "¶", "✦"];

const SERVICES = [
  {
    glyph: "⚖",
    title: "Derecho penal",
    body: "Asesoría a altos ejecutivos para tomar mejores decisiones en casos penales.",
  },
  {
    glyph: "⌂",
    title: "Ley familiar",
    body: "Derechos y deberes de los esposos y los hijos, filiación, sucesiones, divorcios, separaciones y alimentos.",
  },
  {
    glyph: "▥",
    title: "Derecho laboral",
    body: "El equilibrio en las relaciones contractuales de tipo laboral y profesional.",
  },
  {
    glyph: "▤",
    title: "Derecho constitucional",
    body: "Efectivizar el derecho constitucional para que cada persona pueda vivir con dignidad, por vía legal y jurisprudencial.",
  },
  {
    glyph: "◈",
    title: "Derecho civil",
    body: "Las relaciones contractuales de las personas, por voluntad de las partes o por hechos meramente naturales.",
  },
  {
    glyph: "◉",
    title: "Derecho comercial",
    body: "La rama del derecho privado que regula la realización de actos de comercio.",
  },
  {
    glyph: "❖",
    title: "Asesorías empresariales",
    body: "Asistencia legal a empresas en materia comercial, laboral, societaria y de marcas.",
  },
];

const PRINCIPLES = [
  { number: "01 / ESTRATEGIA", title: "Una ruta clara", body: "Objetivos y próximos pasos comprensibles desde el inicio." },
  { number: "02 / CERCANÍA", title: "Comunicación continua", body: "Información oportuna y atención a sus inquietudes." },
  { number: "03 / CONFIANZA", title: "Confidencialidad", body: "Acceso controlado a su información y documentación." },
  { number: "04 / TECNOLOGÍA", title: "Gestión organizada", body: "Expedientes, actuaciones y evidencias en un mismo lugar." },
];

const TRUST = [
  { title: "Una estrategia para cada caso", body: "Soluciones enfocadas en su necesidad." },
  { title: "Información a su alcance", body: "Seguimiento desde el portal de clientes." },
  { title: "Atención cercana", body: "Un equipo que escucha y acompaña." },
];

const PORTAL_CHECKS = [
  "Estado de expedientes",
  "Actuaciones recientes",
  "Documentos y evidencias",
  "Agenda y notificaciones",
  "Mensajería segura",
  "Seguimiento del proceso",
];

/*
  The firm itself: names, roles and photographs from wabogados.co, retrieved
  from `WABOGADOS_recursos`. William Ruiz Villegas is the firm's founder, and
  the order is his first.

  Roles are the ones the firm publishes. Nothing here says where anyone studied,
  how long they have practised or which cases they have won, because those are
  not published either.
*/
const TEAM = [
  {
    name: "William Ruiz Villegas",
    role: "Abogado fundador",
    image: "/equipo/william-ruiz-villegas.jpg",
    width: 480,
    height: 480,
  },
  {
    name: "Faiber Andrés López Ruiz",
    role: "Abogado junior",
    image: "/equipo/faiber-andres-lopez-ruiz.jpg",
    width: 480,
    height: 602,
  },
  {
    name: "Geraldine López Ruiz",
    role: "Asesora de negocios",
    image: "/equipo/geraldine-lopez-ruiz.jpg",
    width: 480,
    height: 784,
  },
];

/*
  Contact details as published by the firm. The email is the one item that could
  not be recovered: wabogados.co serves it behind Cloudflare's email
  protection, so the address is not in the page source. It stays pending rather
  than guessed.
*/
const CONTACT = {
  address: "Cra. 9 # 16-20, oficina 206, edificio Berna, Bogotá D.C.",
  phone: "+57 312 469 9617",
  phoneHref: "+573124699617",
  schedule: "Lunes a viernes, 8:00 a. m. a 7:00 p. m.",
};

/*
  Allied firms, with their marks as published on wabogados.co. A partner's logo
  on your site is a claim about the relationship, so these are the firm's own
  and not ours.
*/
const ALLIES = [
  { name: "Rojas & Ríos Abogados", image: "/aliados/rojas-y-rios-abogados.jpg" },
  { name: "Wolfgang Ramírez", image: "/aliados/wolfgang-ramirez.jpg" },
];

export default async function PublicHomePage({
  searchParams,
}: {
  searchParams?: Promise<{ analisis?: string }>;
}) {
  const params = (await searchParams) ?? {};
  const analysisPage = Math.max(1, Number(params.analisis ?? "1") || 1);

  const areas = await apiFetchOr<LegalAreaOption[]>(
    [],
    "/api/v1/public/legal-areas",
    { anonymous: true },
  );

  const health = await apiFetchOr<{ status?: string; service?: string }>(
    { status: "unknown" },
    "/api/v1/health/ready",
    { anonymous: true },
  );

  const publicLawyers = await apiFetchOr<
    Array<{ id: string; full_name: string; photo_url: string | null; specialties: string[]; legal_areas: string[] }>
  >([], "/api/v1/public/lawyers", { anonymous: true });

  const announcements = await apiFetchOr<
    Array<{ key: string; value: string; description: string | null; updated_at: string }>
  >([], "/api/v1/public/announcements", { anonymous: true });

  const analysesResponse = await apiFetchOr<{
    items: Array<{
      id: string;
      title: string;
      slug: string;
      summary: string | null;
      author_name: string | null;
      published_at: string | null;
    }>;
    total: number;
    page: number;
    page_size: number;
  }>(
    { items: [], total: 0, page: 1, page_size: 6 },
    `/api/v1/public/analyses?page=${analysisPage}&page_size=6`,
    { anonymous: true },
  );

  const session = await requireSession();
  const portalHref =
    session.kind === "ok"
      ? landingFor(session.profile.roles, session.profile.permissions).href
      : null;

  return (
    <div className="public-site">
      <SiteHeader />

      <main>
        {/* --- Hero ------------------------------------------------------ */}
        <div id="inicio" className="wrap">
          <div className="site-hero grid items-center gap-10 py-12 sm:py-16 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
            <div>
              <Reveal delay={0}>
                <p className="site-eyebrow">Derecho con visión de futuro</p>
              </Reveal>

              <Reveal delay={80}>
                <h1 className="site-display site-hero-title mt-7">
                  Su tranquilidad.
                  <br />
                  Nuestra <em>mejor defensa.</em>
                </h1>
              </Reveal>

              <Reveal delay={160}>
                <p className="site-body mt-7 max-w-[42ch]">
                  Acompañamiento jurídico cercano, estrategias claras y tecnología
                  para que usted siempre sepa cómo avanza su caso.
                </p>
              </Reveal>

              <Reveal delay={240}>
                <div className="mt-9 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                  {portalHref ? (
                    <Link href={portalHref} className="site-btn justify-center">
                      Ir a mi portal <span aria-hidden="true">↗</span>
                    </Link>
                  ) : (
                    <a href="#contacto" className="site-btn justify-center">
                      Solicitar consulta <span aria-hidden="true">↗</span>
                    </a>
                  )}
                  <a href="#servicios" className="site-btn line justify-center">
                    Nuestros servicios
                  </a>
                </div>
              </Reveal>

              <Reveal delay={320}>
                <p className="mt-10 text-[10px] leading-relaxed tracking-[0.24em] text-slate">
                  ESTRATEGIA · COMPROMISO · CONFIDENCIALIDAD
                </p>
              </Reveal>
            </div>

            <Reveal delay={200} className="lg:pl-4">
              <Parallax>
                <ColumnsIllustration />
              </Parallax>
            </Reveal>
          </div>
        </div>

        {/* --- Trust band ------------------------------------------------ */}
        <div className="site-band">
          <div className="wrap">
            <div className="grid gap-8 py-14 sm:grid-cols-3 sm:gap-6 sm:py-16">
              {TRUST.map((item, index) => (
                <Reveal key={item.title} delay={index * 90}>
                  <div className="trust-item">
                    <strong className="site-display block text-lg sm:text-xl">
                      {item.title}
                    </strong>
                    <span className="mt-2 block text-sm text-ivory/70">{item.body}</span>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </div>

        {/* --- Practice areas -------------------------------------------- */}
        <section id="servicios" className="site-section">
          <div className="wrap">
            <Reveal>
              <p className="site-eyebrow">Áreas de práctica</p>
            </Reveal>
            <Reveal delay={70}>
              <h2 className="site-display site-section-title mt-5">
                Respaldo jurídico para
                <br className="hidden sm:block" /> las decisiones que importan.
              </h2>
            </Reveal>
            <Reveal delay={140}>
              <p className="site-body mt-6 max-w-[52ch]">
                Personas y organizaciones encuentran un acompañamiento a la medida
                de sus retos.
              </p>
            </Reveal>

            <div className="mt-14 grid gap-x-8 gap-y-10 sm:grid-cols-2 lg:mt-16 lg:grid-cols-4">
              {(areas.length > 0
                ? areas.map((area, index) => ({
                    key: area.id,
                    title: area.name,
                    body: area.description ?? "Área de práctica del despacho.",
                    glyph: GLYPHS[index % GLYPHS.length],
                    lead: index === 0,
                  }))
                : SERVICES.map((service, index) => ({
                    key: service.title,
                    title: service.title,
                    body: service.body,
                    glyph: service.glyph,
                    lead: index === 0,
                  }))
              ).map((service, index) => (
                <Reveal
                  key={service.key}
                  delay={index * 80}
                  as="article"
                  className={`h-full ${service.lead ? "sm:col-span-2" : ""}`}
                >
                  <div
                    className={`service-card flex h-full flex-col ${
                      service.lead ? "service-card--lead" : ""
                    }`}
                  >
                    <span className="service-glyph" aria-hidden="true">
                      {service.glyph}
                    </span>
                    <h3
                      className={`site-display mt-5 ${
                        service.lead ? "text-2xl sm:text-[1.8rem]" : "text-xl sm:text-[1.45rem]"
                      }`}
                    >
                      {service.title}
                    </h3>
                    <p className="site-body-sm mt-3 flex-1">{service.body}</p>
                    <a href="#contacto" className="service-link mt-6 self-start">
                      Consultar esta área <span aria-hidden="true">↗</span>
                    </a>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* --- The firm --------------------------------------------------- */}
        <section id="firma" className="site-band site-section">
          <div className="wrap grid gap-14 lg:grid-cols-2 lg:gap-20">
            <div>
              <Reveal>
                <p className="site-eyebrow">Nuestra forma de trabajar</p>
              </Reveal>
              <Reveal delay={70}>
                <h2 className="site-display site-section-title mt-5">
                  Escuchamos su historia.
                  <br className="hidden sm:block" /> Defendemos sus intereses.
                </h2>
              </Reveal>
              <Reveal delay={140}>
                <p className="site-body mt-7 max-w-[46ch]">
                  Generamos mecanismos de solución de conflictos en aplicación
                  del ordenamiento jurídico, humanizando su aplicación en pro de
                  la justicia y en aras de la configuración de un mejor país.
                </p>
              </Reveal>
              <Reveal delay={190}>
                <p className="site-body-sm mt-7 max-w-[46ch] text-petrol-soft">
                  Una buena asesoría comienza por entender lo que está en juego.
                  Proponemos una experiencia jurídica con comunicación clara,
                  organización y acompañamiento en cada etapa.
                </p>
              </Reveal>
              <Reveal delay={210}>
                <a href="#contacto" className="site-btn gold mt-9">
                  Conversemos sobre su caso <span aria-hidden="true">↗</span>
                </a>
              </Reveal>
            </div>

            <div className="grid gap-px bg-ivory/12 sm:grid-cols-2">
              {PRINCIPLES.map((principle, index) => (
                <Reveal key={principle.number} delay={index * 80}>
                  <div className="h-full bg-petrol-deep p-6 sm:p-7">
                    <span className="text-[10px] tracking-[0.2em] text-gold-bright">
                      {principle.number}
                    </span>
                    <h3 className="site-display mt-3 text-lg sm:text-xl">
                      {principle.title}
                    </h3>
                    <p className="mt-2.5 text-sm leading-relaxed text-ivory/70">
                      {principle.body}
                    </p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>

          {/* The firm's own words, attributed. */}
          <Reveal delay={120}>
            <figure className="mt-16 border-t border-ivory/15 pt-10 text-center sm:mt-20">
              <blockquote className="site-display mx-auto max-w-[34ch] text-xl leading-snug text-ivory/90 sm:text-2xl lg:text-[1.7rem]">
                «Colombianos, las armas os han dado la independencia, pero solo
                las leyes os darán la libertad.»
              </blockquote>
              <figcaption className="mt-5 text-[10px] tracking-[0.2em] text-gold-bright">
                GENERAL FRANCISCO DE PAULA SANTANDER
              </figcaption>
            </figure>
          </Reveal>
        </section>

        {/* --- The client portal ------------------------------------------ */}
        <section id="portal" className="site-section">
          <div className="wrap grid items-center gap-14 lg:grid-cols-2 lg:gap-20">
            <div>
              <Reveal>
                <p className="site-eyebrow">Portal de clientes</p>
              </Reveal>
              <Reveal delay={70}>
                <h2 className="site-display site-section-title mt-5">
                  Su caso, más cerca.
                  <br className="hidden sm:block" /> Desde cualquier lugar.
                </h2>
              </Reveal>
              <Reveal delay={140}>
                <p className="site-body mt-7 max-w-[46ch]">
                  Una ventana a su proceso: consulte novedades, documentos y
                  próximas citas con una experiencia sencilla.
                </p>
              </Reveal>
              <Reveal delay={200}>
                <ul className="mt-8 grid gap-x-6 gap-y-3 sm:grid-cols-2">
                  {PORTAL_CHECKS.map((check) => (
                    <li
                      key={check}
                      className="flex items-start gap-2.5 text-sm text-petrol-soft"
                    >
                      <span aria-hidden="true" className="mt-0.5 text-gold">
                        ✓
                      </span>
                      {check}
                    </li>
                  ))}
                </ul>
              </Reveal>
              <Reveal delay={260}>
                <Link href="/login" className="site-btn gold mt-9">
                  Explorar el portal <span aria-hidden="true">↗</span>
                </Link>
              </Reveal>
            </div>

            {/*
              An illustrative mock. The figures are invented and the panel says
              so, because a screenshot-shaped element full of real-looking
              numbers is the fastest way to make a proposal look like a product
              that already exists.
            */}
            <Reveal delay={160}>
              <div
                aria-label="Vista ilustrativa del portal de clientes, con datos ficticios"
                className="border border-ivory-line bg-surface p-6 shadow-[0_30px_60px_-45px_rgba(19,44,53,0.55)] sm:p-8"
              >
                <div className="flex items-center justify-between gap-3">
                  <b className="text-[10px] tracking-[0.18em] text-petrol sm:text-[11px]">
                    WABOGADOS / MI PORTAL
                  </b>
                  <span className="pending-tag">Vista de ejemplo</span>
                </div>

                <h3 className="site-display mt-7 text-2xl">Bienvenido a su espacio.</h3>
                <p className="site-body-sm mt-2">
                  Aquí encuentra las novedades de sus procesos.
                </p>

                <div className="mt-7 grid grid-cols-3 gap-3 border-y border-ivory-line py-6">
                  {[
                    ["02", "EXPEDIENTES ACTIVOS"],
                    ["08", "DOCUMENTOS"],
                    ["01", "PRÓXIMA CITA"],
                  ].map(([figure, label]) => (
                    <div key={label}>
                      <b className="site-display block text-3xl text-petrol sm:text-4xl">
                        {figure}
                      </b>
                      <span className="mt-1.5 block text-[9px] leading-tight tracking-[0.12em] text-slate">
                        {label}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="mt-6 space-y-3">
                  {[
                    ["Asesoría contractual", "EXP-2026-001 · Derecho civil", "En seguimiento"],
                    ["Última actuación", "Se incorporó un nuevo documento al expediente.", null],
                    ["Próxima reunión", "Revisión de avances con su abogado asignado.", null],
                  ].map(([title, detail, tag]) => (
                    <div key={title} className="border border-ivory-line p-4">
                      {tag ? <span className="pending-tag float-right">{tag}</span> : null}
                      <b className="text-sm text-petrol-soft">{title}</b>
                      <small className="mt-1 block text-[11px] text-slate">{detail}</small>
                    </div>
                  ))}
                </div>

                <p className="site-note mt-6">
                  Los datos mostrados son ficticios y no proceden de ningún
                  expediente.
                </p>
              </div>
            </Reveal>
          </div>
        </section>

        {/* --- Team --------------------------------------------------------- */}
        <section id="equipo" className="site-section bg-ivory-warm">
          <div className="wrap">
            <div className="grid gap-8 lg:grid-cols-[1.15fr_1fr] lg:items-end">
              <div>
                <Reveal>
                  <p className="site-eyebrow">Nuestro equipo</p>
                </Reveal>
                <Reveal delay={70}>
                  <h2 className="site-display site-section-title mt-5">
                    Personas comprometidas
                    <br className="hidden sm:block" /> con su tranquilidad.
                  </h2>
                </Reveal>
              </div>
              <Reveal delay={140}>
                <p className="site-body">
                  Los profesionales de la firma, con el cargo que cada uno
                  sostiene en el día a día.
                </p>
              </Reveal>
            </div>

            <div className="mt-14 grid gap-8 sm:grid-cols-3">
              {(publicLawyers.some((lawyer) => lawyer.photo_url)
                ? publicLawyers
                    .filter((lawyer) => lawyer.photo_url)
                    .map((lawyer) => ({
                      name: lawyer.full_name,
                      role:
                        lawyer.specialties[0] ??
                        lawyer.legal_areas[0] ??
                        "Abogado",
                      image: lawyer.photo_url as string,
                      width: 480,
                      height: 480,
                    }))
                : TEAM
              ).map((member, index) => (
                <Reveal key={member.name} delay={index * 90}>
                  <figure className="portrait">
                    <Image
                      src={member.image}
                      alt={`Fotografía de ${member.name}`}
                      width={member.width}
                      height={member.height}
                      sizes="(min-width: 640px) 30vw, 90vw"
                      className="portrait-img"
                    />
                  </figure>
                  <h3 className="site-display mt-5 text-xl">{member.name}</h3>
                  <p className="site-body-sm mt-1.5">{member.role}</p>
                </Reveal>
              ))}
            </div>

            <Reveal delay={120}>
              <p className="site-note mt-12">
                <span className="pending-tag mr-3">Pendiente</span>
                Se publican{" "}
                <strong>nombres, cargos y fotografías facilitados por la firma</strong>
                . No se han incluido formación, años de ejercicio, cartera de
                casos ni distinciones: son datos que la firma no ha facilitado.
              </p>
            </Reveal>
          </div>
        </section>

        <NewsSection />

        {/* --- Allies -------------------------------------------------------- */}
        <section className="site-section bg-ivory-warm" aria-labelledby="aliados">
          <div className="wrap">
            <div className="grid gap-8 lg:grid-cols-[1.15fr_1fr] lg:items-end">
              <div>
                <Reveal>
                  <p className="site-eyebrow">Aliados estratégicos</p>
                </Reveal>
                <Reveal delay={70}>
                  <h2 id="aliados" className="site-display site-section-title mt-5">
                    Redes que amplían
                    <br className="hidden sm:block" /> lo que podemos resolver.
                  </h2>
                </Reveal>
              </div>
              <Reveal delay={140}>
                <p className="site-body">
                  Trabajamos con aliados para prestar el mejor servicio en los
                  asuntos que exceden nuestra práctica.
                </p>
              </Reveal>
            </div>

            <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:mt-14">
              {ALLIES.map((ally, index) => (
                <Reveal key={ally.name} delay={index * 90}>
                  <div>
                  <div className="ally-mark">
                    <Image
                      src={ally.image}
                      alt={`Logotipo de ${ally.name}`}
                      width={500}
                      height={302}
                      sizes="(min-width: 640px) 45vw, 90vw"
                      className="ally-mark-img"
                    />
                  </div>
                  <span className="mt-4 block text-[11px] tracking-[0.16em] text-slate">
                    {ally.name}
                  </span>
                </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {announcements.length > 0 ? (
          <section className="site-section bg-ivory-warm">
            <div className="wrap">
              <p className="site-eyebrow">Novedades</p>
              <h2 className="site-display site-section-title mt-5">
                Información actualizada del despacho.
              </h2>
              <div className="mt-8 space-y-4">
                {announcements.map((item) => (
                  <article
                    key={item.key}
                    className="border border-ivory-line bg-surface p-6"
                  >
                    {item.description ? (
                      <p className="text-[10px] tracking-[0.2em] text-gold-bright">
                        {item.description}
                      </p>
                    ) : null}
                    <p className="site-body-sm mt-2">{item.value}</p>
                  </article>
                ))}
              </div>
            </div>
          </section>
        ) : null}

        <section className="site-section">
          <div className="wrap">
            <p className="site-eyebrow">Criterio Legal</p>
            <h2 className="site-display site-section-title mt-5">
              Últimos análisis del despacho.
            </h2>
            {analysesResponse.items.length === 0 ? (
              <p className="site-body mt-6 max-w-[52ch]">
                Próximamente publicaremos análisis y criterios jurídicos.
              </p>
            ) : (
              <>
                <div className="mt-8 grid gap-6 sm:grid-cols-2">
                  {analysesResponse.items.map((item) => (
                    <article
                      key={item.id}
                      className="border border-ivory-line bg-surface p-6"
                    >
                      <h3 className="site-display text-xl">{item.title}</h3>
                      {item.summary ? (
                        <p className="site-body-sm mt-2">{item.summary}</p>
                      ) : null}
                      <div className="mt-4 flex items-center justify-between text-xs text-ink-muted">
                        <span>{item.author_name ?? "Despacho"}</span>
                        <span>
                          {item.published_at
                            ? new Date(item.published_at).toLocaleDateString("es-CO")
                            : ""}
                        </span>
                      </div>
                      <Link
                        href={`/analisis/${item.slug}`}
                        className="mt-4 inline-block text-xs font-semibold uppercase tracking-[0.1em] text-wax underline-offset-4 hover:underline"
                      >
                        Leer análisis →
                      </Link>
                    </article>
                  ))}
                </div>
                <div className="mt-8 flex gap-3">
                  {analysisPage > 1 ? (
                    <Link
                      href={`/?analisis=${analysisPage - 1}#criterio`}
                      className="site-btn line justify-center"
                    >
                      Anterior
                    </Link>
                  ) : null}
                  {analysisPage * analysesResponse.page_size < analysesResponse.total ? (
                    <Link
                      href={`/?analisis=${analysisPage + 1}#criterio`}
                      className="site-btn justify-center"
                    >
                      Siguiente
                    </Link>
                  ) : null}
                </div>
              </>
            )}
          </div>
        </section>

        {/* --- Contact ------------------------------------------------------ */}
        <section id="contacto" className="site-section">
          <div className="wrap grid gap-14 lg:grid-cols-2 lg:gap-20">
            <div>
              <Reveal>
                <p className="site-eyebrow">Hablemos</p>
              </Reveal>
              <Reveal delay={70}>
                <h2 className="site-display site-section-title mt-5">
                  El primer paso es
                  <br className="hidden sm:block" /> contarnos su situación.
                </h2>
              </Reveal>
              <Reveal delay={140}>
                <p className="site-body mt-7 max-w-[46ch]">
                  Déjenos sus datos y el área de consulta para iniciar una
                  conversación con nuestro equipo.
                </p>
              </Reveal>

              <Reveal delay={200}>
                <address className="mt-8 border border-ivory-line bg-ivory-warm p-6 not-italic">
                  <b className="block">Atención a personas y organizaciones</b>
                  <span className="mt-3 block text-slate">
                    {CONTACT.address}
                  </span>
                  <span className="mt-1.5 block">
                    <a
                      className="text-petrol-soft underline decoration-gold decoration-1 underline-offset-4 hover:text-gold-deep"
                      href={`tel:${CONTACT.phoneHref}`}
                    >
                      {CONTACT.phone}
                    </a>
                  </span>
                  <span className="mt-1.5 block text-slate">
                    {CONTACT.schedule}
                  </span>
                  <span className="mt-1.5 block text-slate">
                    Estado del sistema:{" "}
                    <strong>
                      {health.status === "ready" ? "Operativo" : "No disponible"}
                    </strong>
                  </span>

                  <div className="mt-6 overflow-hidden rounded-card border border-ivory-line">
                    <iframe
                      title="Ubicación del despacho"
                      src="https://www.openstreetmap.org/export/embed.html?bbox=-74.076%2C4.600%2C-74.068%2C4.606&layer=mapnik&marker=4.603%2C-74.072"
                      loading="lazy"
                      referrerPolicy="no-referrer-when-downgrade"
                      className="h-64 w-full border-0"
                    />
                  </div>
                  <span className="mt-3 block text-slate">
                    Correo electrónico: <strong>por confirmar</strong>. El sitio
                    de la firma lo publica protegido y no puede leerse desde el
                    código fuente.
                  </span>
                </address>
              </Reveal>

              <Reveal delay={260}>
                <p className="site-note mt-7">
                  <span className="pending-tag mr-3">Pendiente de revisión</span>
                  El formulario <strong>envía su solicitud de verdad</strong> y
                  solo confirma cuando el sistema la ha registrado. El aviso de
                  privacidad está redactado con los datos que la firma publica,
                  pero <strong>falta que el despacho lo revise y lo apruebe</strong>
                  antes de publicar: están sin confirmar la razón social completa y
                  el canal para ejercer los derechos.
                </p>
              </Reveal>
            </div>

            <Reveal delay={160}>
              <ContactForm />
            </Reveal>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
