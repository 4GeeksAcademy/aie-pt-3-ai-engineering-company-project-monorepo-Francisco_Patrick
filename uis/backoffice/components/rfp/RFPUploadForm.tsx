'use client';

import React, { useState, useRef } from 'react';
import type { IntakeTicketAcceptedResponseDTO, ErrorResponseDTO } from '@repo/shared-types';

/**
 * Props for the RFPUploadForm component.
 */
export interface RFPUploadFormProps {
  /** Callback invoked when a proposal PDF is successfully accepted. */
  onUploadSuccess: (ticket: IntakeTicketAcceptedResponseDTO) => void;
}

/**
 * Drag-and-drop form component for uploading customer RFP PDF proposals.
 *
 * Validates that file is a PDF <= 25MB before dispatching to `/api/v1/rfp/intake`.
 *
 * @param props - Form callbacks and configuration.
 * @returns JSX Element rendering the dropzone form.
 */
export function RFPUploadForm({ onUploadSuccess }: RFPUploadFormProps): React.ReactElement {
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>): void => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      const selected = files[0];
      if (selected) {
        processUpload(selected);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>): void => {
    const files = e.target.files;
    if (files && files.length > 0) {
      const selected = files[0];
      if (selected) {
        processUpload(selected);
      }
    }
  };

  const processUpload = async (file: File): Promise<void> => {
    setErrorMessage(null);

    // Validation 1: Must be PDF
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      setErrorMessage('Formato no válido: solo se aceptan documentos PDF (.pdf).');
      return;
    }

    // Validation 2: Maximum 25MB
    const MAX_BYTES = 25 * 1024 * 1024;
    if (file.size > MAX_BYTES) {
      setErrorMessage('El archivo excede el tamaño máximo permitido de 25MB.');
      return;
    }

    if (file.size === 0) {
      setErrorMessage('El archivo seleccionado está vacío.');
      return;
    }

    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/v1/rfp/intake`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = (await response.json()) as ErrorResponseDTO;
        throw new Error(errorData.detail || 'Error al enviar propuesta.');
      }

      const result = (await response.json()) as IntakeTicketAcceptedResponseDTO;
      onUploadSuccess(result);

      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al comunicarse con el servidor.';
      setErrorMessage(msg);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="w-full">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
          isDragging
            ? 'border-emerald-500 bg-emerald-500/5'
            : 'border-slate-700 bg-slate-900/50 hover:border-slate-600 hover:bg-slate-900'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          onChange={handleFileChange}
          className="hidden"
          disabled={isUploading}
        />

        <div className="flex flex-col items-center justify-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center text-slate-300">
            {isUploading ? (
              <span className="w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
            ) : (
              <svg
                className="w-6 h-6 text-emerald-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
            )}
          </div>

          <div>
            <p className="text-sm font-medium text-slate-200">
              {isUploading ? 'Subiendo y analizando propuesta...' : 'Arrastra un documento PDF o haz clic para seleccionarlo'}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Archivos PDF hasta 25MB (Pliegos de condiciones, solicitudes RFP, propuestas de clientes)
            </p>
          </div>
        </div>
      </div>

      {errorMessage && (
        <div className="mt-3 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
          {errorMessage}
        </div>
      )}
    </div>
  );
}
