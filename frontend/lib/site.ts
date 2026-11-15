export const SITE_NAME = "WABOGADOS";

export const SITE_CONTACT = {
  address: "Edificio Berna Carrera 9 No. 16-20 Oficina 206, Bogotá D.C.",
  phone: "+57 312 469 9617",
  phoneHref: "+573124699617",
  email: "amiabogado@hotmail.com",
  schedule: "Lunes a viernes, 8:00 a. m. a 7:00 p. m.",
  city: "Bogotá D.C.",
  country: "Colombia",
};

export const SITE_DESCRIPTION =
  "Acompañamiento jurídico para personas y empresas en Bogotá: orientación clara, estrategia y seguimiento en áreas como penal, familiar, laboral, civil, comercial y más.";

export function siteUrl(): string {
  const raw = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (!raw) return "http://localhost:3000";
  return raw.replace(/\/$/, "");
}
