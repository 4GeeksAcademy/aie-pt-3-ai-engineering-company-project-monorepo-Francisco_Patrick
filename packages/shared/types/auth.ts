import type { BaseEntity } from "./index";

export interface PasswordResetToken extends BaseEntity {
  userId: string;
  tokenHash: string;
  expiresAt: string;
  usedAt?: string | null;
}

export type AuditEventType =
  | "forgot_password_request"
  | "password_reset_success"
  | "password_reset_failed"
  | "password_change_success"
  | "password_change_failed";

export interface SecurityAuditLog extends BaseEntity {
  eventType: AuditEventType;
  userId?: string | null;
  ipAddress: string;
  details?: string | null;
}

export interface ForgotPasswordRequest {
  email: string;
}

export interface ForgotPasswordResponse {
  message: string;
}

export interface ResetPasswordRequest {
  token: string;
  new_password: string;
}

export interface ResetPasswordResponse {
  message: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

export interface ChangePasswordResponse {
  message: string;
}
