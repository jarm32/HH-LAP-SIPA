# Diseño conceptual del GA multiobjetivo (NSGA-III)

## 1. Objetivo del algoritmo

Desarrollar un algoritmo genético multiobjetivo que genere soluciones factibles de alta calidad para el problema SIPA modificado, optimizando simultáneamente:

- ↑ `tau_sum` (satisfacción estudiantes)
- ↑ `eta_sum` (satisfacción empresas)
- ↓ `lbar_sum` (coste de supervisión)
- ↓ `sigma_sum` (desequilibrio entre profesores)

---

## 2. Representación del individuo

- Cromosoma principal:  
  `student_to_placement[i] = j`

- La asignación de profesores no se codifica directamente, sino que se reconstruye después. Así se reduce la complejidad y encaja con la representación de la solución (Solution).

---

## 3. Población inicial

- Se generan individuos con `generate_random_feasible_fixing`, asegurando factibilidad inicial.

---

## 4. Evaluación

- Evaluación principal: `evaluate_solution_multi`
- Objetivos:
  - max: `tau_sum`, `eta_sum`
  - min: `lbar_sum`, `sigma_sum`

- Evaluación escalar (`evaluate_solution_scalar`):
  - solo como apoyo para desempates, análisis o poda auxiliar, no como criterio principal.

---

## 5. Selección

Seguirá el esquema de NSGA-III:

1. Construir los frentes no dominados de la población.
2. Ir incorporando los frentes no dominados por orden, desde el mejor hasta donde permita el tamaño de la población.
3. Cuando no sea posible incorporar completo el siguiente frente, usar los puntos de referencia previamente definidos (reference points) para decidir qué soluciones entran y mantener diversidad en la población.

Los puntos de referencia se generan previamente como un conjunto de direcciones distribuidas de forma uniforme en el espacio de objetivos (en este caso, 4 dimensiones). Su número estará relacionado con el tamaño de la población, de modo que permita cubrir distintas regiones del frente de Pareto.

Cada solución se asocia al punto de referencia más cercano (normalmente tras una normalización de los objetivos). Cuando hay que seleccionar soluciones dentro de un frente incompleto, se priorizan aquellas asociadas a puntos de referencia menos representados, favoreciendo así la diversidad.

NSGA-III resulta más adecuado que NSGA-II para repartir mejor la población por el frente y evitar la pérdida de capacidad discriminatoria de la dominancia cuando se trabaja con varios objetivos.

---

## 6. Cruce

El cruce combinará asignaciones de dos padres sobre subconjuntos de estudiantes. Como el descendiente puede quedar inválido, después se aplicará reparación.

Se realizará de forma que:

1. Seleccionar aleatoriamente un subconjunto de estudiantes.
2. Para esos estudiantes, el descendiente hereda la asignación del padre A.
3. Para el resto, intenta heredar la asignación del padre B.
4. Si aparecen conflictos (plazas duplicadas, restricciones violadas, etc.), se resuelven posteriormente mediante reparación.

No se usa una codificación directa sobre `xijt`, ya que sería mucho más grande y difícil de manejar genéticamente que una codificación basada en `student_to_placement`.

---

## 7. Mutación

Mutaciones locales posibles:

- Mover un estudiante a otra plaza.
- Intercambiar plazas entre estudiantes.
- Modificar localmente bloques de dependencias.

Esquema básico de mutación:

1. Seleccionar aleatoriamente uno o varios estudiantes.
2. Aplicar uno de los operadores de mutación definidos (move, swap o modificación de dependencias).
3. Si se generan inconsistencias (plazas duplicadas, violación de restricciones, etc.), se corrigen posteriormente mediante repair.

Toda mutación irá seguida de un proceso de repair para garantizar la factibilidad de la solución.

---

## 8. Repair

El proceso de repair se aplicará tras las operaciones de cruce y mutación para transformar el descendiente en una solución factible. Tendrá dos fases:

### 1. Repair estudiante → plaza
Debe garantizar:

- Cada estudiante tiene exactamente una plaza asignada.
- Cada plaza está ocupada por, como máximo, un estudiante.
- Respeto de mínimos y máximos por empresa.
- Cumplimiento de dependencias.

### 2. Repair plaza → profesor
Debe garantizar:

- Toda plaza ocupada tenga un profesor asignado.
- Ningún profesor exceda su capacidad.

Su implementación se basará en la lógica utilizada en `generate_random_feasible_fixing`, adaptándola al contexto de reparación de soluciones parciales.

---

## 9. Reemplazo

- Esquema elitista tipo `NSGA-III`:
  1. Unir padres e hijos.
  2. Construir frentes no dominados.
  3. Rellenar la nueva población añadiendo frentes completos por orden.
  4. Si el último frente no cabe completo, seleccionar usando reference points para mantener diversidad.

A diferencia de NSGA-II, aquí la diversidad no se gestiona con crowding distance, sino con direcciones de referencia.

---

## 10. Pareto global

El algoritmo trabajará con dos niveles de soluciones:

- Una población interna, de tamaño fijo, que evoluciona mediante selección, cruce, mutación y reemplazo (NSGA-III). Se utiliza para guiar la evolución del algoritmo
- Un Pareto global externo, donde se almacenan todas las soluciones no dominadas encontradas durante la ejecución (memoria). Tras evaluar cada nueva solución generada, esta se incorporará al Pareto global mediante `update_pareto_set`.

---

## 11. Criterio de parada

Inicialmente, el criterio de parada será por límite de tiempo (por ejemplo 60s). Adicionalmente, podrían considerarse otros criterios como un número máximo de generaciones o el estancamiento del Pareto global.

---

## 12. Parámetros iniciales

Configuración inicial propuesta:

- Tamaño de población: 50
- Tamaño de descendencia: 50
- Probabilidad de cruce: 0.8
- Probabilidad de mutación: 0.2
- Tiempo máximo de ejecución: 60s

Además, será necesario definir un conjunto de puntos de referencia, cuya cantidad y distribución estarán relacionadas con el tamaño de la población y el número de objetivos (4 en este caso).

---

## 13. Evaluación frente a baseline

Comparar con la búsqueda aleatoria actual en:

- Tamaño del Pareto final.
- Calidad de soluciones.
- Diversidad del frente.
- Mejor valor escalar auxiliar.
- Tiempo de ejecución.