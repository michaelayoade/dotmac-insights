'use client';

import { useState, useRef, useCallback } from 'react';
import { Upload, Loader2, X, File } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';

interface AttachmentUploadProps {
  onUpload: (file: File, options?: { description?: string }) => Promise<void>;
  disabled?: boolean;
  accept?: string;
  maxSize?: number; // in MB
}

export function AttachmentUpload({
  onUpload,
  disabled = false,
  accept = '.pdf,.png,.jpg,.jpeg,.gif,.doc,.docx,.xls,.xlsx,.csv,.txt,.zip',
  maxSize = 10,
}: AttachmentUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = useCallback(
    (file: File): string | null => {
      const maxBytes = maxSize * 1024 * 1024;
      if (file.size > maxBytes) {
        return `File too large. Maximum size is ${maxSize}MB`;
      }

      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      const allowedExts = accept.split(',').map((e) => e.trim().toLowerCase());
      if (!allowedExts.some((allowed) => ext === allowed || allowed === '*')) {
        return `File type not allowed. Allowed: ${accept}`;
      }

      return null;
    },
    [accept, maxSize]
  );

  const handleFile = useCallback(
    (file: File) => {
      setError(null);
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }
      setSelectedFile(file);
    },
    [validateFile]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled) return;

      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [disabled, handleFile]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile || isUploading) return;

    setIsUploading(true);
    setError(null);

    try {
      await onUpload(selectedFile, { description: description.trim() || undefined });
      setSelectedFile(null);
      setDescription('');
      if (inputRef.current) inputRef.current.value = '';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  const handleCancel = () => {
    setSelectedFile(null);
    setDescription('');
    setError(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="space-y-3">
      {!selectedFile ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled) setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => !disabled && inputRef.current?.click()}
          className={cn(
            'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
            isDragging
              ? 'border-teal-electric bg-teal-electric/5'
              : 'border-slate-border hover:border-slate-border/70',
            disabled && 'opacity-50 cursor-not-allowed'
          )}
        >
          <Upload className="w-8 h-8 mx-auto mb-2 text-slate-muted" />
          <p className="text-sm text-foreground font-medium">
            Drop a file here or click to upload
          </p>
          <p className="text-xs text-slate-muted mt-1">
            Max {maxSize}MB - {accept}
          </p>
          <input
            ref={inputRef}
            type="file"
            accept={accept}
            onChange={handleChange}
            disabled={disabled}
            className="hidden"
          />
        </div>
      ) : (
        <div className="bg-slate-elevated rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-slate-card flex items-center justify-center">
              <File className="w-5 h-5 text-teal-electric" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-foreground font-medium text-sm truncate">
                {selectedFile.name}
              </p>
              <p className="text-xs text-slate-muted">
                {(selectedFile.size / 1024).toFixed(1)} KB
              </p>
            </div>
            <button
              onClick={handleCancel}
              disabled={isUploading}
              className="p-1.5 text-slate-muted hover:text-foreground transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Add a description (optional)"
            disabled={isUploading}
            className="w-full px-3 py-2 bg-slate-card border border-slate-border rounded-md text-sm text-foreground placeholder-slate-muted focus:border-teal-electric focus:ring-1 focus:ring-teal-electric outline-none"
          />

          <div className="flex items-center justify-end gap-2">
            <Button
              onClick={handleCancel}
              disabled={isUploading}
              className="px-3 py-1.5 rounded-md border border-slate-border text-slate-muted text-sm hover:text-foreground hover:border-slate-border/70"
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpload}
              disabled={isUploading}
              className="px-4 py-1.5 rounded-md bg-teal-electric text-slate-950 text-sm font-medium hover:bg-teal-electric/90 disabled:opacity-50 inline-flex items-center gap-2"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  Upload
                </>
              )}
            </Button>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}

export default AttachmentUpload;
