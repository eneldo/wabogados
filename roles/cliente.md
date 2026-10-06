# ROL — CLIENTE

Acceso únicamente a información publicada y vinculada a su identidad.

## Permisos (Fase 5)

- `cases:read_published`
- `actions:read_published`
- `calendar:read_published`

El alcance se resuelve con `Client.user_id`: el usuario solo alcanza los
expedientes de su propia ficha y, dentro de ellos, únicamente lo `publicada`.

## Comportamiento esperado

- No ve actuaciones internas ni de equipo.
- No ve expedientes de otros clientes; la API responde 404.
- No puede crear, modificar ni cerrar nada.
- Pedir un filtro de visibilidad no permitida devuelve una lista vacía, no un
  error, para no confirmar la existencia de información reservada.

## Pendiente por fase

- Fase 6: `documents:read_published`.
- Fase 7: `evidences:read_published` y descarga de originales autorizada.
- Fase 8: mensajería con el expediente.

## Restricciones de diseño

- No debe ver información interna de otros clientes.
- Solo evidencias y documentos publicados.
- El acceso cruzado entre clientes debe quedar bloqueado en el backend.
