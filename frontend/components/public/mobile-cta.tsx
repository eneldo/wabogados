export function PublicMobileCta({
  phone,
  phoneHref,
  consultHref = "/#contacto",
}: {
  phone: string;
  phoneHref: string;
  consultHref?: string;
}) {
  return (
    <div className="public-mobile-cta" role="region" aria-label="Acciones rápidas de contacto">
      <a href={`tel:${phoneHref}`} className="site-btn line public-mobile-cta-btn">
        Llamar
      </a>
      <a href={consultHref} className="site-btn public-mobile-cta-btn">
        Consultar
      </a>
      <span className="sr-only">Teléfono: {phone}</span>
    </div>
  );
}
