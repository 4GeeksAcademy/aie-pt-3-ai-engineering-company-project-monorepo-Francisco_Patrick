# Quickstart Validation Guide: AUTH-03 Password Reset

## Requirements & Prerequisites
- Node.js ES2020+, TypeScript 5.9+
- Backend API server corriendo bajo `services/api`
- Frontend Backoffice corriendo bajo `uis/backoffice`
- Variable de entorno `RESEND_API_KEY` o mockup local habilitado

## Runnable Validation Scenarios

### Scenario 1: Solicitud de restablecimiento anti-enumeración
1. Navegar a `http://localhost:3000/forgot-password`.
2. Introducir `nonexistent@trackflow.com` y pulsar "Enviar".
3. **Resultado esperado**: La UI deshabilita el botón, devuelve `200 OK` y muestra: `"Si esa dirección está registrada, recibirás un enlace en breve"`.
4. Repetir con un usuario registrado `user@trackflow.com`.
5. **Resultado esperado**: UI muestra el mismo mensaje y el servicio emite un correo con el token.

### Scenario 2: Restablecimiento exitoso y de uso único
1. Copiar la URL del correo o simulación: `http://localhost:3000/reset-password?token=<token_válido>`.
2. Introducir una nueva contraseña coincidente.
3. **Resultado esperado**: Redirección automática a `/login` con mensaje de éxito.
4. Navegar inmediatamente de nuevo a la misma URL `http://localhost:3000/reset-password?token=<token_válido>`.
5. **Resultado esperado**: La API rechaza la solicitud con `400 Bad Request` indicando token inválido/usado.

### Scenario 3: Cambio de contraseña autenticado
1. Iniciar sesión en el backoffice y navegar a `/account/change-password`.
2. Introducir contraseña actual incorrecta y nueva contraseña.
3. **Resultado esperado**: Error 400 informando que la contraseña actual no coincide.
4. Corregir la contraseña actual y volver a enviar.
5. **Resultado esperado**: Mensaje de éxito informando que la contraseña ha sido actualizada.
