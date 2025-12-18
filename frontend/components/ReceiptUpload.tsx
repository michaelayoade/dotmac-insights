'use client';

import { useState, useRef, useCallback } from 'react';
import Image from 'next/image';
import {
  Upload,
  X,
  Image as ImageIcon,
  FileText,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Trash2,
  ZoomIn,
  Download,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { documentsApi, DocumentAttachment } from '@/lib/api';

interface ReceiptUploadProps {
  doctype: string;
  docId?: number;
  existingAttachments?: DocumentAttachment[];
  onUploadComplete?: (attachment: DocumentAttachment) => void;
  onDelete?: (attachmentId: number) => void;
  maxFiles?: number;
  maxSizeMB?: number;
  acceptedTypes?: string[];
  disabled?: boolean;
  className?: string;
}

const DEFAULT_ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf'];
const DEFAULT_MAX_SIZE_MB = 10;

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(fileType?: string) {
  if (fileType?.startsWith('image/')) return ImageIcon;
  return FileText;
}

interface PendingFile {
  id: string;
  file: File;
  preview?: string;
  progress: 'pending' | 'uploading' | 'success' | 'error';
  error?: string;
}

export default function ReceiptUpload({
  doctype,
  docId,
  existingAttachments = [],
  onUploadComplete,
  onDelete,
  maxFiles = 5,
  maxSizeMB = DEFAULT_MAX_SIZE_MB,
  acceptedTypes = DEFAULT_ACCEPTED_TYPES,
  disabled = false,
  className,
}: ReceiptUploadProps) {
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const totalFiles = existingAttachments.length + pendingFiles.length;
  const canAddMore = totalFiles < maxFiles;

  const validateFile = useCallback((file: File): string | null => {
    if (!acceptedTypes.includes(file.type)) {
      return `File type not supported. Accepted: ${acceptedTypes.map(t => t.split('/')[1]).join(', ')}`;
    }
    if (file.size > maxSizeMB * 1024 * 1024) {
      return `File too large. Maximum size: ${maxSizeMB}MB`;
    }
    return null;
  }, [acceptedTypes, maxSizeMB]);

  const createPreview = useCallback((file: File): Promise<string | undefined> => {
    return new Promise((resolve) => {
      if (file.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target?.result as string);
        reader.onerror = () => resolve(undefined);
        reader.readAsDataURL(file);
      } else {
        resolve(undefined);
      }
    });
  }, []);

  const uploadFile = useCallback(async (id: string, file: File) => {
    if (!docId) return;

    setPendingFiles((prev) =>
      prev.map((p) => (p.id === id ? { ...p, progress: 'uploading' } : p))
    );

    try {
      const result = await documentsApi.uploadAttachment(doctype, docId, file, {
        attachment_type: 'receipt',
        is_primary: existingAttachments.length === 0,
      });

      setPendingFiles((prev) =>
        prev.map((p) => (p.id === id ? { ...p, progress: 'success' } : p))
      );

      // Notify parent and remove from pending after a delay
      if (onUploadComplete) {
        const attachment: DocumentAttachment = {
          id: result.id,
          doctype,
          document_id: docId,
          file_name: result.file_name,
          file_path: '',
          file_size: result.file_size,
          is_primary: existingAttachments.length === 0,
          attachment_type: 'receipt',
        };
        onUploadComplete(attachment);
      }

      // Remove from pending after showing success
      setTimeout(() => {
        setPendingFiles((prev) => prev.filter((p) => p.id !== id));
      }, 1500);
    } catch (err) {
      setPendingFiles((prev) =>
        prev.map((p) =>
          p.id === id
            ? { ...p, progress: 'error', error: err instanceof Error ? err.message : 'Upload failed' }
            : p
        )
      );
    }
  }, [docId, doctype, existingAttachments.length, onUploadComplete]);

  const handleFiles = useCallback(async (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    const remainingSlots = maxFiles - totalFiles;
    const filesToAdd = fileArray.slice(0, remainingSlots);

    for (const file of filesToAdd) {
      const error = validateFile(file);
      const preview = await createPreview(file);
      const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

      const pendingFile: PendingFile = {
        id,
        file,
        preview,
        progress: error ? 'error' : 'pending',
        error: error || undefined,
      };

      setPendingFiles((prev) => [...prev, pendingFile]);

      // Auto-upload if docId is provided and no error
      if (docId && !error) {
        uploadFile(id, file);
      }
    }
  }, [docId, totalFiles, maxFiles, validateFile, createPreview, uploadFile]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    if (!disabled && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  }, [disabled, handleFiles]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setDragActive(true);
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
  }, []);

  const handleClick = useCallback(() => {
    if (!disabled && canAddMore) {
      inputRef.current?.click();
    }
  }, [disabled, canAddMore]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
      e.target.value = '';
    }
  }, [handleFiles]);

  const removePending = useCallback((id: string) => {
    setPendingFiles((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const handleDelete = async (attachmentId: number) => {
    setDeletingId(attachmentId);
    try {
      await documentsApi.deleteAttachment(attachmentId);
      onDelete?.(attachmentId);
    } catch (err) {
      console.error('Failed to delete attachment:', err);
    } finally {
      setDeletingId(null);
    }
  };

  const retryUpload = useCallback((id: string) => {
    const pending = pendingFiles.find((p) => p.id === id);
    if (pending && docId) {
      uploadFile(id, pending.file);
    }
  }, [pendingFiles, docId, uploadFile]);

  return (
    <div className={cn('space-y-3', className)}>
      {/* Drop Zone */}
      <div
        onClick={handleClick}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={cn(
          'relative border-2 border-dashed rounded-xl p-6 transition-all cursor-pointer',
          dragActive
            ? 'border-violet-400 bg-violet-500/10'
            : 'border-slate-border hover:border-slate-muted',
          disabled && 'opacity-50 cursor-not-allowed',
          !canAddMore && 'opacity-50 cursor-not-allowed'
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={acceptedTypes.join(',')}
          onChange={handleInputChange}
          disabled={disabled || !canAddMore}
          className="hidden"
        />
        <div className="flex flex-col items-center gap-2 text-center">
          <div className={cn('p-3 rounded-full', dragActive ? 'bg-violet-500/20' : 'bg-slate-elevated')}>
            <Upload className={cn('w-6 h-6', dragActive ? 'text-violet-400' : 'text-slate-muted')} />
          </div>
          <div>
            <p className="text-sm text-white font-medium">
              {canAddMore ? 'Drop receipts here or click to upload' : 'Maximum files reached'}
            </p>
            <p className="text-xs text-slate-muted mt-1">
              {acceptedTypes.map((t) => t.split('/')[1].toUpperCase()).join(', ')} up to {maxSizeMB}MB
            </p>
          </div>
          {!docId && (
            <p className="text-xs text-amber-400 mt-1">
              Save the claim first to enable receipt upload
            </p>
          )}
        </div>
      </div>

      {/* Existing Attachments */}
      {existingAttachments.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-slate-muted font-medium uppercase tracking-wide">Uploaded Receipts</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {existingAttachments.map((att) => {
              const Icon = getFileIcon(att.file_type);
              const isImage = att.file_type?.startsWith('image/');
              return (
                <div
                  key={att.id}
                  className="bg-slate-elevated border border-slate-border rounded-lg p-2 group relative"
                >
                  <div className="flex items-center gap-2">
                    <div className={cn('p-1.5 rounded bg-slate-card', isImage ? 'text-emerald-400' : 'text-violet-400')}>
                      <Icon className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-white truncate" title={att.file_name}>
                        {att.file_name}
                      </p>
                      {att.file_size && (
                        <p className="text-[10px] text-slate-muted">{formatFileSize(att.file_size)}</p>
                      )}
                    </div>
                  </div>
                  <div className="absolute top-1 right-1 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {isImage && (
                      <button
                        onClick={() => setPreviewUrl(`/api/attachments/${att.id}/file`)}
                        className="p-1 bg-slate-card rounded text-slate-muted hover:text-white transition-colors"
                        title="Preview"
                      >
                        <ZoomIn className="w-3 h-3" />
                      </button>
                    )}
                    <button
                      onClick={() => handleDelete(att.id)}
                      disabled={deletingId === att.id}
                      className="p-1 bg-slate-card rounded text-slate-muted hover:text-rose-400 transition-colors disabled:opacity-50"
                      title="Delete"
                    >
                      {deletingId === att.id ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <Trash2 className="w-3 h-3" />
                      )}
                    </button>
                  </div>
                  {att.is_primary && (
                    <span className="absolute bottom-1 right-1 px-1.5 py-0.5 bg-violet-500/20 text-violet-400 text-[9px] rounded">
                      Primary
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Pending Files */}
      {pendingFiles.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-slate-muted font-medium uppercase tracking-wide">Uploading</p>
          <div className="space-y-2">
            {pendingFiles.map((pending) => (
              <div
                key={pending.id}
                className={cn(
                  'bg-slate-elevated border rounded-lg p-3 flex items-center gap-3',
                  pending.progress === 'error' ? 'border-rose-500/50' : 'border-slate-border'
                )}
              >
                {/* Preview or Icon */}
                {pending.preview ? (
                  <div className="w-12 h-12 rounded overflow-hidden bg-slate-card flex-shrink-0 relative">
                    <Image src={pending.preview} alt="" fill className="object-cover" unoptimized />
                  </div>
                ) : (
                  <div className="w-12 h-12 rounded bg-slate-card flex items-center justify-center flex-shrink-0">
                    <FileText className="w-5 h-5 text-violet-400" />
                  </div>
                )}

                {/* File Info */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-white truncate">{pending.file.name}</p>
                  <p className="text-xs text-slate-muted">{formatFileSize(pending.file.size)}</p>
                  {pending.error && (
                    <p className="text-xs text-rose-400 mt-1">{pending.error}</p>
                  )}
                </div>

                {/* Status */}
                <div className="flex items-center gap-2">
                  {pending.progress === 'pending' && !docId && (
                    <span className="text-xs text-slate-muted">Waiting...</span>
                  )}
                  {pending.progress === 'uploading' && (
                    <Loader2 className="w-5 h-5 text-violet-400 animate-spin" />
                  )}
                  {pending.progress === 'success' && (
                    <CheckCircle className="w-5 h-5 text-emerald-400" />
                  )}
                  {pending.progress === 'error' && (
                    <>
                      <AlertTriangle className="w-5 h-5 text-rose-400" />
                      {docId && (
                        <button
                          onClick={() => retryUpload(pending.id)}
                          className="text-xs text-violet-400 hover:text-violet-300"
                        >
                          Retry
                        </button>
                      )}
                    </>
                  )}
                  <button
                    onClick={() => removePending(pending.id)}
                    className="p-1 text-slate-muted hover:text-white transition-colors"
                    title="Remove"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Preview Modal */}
      {previewUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setPreviewUrl(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh]">
            <button
              onClick={() => setPreviewUrl(null)}
              className="absolute -top-10 right-0 p-2 text-white/70 hover:text-white"
            >
              <X className="w-6 h-6" />
            </button>
            <Image
              src={previewUrl}
              alt="Receipt preview"
              width={800}
              height={600}
              className="max-w-full max-h-[90vh] w-auto h-auto rounded-lg shadow-2xl"
              onClick={(e) => e.stopPropagation()}
              unoptimized
            />
          </div>
        </div>
      )}

      {/* File Count */}
      {maxFiles > 1 && (
        <p className="text-xs text-slate-muted text-right">
          {totalFiles} / {maxFiles} files
        </p>
      )}
    </div>
  );
}
