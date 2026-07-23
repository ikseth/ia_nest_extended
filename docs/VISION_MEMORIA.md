# Vision de la memoria de ia_nest_extended

Estado: reconciliado
Version: 0.1 - 2026-07-18

## El fin

El fin de esta capa NO es recordar la conversacion. Es dar al ente un YO SIMULADO,
CONTINUO Y EVOLUTIVO: continuidad de lo vivido, un caracter sedimentado, perfiles
de con quien y con que se relaciona, y conocimiento donde apoyarse.

La personalidad no se configura: EMERGE DEL BUCLE.

    experiencia -> consolidacion -> sedimento (identidad / principios)
                -> re-inyeccion en el prompt -> comportamiento -> nueva experiencia

Criterio de aceptacion heredado de la cantera `ia_nest`: la memoria deja de ser
cache de conversacion y pasa a ser sistema cognitivo.

## La frontera: sustrato aqui, juicio en conscience

La cantera ponia memoria y conciencia en el centro del motor. La doctrina del ente
(core ADR 0031/0033/0034/0035) las separo en capas:

- `ia_nest_extended` es el SUSTRATO y el MECANISMO del yo: modelo de tipos,
  almacenamiento auditable sin borrado, promocion y compresion, recuperacion.
- `ia_nest_core_conscience` es el JUICIO que lo cultiva: decide que merece
  sedimentarse y reescribe el caracter.

Dicho corto: extended es el sustrato del yo que conscience cultiva; no es el
cultivador.

Principio que fija la frontera (ADR 0002): el caracter del ente no es mutable por
la experiencia en bruto; solo la reflexion reescribe el yo. Por eso el camino
experiencial (write-back) no puede escribir las memorias de identidad.

## Funciones de memoria deseadas

Ambicion heredada de la cantera y reconciliada aqui. Se listan como FUNCIONES; su
tipificacion concreta (clase, tier, namespace) se reconcilia en la Fase 2 del PLAN.

| Funcion | Que guarda | Clase prevista |
|---|---|---|
| Conversacional | contexto del hilo o sesion activa | estricta |
| Corto plazo | temas recientes, contexto medio | estricta |
| Medio plazo | hitos de relevancia media/alta, detalle segun relevancia | estricta |
| Largo plazo | hitos antiguos de alta relevancia, detalle bajo | estricta |
| Entidades | perfiles de personas, objetos y proyectos con los que se relaciona | delegada (conscience), con etiquetado mecanico de extended (ADR 0004) |
| Formativa | experiencias que justifican principios (incluidas las negativas) | disuelta en enlaces `evidence_refs` hacia engramas (ADR 0005) |
| Identidad | quien soy, que hago, caracterizacion del yo; con `principles`, la personalidad | delegada (conscience), inyeccion permanente |
| Conocimientos | conocimiento tecnico y humanistico documental | no es memoria (ver abajo) |

Dos aportes sobre la ambicion original de la cantera:

1. ENTIDADES como ciudadano de primera (alli quedaba implicito en la segmentacion
   por servicio y dominio).
2. GRADIENTE DE DETALLE: el detalle decrece con la edad y la relevancia. El largo
   plazo no es "lo mismo mas viejo": es lo mismo COMPRIMIDO.

## Conocimientos (RAG) no es un tier de memoria

Es un subsistema hermano (Fase 5): curado y externo, indexado por dominio, no
autobiografico, no decae por edad, compartido y no segmentado por sesion. Comparte
con la memoria el MECANISMO de recuperacion e inyeccion en el prompt -y su
presupuesto- pero no el MODELO. No se colapsan.

La cantera distinguia ademas un corpus de conocimiento etico para la deliberacion
de conciencia; eso pertenece a conscience, no a esta capa.

## Regla de retencion

TTL significa salida de la ventana caliente, no eliminacion. No hay borrado fisico
en el flujo normal: se archiva, se supersede y se registra el lineage. Heredado de
la cantera y vinculante para el modelo de tipos (ADR 0002).

## Que esta decidido y que no

- Decidido: el fin, la frontera con conscience y el MECANISMO (registro de tipos,
  clases estrictas y delegadas, autoridad de escritura por capacidad, costura de
  consolidacion). Ver ADR 0002.
- Decidido: el modelo de relevancia y el gradiente de tiers (Opcion C: tres tiers
  -conversacional / episodica / semantica- definidos por su vector de pesos, no
  por ventanas de fecha; el gradiente corto/medio/largo se disuelve en la curva
  de recencia y en el namespace `tasks`). Motor: `postgres + pgvector`. Ver
  ADR 0003.
- Decidido: entities como tercer patron (perfil mutable versionado que se
  actualiza, no decae) y el modelo multi-espacio de recuperacion (cada espacio en
  su representacion natural; lo exacto no se aproxima). Ver ADR 0004. Vocabulario:
  ENGRAMA = registro individual de memoria.
- Decidido: no hay tipo `historic`; personalidad = `identity` + `principles`
  (inyeccion permanente) y la evidencia formativa son enlaces hacia engramas.
  Ver ADR 0005.
- Decidido: el roster de tipos, `docs/ROSTER_MEMORIA.md` (reconciliado).
- Dependencia por decidir (Fase 2/3): el modelo de embeddings y su dimensionalidad
  (servible por el Ollama del lab).
