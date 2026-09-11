import os
from typing import Optional

class EmailService:
    def __init__(self):
        self.api_key = os.environ.get("RESEND_API_KEY")

    def send_password_reset_email(self, to_email: str, reset_link: str) -> bool:
        if not self.api_key:
            # Fallback for dev / mock environment when API Key is missing
            print(f"[EmailService Mock] Sending Password Reset Email to {to_email}: {reset_link}")
            return True

        # In production with RESEND_API_KEY, use Resend API via urllib or resend package if installed
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
        except Exception as e:
            print(f"[EmailService Error] Failed to send email via Resend: {e}")
            return False
