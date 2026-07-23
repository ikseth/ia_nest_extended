# Decision 0005: disolucion de historic; personalidad como estado mas evidencia enlazada

Fecha: 2026-07-18

## Decision

Se elimina `historic` como tipo de memoria (supersede parcial de la enumeracion
de delegadas del ADR 0002: `persona` y `principles` quedan; `historica` se
disuelve). Su funcion se reparte sin crear tier:

1. **Personalidad = `identity` + `principles`**: el estado actual del yo,
   pequeno y versionado, de INYECCION PERMANENTE en el contexto (via el system
   prompt por perfil del core, ADR 0025; es el bucle de re-inyeccion de
   `docs/VISION_MEMORIA.md`). Es lo que conscience ira definiendo con el tiempo.
2. **Evidencia formativa = enlaces, no tipo**: un "recuerdo formativo" es un
   engrama normal (episodico/semantico, vivo o archivado) REFERENCIADO por un
   principio o por la identidad via `evidence_refs`. Como no hay borrado fisico,
   la referencia nunca se rompe. Reusa el grafo de enlaces nombrado en ADR 0004,
   generalizado a enlaces desde delegadas hacia engramas.
3. **Relato formativo por relevancia**: diferido con nombre. Si el ente necesita
   contar sus recuerdos formativos, conscience puede escribirlos como contenido
   delegado en el tier semantico; declaracion, no maquinaria nueva.

Refinamiento de la regla de validacion (precisa ADR 0003): los tipos se
distinguen por el CONJUNTO de sus ejes (modo de recuperacion, dueno, scope,
namespace); aliasing es coincidir en todos. Dos tipos pueden compartir tier si
difieren en dueno o scope. Con esto, las delegadas quedan nitidas por modo:
inyeccion permanente (`identity`, `principles`, `safety`) y lookup de perfil
(`entities`); NINGUNA usa el ranking del ADR 0003.

## Motivo

Dos razones independientes, ambas del usuario en reconciliacion:

- "La historia ya esta": el archivo del ente existe por construccion (sin
  borrado fisico mas destilado semantico); un tier llamado `historic` sugiere
  archivar, que ya es gratis.
- Sin patron propio: seria "durable, sin decaimiento, escrito por conscience",
  exactamente lo que ya son `identity`/`principles`. Un tier sin comportamiento
  propio es la Leccion 1 (core ADR 0011) en el lado delegado.

La cantera ya contenia la solucion dibujada: `consciousness_principles` llevaba
`evidence_refs` y existia `memory_links`. En la cantera `historic` existia para
alimentar los principios: era combustible de la personalidad, no archivo. Se
conserva la funcion (evidencia revisable para reforzar/debilitar principios) sin
el tier.

## Consecuencia

- `docs/ROSTER_MEMORIA.md` pierde la fila `historic`, gana la columna "modo de
  recuperacion" en delegadas y pasa de PROPUESTA a RECONCILIADO: la Fase 2 queda
  implementable.
- `docs/VISION_MEMORIA.md` y `docs/PLAN.md` se alinean.
- ADR 0002 queda parcialmente superado solo en su enumeracion de ejemplo; el
  mecanismo (clases, autoridad de escritura, costura) permanece integro.
- Impacto de version: ninguno (sin contrato publico cortado; Fase 7).
