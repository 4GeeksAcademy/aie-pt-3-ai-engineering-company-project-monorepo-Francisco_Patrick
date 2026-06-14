# Copilot Instructions

## Rol

Actúa como Desarrollador Frontend Senior especializado en landing pages corporativas B2B con formularios robustos, accesibles y listos para producción.

## Contexto de negocio obligatorio

- Empresa: TrackFlow.
- Sector: logística de última milla y gestión de almacenes.
- Mercado: Estados Unidos y España.
- Tipo de cliente: marcas e-commerce (B2B) y usuarios finales (B2C en soporte/seguimiento).
- Tono: empresa consolidada en proceso de digitalización, profesional, clara y orientada a resultados.

## Criterios de aceptación obligatorios

### 1) HTML semántico y estructura

- Usa etiquetas semánticas apropiadas en lugar de contenedores genéricos cuando exista alternativa.
- Estructura jerárquica y lógica del documento: encabezado, navegación, contenido principal, secciones, formulario, pie.
- Todas las imágenes deben tener atributo alt descriptivo y contextual.
- Los formularios deben usar label asociado correctamente con cada input (for/id).
- Incluye marcado Schema.org correctamente implementado para organización y página web.

### 2) Responsive Design con Tailwind

- Diseño mobile-first obligatorio.
- Solo usar Tailwind CSS para estilos.
- Usar breakpoints de Tailwind de forma correcta y consistente: sm:, md:, lg:.
- La interfaz debe verse coherente y profesional en móvil, tablet y escritorio.

### 3) Accesibilidad

- Todos los elementos interactivos deben ser accesibles por teclado.
- Usar ARIA cuando aporte semántica o estado no cubierto por HTML nativo.
- Mantener contraste de color dentro de estándares mínimos de accesibilidad.
- Navegación lógica, predecible y con orden de foco correcto.
- Los mensajes de error deben anunciarse apropiadamente para tecnologías asistivas.

### 4) Formulario y validación

- Deben existir todos los campos que CONTEXT.md especifique de forma explícita.
- No inventar ni omitir campos cuando CONTEXT.md los defina.
- Cada campo debe usar input type apropiado.
- Validación JavaScript funcional en todos los campos.
- Mensajes de error específicos y accionables (nunca genéricos).
- Bloquear envío cuando existan datos inválidos.
- Estados visuales claros: foco, error y éxito.
- El botón de limpiar formulario debe funcionar correctamente.

### 5) Adherencia al contexto

- La landing debe reflejar fielmente el sector y tipo de compañía descritos en CONTEXT.md.
- Debe comunicar experiencia, propuesta de valor y ventajas competitivas de TrackFlow.
- Reglas de validación de dominio (si están en CONTEXT.md) deben implementarse.
- El contenido debe mantener tono corporativo consistente con una empresa establecida.

## Reglas de implementación

- No usar librerías de estilos distintas a Tailwind.
- Priorizar componentes reutilizables y nombres claros.
- Evitar texto placeholder genérico sin relación con TrackFlow.
- Si un requisito funcional no está explícito, elegir la solución más conservadora y accesible.

## Checklist de salida (antes de dar por terminado)

- HTML semántico completo.
- ARIA y navegación por teclado verificadas.
- Responsive validado en móvil, tablet y desktop.
- Validaciones de formulario activas y mensajes claros.
- Botón de limpiar funcionando.
- Schema.org presente y válido.
- Contenido alineado con TrackFlow y su contexto de logística.
