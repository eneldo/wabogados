import type { LegalAreaOption } from "./types";

export type ServiceIconName =
  | "landmark" | "leaf" | "bank" | "contract" | "store" | "family"
  | "house" | "globe" | "briefcase" | "shield" | "file-check"
  | "receipt" | "book" | "building" | "scales";

const SERVICE_ICONS: Record<string, ServiceIconName> = {
  administrativo: "landmark",
  ambiental: "leaf",
  bancario: "bank",
  civil: "contract",
  comercial: "store",
  familia: "family",
  familiar: "family",
  "ley-familiar": "family",
  inmobiliario: "house",
  internacional: "globe",
  laboral: "briefcase",
  penal: "shield",
  procesal: "file-check",
  tributario: "receipt",
  fiscal: "receipt",
  constitucional: "book",
  "asesorias-empresariales": "building",
  "asesoria-empresarial": "building",
  empresarial: "building",
};

/** The firm's published copy, used only when the live catalogue is unavailable. */
const FALLBACK_SERVICES = [
  { title: "Derecho penal", body: "Asesoría a altos ejecutivos para tomar mejores decisiones en casos penales." },
  { title: "Ley familiar", body: "Derechos y deberes de los esposos y los hijos, filiación, sucesiones, divorcios, separaciones y alimentos." },
  { title: "Derecho laboral", body: "El equilibrio en las relaciones contractuales de tipo laboral y profesional." },
  { title: "Derecho constitucional", body: "Efectivizar el derecho constitucional para que cada persona pueda vivir con dignidad, por vía legal y jurisprudencial." },
  { title: "Derecho civil", body: "Las relaciones contractuales de las personas, por voluntad de las partes o por hechos meramente naturales." },
  { title: "Derecho comercial", body: "La rama del derecho privado que regula la realización de actos de comercio." },
  { title: "Asesorías empresariales", body: "Asistencia legal a empresas en materia comercial, laboral, societaria y de marcas." },
];

export function serviceSlug(name: string): string {
  return name.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

/** Resolve by meaning, never by catalogue position or database ID. */
export function serviceIconName(name: string): ServiceIconName {
  const key = serviceSlug(name).replace(/^derecho-(?:de-|del-)?/, "");
  return Object.hasOwn(SERVICE_ICONS, key) ? SERVICE_ICONS[key] : "scales";
}

export function publicServices(areas: LegalAreaOption[]) {
  const items = areas.length > 0
    ? areas.map((area) => ({
        key: area.id,
        title: area.name,
        body: area.description ?? "Área de práctica del despacho.",
      }))
    : FALLBACK_SERVICES.map((service) => ({ ...service, key: service.title }));

  return items.map((service, index) => ({
    ...service,
    slug: serviceSlug(service.title),
    icon: serviceIconName(service.title),
    lead: index === 0,
  }));
}
