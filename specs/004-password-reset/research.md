# Phase 0: Research & Decision Log

## Technical Decisions

### Decision 1: Token Generation and Invalidation Mechanism
- **Decision**: Usar tokens aleatorios criptográficamente seguros (`crypto.randomBytes(32).toString('hex')`) almacenados en memoria/tabla persistente `password_reset_tokens` con hash SHA-256 en lugar de JWTs puros.
- **Rationale**: Los JWTs puros sin estado no pueden invalidarse inmediatamente antes de su expiración salvo que se mantenga una lista negra. Almacenar el hash del token en servidor permite invalidarlo al instante tras su primer uso, cumpliendo con el requisito estricto de seguridad.
- **Alternatives Considered**: 
  - *JWT con claim `exp`*: Rechazado porque no permite invalidación inmediata post-reset sin persistencia de estado.
  - *Invalidación por `password_changed_at`*: Menos granular si se solicitan múltiples tokens antes de consumir uno.

### Decision 2: Servicio de Correo Transaccional e Integración
- **Decision**: Utilizar `Resend` vía SDK de TypeScript con fallback a SMTP o simulación en entorno de desarrollo.
- **Rationale**: Es el proveedor especificado en el requerimiento (`password-reset.md`). Las API Keys se manejan estrictamente desde la variable de entorno `RESEND_API_KEY`.
- **Alternatives Considered**:
  - *Nodemailer / SMTP directo*: Mayor complejidad de configuración y soporte de plantillas HTML.

### Decision 3: Anti-Enumeración y Rate Limiting
- **Decision**: Límite de 5 peticiones por hora por dirección de email para `POST /auth/forgot-password`. Responder siempre con `200 OK` y payload idéntico `{ message: "If that email is registered, you will receive a reset link shortly" }`.
- **Rationale**: Garantiza la protección contra enumeración de usuarios y previene ataques de denegación de servicio (DoS) o spam de correos.
- **Alternatives Considered**:
  - *Devolver 404 cuando el email no existe*: Rechazado explícitamente por el requisito de seguridad anti-enumeración.
