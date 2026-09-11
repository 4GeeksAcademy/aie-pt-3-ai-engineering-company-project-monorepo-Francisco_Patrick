# Feature Specification: Recuperación y Cambio de Contraseña (AUTH-03)

**Feature Branch**: `004-password-reset`

**Created**: 2026-09-11

**Status**: Draft

**Input**: User description from password-reset.md (AUTH-03 — Recuperación y cambio de contraseña)

## Clarifications

### Session 2026-09-11

- Q: ¿Cuál debe ser la ventana exacta de expiración por defecto para los tokens de restablecimiento de contraseña? → A: 30 minutos (Equilibrio idóneo entre seguridad y usabilidad en e-commerce/B2B).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Solicitud de Restablecimiento de Contraseña (Priority: P1)

Como usuario registrado que ha olvidado su contraseña, quiero solicitar un enlace de restablecimiento introduciendo mi correo electrónico para poder recuperar el acceso a mi cuenta de forma segura sin revelar si la dirección existe en el sistema.

**Why this priority**: Es la puerta de entrada principal para usuarios bloqueados sin acceso a su cuenta; además establece las bases de seguridad anti-enumeración de usuarios.

**Independent Test**: Puede probarse enviando una solicitud desde la pantalla `/forgot-password` tanto con un correo registrado como con uno no registrado y verificando que en ambos casos se muestra la misma pantalla de confirmación y se envía el correo correspondiente únicamente para la cuenta existente.

**Acceptance Scenarios**:

1. **Given** un usuario en la página `/forgot-password`, **When** introduce un correo válido registrado y envía el formulario, **Then** el formulario se deshabilita para evitar envíos duplicados, la interfaz muestra el mensaje genérico de confirmación ("Si esa dirección está registrada, recibirás un enlace en breve") y el sistema envía un correo transaccional en HTML con un enlace único de restablecimiento.
2. **Given** un usuario en la página `/forgot-password`, **When** introduce un correo no registrado y envía el formulario, **Then** la interfaz devuelve una respuesta exitosa idéntica mostrando la confirmación sin revelar que el usuario no existe y sin enviar ningún correo.

---

### User Story 2 - Restablecimiento de Contraseña desde Enlace (Priority: P2)

Como usuario que ha recibido un correo de restablecimiento, quiero abrir el enlace con token seguro y definir una nueva contraseña para actualizar mis credenciales e iniciar sesión inmediatamente.

**Why this priority**: Completa el flujo de recuperación de cuenta y permite volver a autenticarse.

**Independent Test**: Puede probarse navegando a `/reset-password?token=<token_válido>`, enviando una nueva contraseña válida con confirmación idéntica y comprobando la redirección automática a `/login` con mensaje de éxito, así como la actualización efectiva de las credenciales.

**Acceptance Scenarios**:

1. **Given** un usuario con un token de restablecimiento válido y no expirado en el query string de `/reset-password`, **When** introduce una nueva contraseña y su confirmación coincidente y presiona enviar, **Then** la contraseña se actualiza en el sistema, el token queda invalidado de forma permanente y el usuario es redirigido a `/login` con un mensaje indicando que el cambio fue exitoso.
2. **Given** un usuario intentando restablecer contraseña con un token expirado, ya utilizado o alterado, **When** envía el formulario en `/reset-password`, **Then** el sistema rechaza la solicitud con un mensaje de error claro y proporciona un enlace directo para volver a solicitar un nuevo token en `/forgot-password`.

---

### User Story 3 - Cambio de Contraseña Autenticado (Priority: P3)

Como usuario con sesión activa en la plataforma, quiero cambiar mi contraseña actual por una nueva dentro de mi panel de cuenta para mantener la seguridad de mi perfil.

**Why this priority**: Permite el mantenimiento proactivo de la seguridad por parte de usuarios ya conectados.

**Independent Test**: Puede probarse desde `/account/change-password` enviando la contraseña actual correcta junto a la nueva contraseña y verificando que la actualización es aceptada, o enviando una contraseña actual errónea y comprobando la respuesta de rechazo.

**Acceptance Scenarios**:

1. **Given** un usuario autenticado en la página `/account/change-password`, **When** introduce su contraseña actual correcta y una nueva contraseña coincidente con su confirmación, **Then** la API valida la contraseña actual, actualiza la credencial y muestra un mensaje de confirmación de éxito.
2. **Given** un usuario autenticado en `/account/change-password`, **When** introduce una contraseña actual incorrecta o contraseñas nuevas que no coinciden entre sí, **Then** el formulario bloquea la petición en el cliente (si no coinciden) o la API devuelve una respuesta de error indicando que la contraseña actual no es válida.

---

### Edge Cases

- ¿Qué ocurre si un usuario solicita múltiples tokens de restablecimiento consecutivos? El token previo debe ser invalidado o reemplazado por el más reciente, y las peticiones están sujetas a un límite de frecuencia (rate limit) por dirección de correo por hora para prevenir abusos.
- ¿Cómo se comporta el sistema si el token JWT o aleatorio expira justo mientras el usuario rellena el formulario de `/reset-password`? Al enviar, la API rechaza el cambio, mantiene la contraseña anterior intacta y muestra una alerta con enlace hacia `/forgot-password`.
- ¿Qué ocurre si la API key del servicio de correo transaccional no está configurada o falla la entrega del email? El sistema debe registrar el evento de auditoría de fallo, manejar la excepción limpiamente sin revelar detalles sensibles de la infraestructura al usuario y retornar la confirmación genérica en la UI.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El sistema DEBE proporcionar el endpoint `POST /auth/forgot-password` que acepte una dirección de correo electrónico y devuelva siempre una respuesta HTTP exitosa (200 OK) sin revelar la existencia previa del correo en la plataforma.
- **FR-002**: El sistema DEBE generar un token de restablecimiento seguro firmado con un tiempo de vida exacto de 30 minutos por defecto e invalidación tras su primer uso, enviando un correo transaccional formateado en HTML con el enlace de restablecimiento únicamente cuando el usuario exista.
- **FR-003**: El sistema DEBE proporcionar el endpoint `POST /auth/reset-password` que reciba el token y la nueva contraseña, validando la firma, tiempo de expiración y estado de no reutilización antes de actualizar el hash de la contraseña e invalidar el token de forma permanente.
- **FR-004**: El sistema DEBE proporcionar el endpoint autenticado `POST /auth/change-password` que requiera token de sesión válido, verifique la contraseña actual del usuario y aplique la nueva contraseña tras comprobar que la actual es correcta.
- **FR-005**: La interfaz frontend (`uis/backoffice/`) DEBE incluir la vista `/forgot-password` que deshabilite el formulario tras el envío y muestre siempre un mensaje genérico de confirmación anti-enumeración.
- **FR-006**: La interfaz frontend DEBE incluir la vista `/reset-password` que extraiga el token del query string URL, valide la coincidencia de contraseñas y redirija a `/login` tras un restablecimiento exitoso o muestre error con enlace a `/forgot-password` si el token es inválido/expirado.
- **FR-007**: La interfaz frontend DEBE incluir la vista `/account/change-password` para usuarios autenticados con validación en cliente de coincidencia de contraseñas.
- **FR-008**: La pantalla de acceso `/login` DEBE disponer de un enlace visible y accesible hacia la página `/forgot-password`.
- **FR-009**: El sistema DEBE almacenar todas las credenciales y claves de servicios de correo en variables de entorno sin exponer secretos en el código fuente.
- **FR-010**: El sistema DEBE implementar limitación de tasa (rate limiting) para peticiones de restablecimiento y registrar eventos de auditoría (timestamp, IP, resultado) para cada intento de cambio o recuperación de contraseña.

### Key Entities *(include if feature involves data)*

- **Usuario (User)**: Representa la cuenta del usuario en la plataforma. Atributos relevantes: identificador único, correo electrónico, hash de la contraseña, fecha de último cambio de contraseña.
- **Token de Restablecimiento (Password Reset Token)**: Registro o reivindicación de autorización temporal para restablecer la clave. Atributos: identificador o hash del token, ID de usuario asociado, fecha de emisión, fecha de expiración (configurada a 30 minutos por defecto), estado de utilización (usado/invalidado).
- **Registro de Auditoría de Seguridad (Security Audit Log)**: Evento persistido para trazabilidad de la seguridad de credenciales. Atributos: ID de evento, tipo de acción (`forgot_password_request`, `password_reset_success`, `password_change_success`), timestamp, dirección IP de origen, estado del resultado.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: El 100% de las solicitudes al endpoint `/auth/forgot-password` responden con código 200 OK y tiempo de respuesta inferior a 1.5 segundos independientemente de si el correo está registrado o no.
- **SC-002**: Ningún token de restablecimiento puede ser utilizado más de 1 vez ni tras haber superado su ventana de expiración exacta de 30 minutos (100% de rechazo con código 400 en tokens reutilizados o expirados).
- **SC-003**: Los usuarios que completan el proceso de restablecimiento reciben el correo transaccional en menos de 60 segundos y pueden iniciar sesión con su nueva contraseña al primer intento en más del 95% de los casos.
- **SC-004**: El 0% de las API keys o secretos de correo se exponen en repositorios o código fuente cliente/servidor.

## Assumptions

- Se asume el uso de un servicio de correo transaccional (como Resend) cuyo cliente e integración se configura mediante variables de entorno en backend (`services/api`).
- Se asume que las contraseñas se almacenan mediante algoritmos de hashing seguros y unidireccionales (ej. bcrypt / argon2) previamente establecidos en la plataforma.
- Se asume que las vistas de frontend se integran dentro de la estructura existente de `./uis/backoffice` utilizando componentes y estilos móviles de Tailwind CSS alineados con el sistema de diseño.
