## 3. Población inicial

- Los individuos iniciales se generan con:
  `generate_random_feasible_fixing`

- Por tanto, la población inicial parte de soluciones **factibles**.

---

## 4. Evaluación

- Evaluación principal: `evaluate_solution_multi`
- Objetivos:
  - maximizar `tau_sum`
  - maximizar `eta_sum`
  - minimizar `lbar_sum`
  - minimizar `sigma_sum`

- Evaluación escalar (`evaluate_solution_scalar`):
  - solo como apoyo para desempates, análisis o poda auxiliar, no como criterio principal.

---

## 5. Selección

- Método: **NSGA-III**

La selección se basará en:

- ordenación por frentes no dominados,
- asociación de soluciones a **reference points / reference directions**,
- mantenimiento de diversidad guiado por esas direcciones de referencia.

**Motivo:** con 4 objetivos, NSGA-III resulta más adecuado que NSGA-II para repartir mejor la población por el frente y evitar pérdida de capacidad discriminatoria de la dominancia.

---

## 6. Cruce

- El cruce combinará asignaciones de dos padres sobre subconjuntos de estudiantes.
- El descendiente puede quedar inválido, por lo que después se aplicará reparación.

No se usa una codificación directa sobre `xijt`, ya que sería mucho más grande y difícil de manejar genéticamente que una codificación basada en `student_to_placement`.

---

## 7. Mutación

Mutaciones locales posibles:

- mover un estudiante a otra plaza,
- intercambiar plazas entre estudiantes,
- modificar localmente bloques de dependencias.

Toda mutación irá seguida de **repair**.

---

## 8. Repair

El operador de reparación es una pieza central del algoritmo y tendrá dos fases:

### 1. Repair estudiante → plaza
Debe garantizar:

- una plaza por estudiante,
- una plaza ocupada a lo sumo por un estudiante,
- respeto de mínimos y máximos por empresa,
- cumplimiento de dependencias.

### 2. Repair plaza → profesor
Debe garantizar:

- que toda plaza ocupada tenga profesor,
- que ningún profesor exceda su capacidad.

Se reutilizará, en lo posible, la lógica ya presente en `random_feasible_fixing`.

---

## 9. Reemplazo

- Esquema elitista tipo **NSGA-III**:
  - unir padres e hijos,
  - construir frentes no dominados,
  - rellenar la nueva población priorizando los mejores frentes,
  - si el último frente no cabe completo, seleccionar usando **reference points** para mantener diversidad.

A diferencia de NSGA-II, aquí la diversidad no se gestiona con crowding distance, sino con direcciones de referencia.

---

## 10. Pareto global

Además de la población interna, se mantendrá un conjunto externo de soluciones no dominadas usando:

- `update_pareto_set`
- `prune_pareto_set_by_size`

Esto permitirá conservar las mejores soluciones de toda la ejecución, independientemente de la población de cada generación.

---

## 11. Criterio de parada

Inicialmente:

- límite de tiempo, por ejemplo `60s`

Opcionalmente, más adelante:

- número máximo de generaciones,
- estancamiento del Pareto global.

Esto mantiene comparabilidad con la baseline actual.

---

## 12. Parámetros iniciales

Configuración inicial propuesta:

- población: 50
- descendencia: 50
- probabilidad de cruce: 0.8
- probabilidad de mutación: 0.2
- generaciones máximas: 100
- tiempo máximo: 60 s
- tamaño máximo del Pareto externo: 50
- seed: 1234

En NSGA-III habrá que fijar además las **reference directions** para 4 objetivos.

---

## 13. Evaluación frente a baseline

Comparar con la búsqueda aleatoria actual en:

- tamaño del Pareto final,
- calidad de soluciones,
- diversidad del frente,
- mejor valor escalar auxiliar,
- tiempo de ejecución.

---

## 14. Decisiones clave

- GA multiobjetivo desde el inicio
- algoritmo base: **NSGA-III**
- cromosoma: `student_to_placement`
- profesores: reconstrucción, no codificación genética directa
- población inicial factible
- evaluación principal por 4 objetivos separados
- cruce y mutación seguidos de repair
- mantenimiento de Pareto global externo