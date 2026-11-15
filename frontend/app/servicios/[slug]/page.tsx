import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { ContactForm } from "@/components/public/contact-form";
import { PublicAnalytics } from "@/components/public/public-analytics";
import { PublicMobileCta } from "@/components/public/mobile-cta";
import { SiteFooter, SiteHeader } from "@/components/public/site-header";
import { getPublicServices } from "@/lib/public-services.server";
import { SITE_CONTACT, SITE_NAME, siteUrl } from "@/lib/site";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const { services } = await getPublicServices();
  const service = services.find((item) => item.slug === slug);
  if (!service) {
    return {
      title: "Áreas de práctica",
      description: "Áreas de práctica y servicios jurídicos de WABOGADOS.",
      robots: { index: false, follow: true },
    };
  }
  const description = `${service.body}${service.hint ? ` Cuándo acudir: ${service.hint}` : ""}`.slice(0, 160);
  const path = `/servicios/${service.slug}`;
  return {
    title: service.title,
    description,
    alternates: { canonical: path },
    openGraph: {
      title: `${service.title} | WABOGADOS`,
      description,
      url: path,
      locale: "es_CO",
      type: "website",
      siteName: SITE_NAME,
      images: [{ url: "/marca/wabogados-logo.webp", alt: "WABOGADOS" }],
    },
    twitter: {
      card: "summary_large_image",
      title: `${service.title} | WABOGADOS`,
      description,
      images: ["/marca/wabogados-logo.webp"],
    },
  };
}

export default async function ServicePage({ params }: Props) {
  const { slug } = await params;
  const { services, available } = await getPublicServices();
  const service = services.find((item) => item.slug === slug);

  if (!service && available) notFound();

  const serviceJsonLd = service
    ? {
        "@context": "https://schema.org",
        "@type": "LegalService",
        name: `${service.title} - ${SITE_NAME}`,
        serviceType: service.title,
        description: service.body,
        provider: { "@type": "LegalService", name: SITE_NAME, telephone: SITE_CONTACT.phone, email: SITE_CONTACT.email },
        areaServed: "Colombia",
        url: `${siteUrl()}/servicios/${service.slug}`,
      }
    : null;

  return (
    <div className="public-site public-home public-service">
      {serviceJsonLd ? (
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceJsonLd) }} />
      ) : null}
      {service ? <PublicAnalytics path={`/servicios/${service.slug}`} enabled={process.env.WEBSITE_ANALYTICS_ENABLED !== "false"} /> : null}
      <SiteHeader homePage={false} />
      <main id="contenido-principal" className="wrap py-12 sm:py-16">
        <nav aria-label="Ruta de navegación" className="mb-10 flex flex-wrap gap-3 text-sm text-slate">
          <Link href="/" className="hover:text-gold">Inicio</Link>
          <span aria-hidden="true">/</span>
          <Link href="/#servicios" className="hover:text-gold">Servicios</Link>
          {service ? <><span aria-hidden="true">/</span><span aria-current="page">{service.title}</span></> : null}
        </nav>

        {service ? (
          <>
            <section className="service-detail-grid" aria-labelledby="service-title">
              <div>
                <p className="site-eyebrow">Área de práctica</p>
                <h1 id="service-title" className="site-display mt-6 text-4xl sm:text-5xl lg:text-6xl">{service.title}</h1>
                <p className="site-body mt-7 max-w-[50ch]">{service.body}</p>
                {service.hint ? (
                  <p className="mt-5 max-w-[50ch] text-sm text-slate">
                    <strong className="font-semibold text-petrol-soft">Cuándo acudir:</strong> {service.hint}
                  </p>
                ) : null}
                <div className="mt-8 flex flex-wrap gap-3">
                  <a href="#consulta" className="site-btn">Consultar sobre {service.title} <span aria-hidden="true">↓</span></a>
                  <Link href="/#servicios" className="site-btn line">Ver todas las áreas</Link>
                </div>

                <div className="service-detail-guide mt-12">
                  <h2 className="site-display text-2xl">Cómo iniciar su consulta</h2>
                  <ol className="mt-6 space-y-6">
                    {[
                      ["Cuéntenos su situación", "Describa lo sucedido y qué necesita consultar, sin incluir contraseñas ni información bancaria."],
                      ["Organice sus antecedentes", "Tenga a mano las fechas y documentos relevantes. No necesita adjuntarlos a este formulario."],
                      ["El despacho revisará su solicitud", "El equipo valorará la consulta y le contactará por los medios que indique. El envío no implica la aceptación de un encargo profesional."],
                    ].map(([title, body], index) => (
                      <li key={title} className="flex gap-4">
                        <span className="home-index" aria-hidden="true">0{index + 1}</span>
                        <div><h3 className="text-sm font-semibold">{title}</h3><p className="site-body-sm mt-1">{body}</p></div>
                      </li>
                    ))}
                  </ol>
                </div>
              </div>

              <section id="consulta" className="service-detail-form" aria-labelledby="consultation-title">
                <p className="site-eyebrow">Hablemos de su caso</p>
                <h2 id="consultation-title" className="site-display mt-5 text-2xl">Solicitar una consulta</h2>
                <p className="site-body-sm mt-3 mb-7">Área seleccionada: <strong>{service.title}</strong>. Complete sus datos para que podamos contactarle.</p>
                <ContactForm key={service.slug} requestedArea={service.title} areas={services.map((item) => item.title)} />
                <p className="site-note mt-6">El tratamiento de sus datos se realiza conforme al aviso de privacidad aprobado por el despacho. El envío de esta solicitud no garantiza un resultado ni un plazo de respuesta.</p>
              </section>
            </section>
            <div className="mt-12 border-t border-ivory-line pt-8 text-sm text-slate">
              ¿Prefiere hablar con nosotros? <a href="tel:+573124699617" className="service-link">+57 312 469 9617</a>
            </div>
          </>
        ) : (
          <section className="py-12" role="status">
            <h1 className="site-display text-3xl">No pudimos cargar esta área</h1>
            <p className="site-body mt-5">El catálogo no está disponible en este momento. Inténtelo de nuevo o llámenos al +57 312 469 9617.</p>
            <Link href="/#servicios" className="site-btn mt-7">Volver a los servicios</Link>
          </section>
        )}
      </main>
      <PublicMobileCta phone={SITE_CONTACT.phone} phoneHref={SITE_CONTACT.phoneHref} consultHref="#consulta" />
      <SiteFooter homePage={false} />
    </div>
  );
}
