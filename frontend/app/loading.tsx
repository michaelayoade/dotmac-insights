export default function Loading() {
  return (
    <div className="min-h-[400px] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="relative">
          <div className="w-12 h-12 rounded-full border-4 border-slate-border border-t-teal-electric animate-spin" />
        </div>
        <p className="text-slate-muted text-sm">Loading...</p>
      </div>
    </div>
  );
}
