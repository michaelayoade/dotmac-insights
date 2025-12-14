'use client';

import { useCallback, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { Upload, FileText, X, AlertTriangle } from 'lucide-react';

interface FileUploadProps {
  accept?: string;
  maxSizeMB?: number;
  onFileSelect: (file: File) => void;
  onFileRemove: () => void;
  selectedFile: File | null;
  error?: string;
  disabled?: boolean;
}

export function FileUpload({
  accept = '.csv,.ofx,.qfx',
  maxSizeMB = 10,
  onFileSelect,
  onFileRemove,
  selectedFile,
  error,
  disabled = false,
}: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  const maxSizeBytes = maxSizeMB * 1024 * 1024;

  const handleFile = useCallback(
    (file: File) => {
      // Validate file type
      const validExtensions = accept.split(',').map((ext) => ext.trim().toLowerCase());
      const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();

      if (!validExtensions.includes(fileExtension)) {
        return;
      }

      // Validate file size
      if (file.size > maxSizeBytes) {
        return;
      }

      onFileSelect(file);
    },
    [accept, maxSizeBytes, onFileSelect]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      if (disabled) return;

      const file = e.dataTransfer.files[0];
      if (file) {
        handleFile(file);
      }
    },
    [disabled, handleFile]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      e.stopPropagation();
      if (!disabled) setIsDragging(true);
    },
    [disabled]
  );

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile]
  );

  const handleClick = useCallback(() => {
    if (!disabled && !selectedFile) {
      inputRef.current?.click();
    }
  }, [disabled, selectedFile]);

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    if (ext === 'csv') return 'CSV';
    if (ext === 'ofx' || ext === 'qfx') return 'OFX';
    return 'FILE';
  };

  if (selectedFile) {
    return (
      <div className="space-y-2">
        <div className="bg-slate-card border border-slate-border rounded-xl p-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-lg bg-teal-electric/10 border border-teal-electric/30 flex items-center justify-center">
              <span className="text-teal-electric text-xs font-mono font-bold">{getFileIcon(selectedFile.name)}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white font-medium truncate">{selectedFile.name}</p>
              <p className="text-slate-muted text-sm">{formatFileSize(selectedFile.size)}</p>
            </div>
            <button
              type="button"
              onClick={onFileRemove}
              className="p-2 text-slate-muted hover:text-coral-alert hover:bg-coral-alert/10 rounded-lg transition-colors"
              aria-label="Remove file"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {error && (
          <div className="flex items-center gap-2 text-coral-alert text-sm">
            <AlertTriangle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div
        onClick={handleClick}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={cn(
          'relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors',
          isDragging
            ? 'border-teal-electric bg-teal-electric/5'
            : 'border-slate-border hover:border-slate-muted',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleInputChange}
          className="hidden"
          disabled={disabled}
        />

        <div className="flex flex-col items-center gap-3">
          <div
            className={cn(
              'w-14 h-14 rounded-full flex items-center justify-center',
              isDragging ? 'bg-teal-electric/20' : 'bg-slate-elevated'
            )}
          >
            <Upload className={cn('w-6 h-6', isDragging ? 'text-teal-electric' : 'text-slate-muted')} />
          </div>

          <div className="space-y-1">
            <p className="text-white font-medium">
              {isDragging ? 'Drop file here' : 'Drop file here or click to browse'}
            </p>
            <p className="text-slate-muted text-sm">
              Supports {accept.replace(/\./g, '').toUpperCase()} files up to {maxSizeMB}MB
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-coral-alert text-sm">
          <AlertTriangle className="w-4 h-4" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}

export default FileUpload;
