import os
from typing import Optional

def mask_email(email: str) -> str:
    """Mask email address PII for safe log output."""
    if not email or "@" not in email:
        return "***"
    parts = email.split("@", 1)
    name = parts[0]
    domain = parts[1]
    masked_name = name[0] + "***" + name[-1] if len(name) > 2 else name[0] + "***"
    return f"{masked_name}@{domain}"

class EmailService:
    def __init__(self):
        self.api_key = os.environ.get("RESEND_API_KEY")

    def send_password_reset_email(self, to_email: str, reset_link: str) -> bool:
        masked_to = mask_email(to_email)
        if not self.api_key:
            # Fallback for dev / mock environment when API Key is missing (omitting reset link token for security)
            print(f"[EmailService Mock] Password reset email dispatch requested for user {masked_to} (reset link token omitted)")
            return True

        # In production with RESEND_API_KEY, use Resend API via urllib
        try:
            import urllib.request
            import json

            req = urllib.request.Request(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                data=json.dumps({
                    "from": "TrackFlow Security <security@trackflow.com>",
                    "to": [to_email],
                    "subject": "Restablecimiento de Contraseña - TrackFlow",
                    "html": f"""
                    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #1e293b;">Restablecimiento de Contraseña</h2>
                        <p style="color: #475569;">Hemos recibido una solicitud para restablecer la contraseña de tu cuenta en TrackFlow.</p>
                        <p style="color: #475569;">Haz clic en el siguiente botón para establecer una nueva contraseña. Este enlace expira en 30 minutos:</p>
                        <div style="margin: 30px 0;">
                            <a href="{reset_link}" style="background-color: #2563eb; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Restablecer mi Contraseña</a>
                        </div>
                        <p style="color: #94a3b8; font-size: 12px;">Si no solicitaste este cambio, puedes ignorar este correo de forma segura.</p>
                    </div>
                    """
                }).encode("utf-8"),
                method="POST"
            )
            with urllib.request.urlopen(req) as resp:
                return resp.status in (200, 201)
        except Exception:
            print(f"[EmailService Error] Failed to dispatch password reset email to {masked_to}")
            return False
