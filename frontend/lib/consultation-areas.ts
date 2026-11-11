/** The current backend intake contract. Keep compatibility without losing the chosen service. */
export const CONSULTATION_AREAS = [
  "Derecho penal", "Ley familiar", "Derecho laboral", "Derecho constitucional",
  "Derecho civil", "Derecho comercial", "Asesorías empresariales", "Otra consulta",
];

const ALIASES: Record<string, string> = {
  Penal: "Derecho penal",
  Familia: "Ley familiar",
  Laboral: "Derecho laboral",
  Constitucional: "Derecho constitucional",
  Civil: "Derecho civil",
  Comercial: "Derecho comercial",
};

export function consultationSubject(area: string, message: string) {
  const canonical = CONSULTATION_AREAS.includes(area)
    ? area : Object.hasOwn(ALIASES, area) ? ALIASES[area] : "Otra consulta";
  return {
    area: canonical,
    message: canonical === area ? message : `Área de consulta: ${area}.\n\n${message}`,
  };
}
