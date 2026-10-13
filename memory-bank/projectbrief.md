# TrackFlow — Project Brief

## Descripción del Negocio (Business Description)

**TrackFlow** es una empresa de logística de última milla y gestión de almacenes fundada en 2009 en Los Ángeles, Estados Unidos. Actualmente opera en dos mercados estratégicos —Estados Unidos y España— con almacenes físicos en **Los Ángeles** y **Zaragoza**. 

### Propuesta de Valor
TrackFlow asume la responsabilidad integral de la cadena logística para marcas de e-commerce B2B. Almacena inventario, realiza el picking y packing de pedidos, coordina la distribución con transportistas de última milla y gestiona la logística inversa (devoluciones). Permite que las empresas e-commerce se concentren en la creación y venta de productos mientras TrackFlow asegura la entrega óptima al consumidor final (B2C).

---

## El Problema que Resuelve (Problem Statement)
Las marcas de e-commerce destacan por diseñar y vender productos, pero carecen de la infraestructura y el know-how para gestionar entregas globales de última milla, almacenamiento multi-sede y devoluciones. TrackFlow resuelve este problema convirtiéndose en su socio logístico de extremo a extremo.

---

## Objetivos del Proyecto (Project Objectives)

El objetivo principal del proyecto es diseñar, construir y desplegar la infraestructura tecnológica, pipelines de datos y soluciones de Inteligencia Artificial que transformen a TrackFlow en una plataforma logística moderna, unificada y altamente automatizada.

### 1. Operaciones de Almacén
- Crear una **API de inventario unificada** con stock en tiempo real por SKU en ambos almacenes.
- Construir un **pipeline de ingesta de pedidos** que parsee e ingiera automáticamente pedidos recibidos por email.
- Desplegar un **Dashboard de Operaciones** y un sistema de **alertas automáticas de bajo stock**.

### 2. Última Milla y Transportistas
- Implementar un **motor inteligente de selección de transportista** basado en destino, peso, costo y urgencia.
- Desarrollar un **endpoint unificado de tracking** que agregue datos en tiempo real de los 8 transportistas.
- Publicar un **portal de seguimiento público** para consumidores finales y un **dashboard de rendimiento logístico**.

### 3. Logística Inversa Inteligente
- Desarrollar un **motor de aprobación automática de devoluciones** con reglas configurables por cliente.
- Automatizar el flujo de recogida (aprobación → generación de etiquetas → programación con transportista).
- Crear un **sistema de inspección asistido por IA** (visión por computador / IA multimodal) para clasificar el estado de productos devueltos a partir de fotografías.

### 4. Experiencia del Cliente (CX) Automatizada
- Desplegar un **agente de IA de primera línea** capaz de resolver consultas recurrentes de tracking y devoluciones en español e inglés.
- Construir una **base de conocimiento semántica (RAG)** e integrar un **sistema unificado de tickets** con dashboard en tiempo real y **análisis de sentimiento**.

### 5. Gestión Comercial y CRM
- Integrar un **CRM unificado** y automatizar la generación y envío de **informes PDF para clientes**.
- Implementar un **dashboard de salud de clientes** con puntuación de riesgo de renovación y alertas pre-vencimiento (90 y 30 días).
- Desarrollar un **agente comercial de IA** para recomendación de servicios y propuestas de precios.

### 6. Telemetría y Plataforma Tecnológica
- Unificar la **telemetría, ingesta de eventos y logging centralizado** de ambas infraestructuras cloud.
- Construir un **pipeline de datos robusto** que alimente todos los dashboards de la compañía.
- Automatizar tareas operativas (health checks, copias de seguridad) y desplegar un **agente de documentación técnica**.

### 7. Dirección y Control Ejecutivos
- Implementar un **Dashboard Ejecutivo Global** con KPIs en tiempo real (volumen, tasa de entrega on-time, costes operativos, devoluciones y satisfacción).
- Generar **informes semanales ejecutivos automatizados** (lunes 7:00 AM) y poner a disposición un **Asistente de IA Ejecutivo** para consultas analíticas en lenguaje natural.
