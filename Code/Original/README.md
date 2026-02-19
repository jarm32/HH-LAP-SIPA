# SIPA – Ejecución del modelo ILP

Esta carpeta contiene lo esencial para la implementación original del modelo SIPA basado en ILP, junto con una instancia de ejemplo.

## Contenido

- **`problem_instance_600_0.txt`**  
  Instancia del problema (estudiantes, prácticas, empresas, competencias, restricciones y distancias).

- **`simple_sipa.py`**  
  Modelo del problema. Lee la instancia y construye todas las estructuras necesarias (utilidades, dependencias, límites por empresa, etc.).

- **`simple_sipa_milp.py`**  
  Implementación del modelo ILP. Define variables, restricciones y función objetivo, y resuelve el problema con un solver.

- **`prueba_modelo_simple.py`**  
  Script de prueba que actúa como lanzadera técnica: carga los datos, construye el modelo y ejecuta el ILP.

- **`tools/`**  
  Carpeta que contiene código auxiliar utilizado por los componentes principales del modelo. Incluye funciones de apoyo para el preprocesado de datos, normalización, cálculo de utilidades u otras operaciones comunes reutilizadas por el modelo del problema y los algoritmos de resolución.

- **`instance_creator.py`**
  Generador de instancias sintéticas del problema SIPA. Crea automáticamente estudiantes, empresas, prácticas, competencias, dependencias y matrices de distancias, validando cada instancia mediante el solver ILP antes de guardarla.

- **`create_instance.py`**
  Script alternativo de generación de instancias sintéticas, orientado a la creación masiva de problemas con distintos tamaños y configuraciones, incluyendo cálculo automático de matrices de distancia.

- **`multiple_instance_creator.sh`**
  Script de automatización para la generación por lotes de múltiples instancias con distintos parámetros (surplus, dependencias, competencias), ejecutando repetidamente el generador principal.

## Requisitos

- Python **3.9** o **3.10**
- Dependencias del proyecto instaladas (incluyendo **OR-Tools**)

## Cómo ejecutar el modelo

Desde esta carpeta, ejecutar:

`python prueba_modelo_simple.py`

Este script:

- Carga la instancia del problema desde el archivo .txt.

- Construye el modelo SIPA.

- Resuelve el modelo mediante ILP.

- Verifica que los resultados obtenidos son correctos.

Si la ejecución termina sin errores, el modelo ILP se ha ejecutado correctamente para la instancia proporcionada.

Flujo general
Instancia (.txt)
      ↓
Modelo del problema (simple_sipa.py)
      ↓
Resolución ILP (simple_sipa_milp.py)