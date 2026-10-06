# Preferencias del Proyecto

Registrar preferencias técnicas y operativas estables.

## Como decide la firma (observado el 2026-10-02)

- **Pide el CRUD completo y hay que entregarlo entero.** Cuando dijo que necesitaba
  editar y eliminar, la respuesta correcta no fue decir que ya existia ni negarse:
  fue explicar que faltaba de verdad el acceso desde el listado, arreglarlo, y
  llevar la parte irreversible a una decision explicita.
- **Ante un choque con una regla del proyecto, decide ella.** Ante eliminar contra
  la regla 5 eligio desactivar y archivar, sin mas discusion. Preguntar con la
  regla citada y el riesgo concreto es lo que desbloquea; negar sin preguntar
  deja la pantalla sin lo que se pidio.
- **Pide pulido visual de forma explicita.** Primero pidio una interfaz mas
  elegante, y despues el boton hamburguesa: no acepta una version que funcione pero
  se vea como un formulario gris sobre papel gris.

## Como trabajar con esta persona

- Responder en espanol.
- Prefiere que se le diga **que se verifico y como**, no que se afirme que algo
  funciona. Las comprobaciones concretas -ciclo contra el despliegue, ids
  duplicados, cero desbordamiento en cuatro anchos- son lo que da confianza.
- Las decisiones irreversibles -borrar un registro juridico, anular una regla del
  proyecto- se le presentan con su coste, no se ejecutan por su cuenta.

## Lo que hay que tener presente

- "No se puede hacer" y "no se ha decidido" son cosas distintas. La regla existe
  para que alguien la confirme o la anule.
- Cuando la accion destructiva no se puede probar sin dejar los datos de
  demostracion en mal estado -desactivar al unico abogado activo-, se abre el
  dialogo y se cancela, y **se dice que no se confirmo**.