## Elección de Empresa
---
En una primera lectura ya me sentí atraído por la creación de un código conectado a la vida de un paquete desde que sale de la estantería hasta que llega a la puerta del cliente, los problemas de SGAs distintos para cada almacén y la falta de automatización y seguridad en el proceso de los envíos.
En una segunda lectura con mayor profundidad, me comenzó a interesar más TrackFlow por el problema de datos, de unificación, de telemetría y el estado “patchwork” en el que se encuentra.
El reto de crear una solución para cada problema, automatizaciones y mejoras modernas para la generación de documentos, asistencia automatizada, telemetría, tracking y dashboards me terminó de convencer.


## Departamentos con problemas interesantes
---
Sentí una gran atracción por la parte que involucra toda la logística y operaciones físicas donde vi un gran problema de seguimiento, stocks, alertas y visibilidad global de ambos almacenes. La necesidad de crear un dashboard para cada departamento para tener un control en tiempo real de lo que ocurre, pudiendo saber cuál es el stock o el estado del paquete, si ha llegado o no al destinatario o si se devuelve.

En definitiva, los que más me interesaron fueron:
- Operaciones de almacén
- Última milla y gestión de transportistas
- Logística inversa

Los demás problemas me resultaron interesantes, pero no tanto como la parte logística.

## Reto de automatización o IA que más ganas tengo de construir
---
La clasificación de estado de productos devueltos por imagen es el reto que más tengo ganas de hacer. Sin embargo, no es el único. La selección inteligente de transportistas con recomendaciones explicables y un tracking en tiempo real que extrae datos de 8 APIs de transportista distintas también son retos que me gustan.


## Mi idea de agente de IA
---
El agente de IA requerirá de la información del inventario de los almacenes para poder controlar el stock de forma eficiente. Esto permitiría al agente de IA enviar alertas reales de stock bajo, avisando a los operarios y los clientes correctamente. Para esto el agente de IA requerirá también información de los emails de los clientes para poder enviar dichas alertas de stock bajo.
Además de los emails, necesitaría la información de entrega a los clientes (dirección de entrega, peso del paquete, urgencia), junto con la de los transportistas que recibirá a través de las APIs de éstos, para poder realizar estimaciones y poder proporcionar una sugerencia de qué transportista sería el más adecuado para realizar el envío.
También recibirá varias imagenes mediante fotografías para realizar un analisis mediante imagen del estado visual de un paquete para proporcionar una clasificación adecuada para los paquetes, actualizando la información para que los operarios puedan trabajar adecuadamente con ella.

Como el resultado de una investigación propia, sugiriría el uso de Claude Code de Anthropic, ya que puede ofrecer los servicios de IA que se necesita para solventar los retos de automatización o IA.
- Tiene MCP para el uso de herramientas externas.
- Puede comunicarse con APIs, lo cual se vuelve crucial para conectar con las APIs de transportistas.
- Puede crear análisis y realizar una explicación.
- Puede trabajar con imágenes para generar un estado del paquete.
- Puede hacer tracking en tiempo real.
- Tiene una ventana de contexto amplia.

