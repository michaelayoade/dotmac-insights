'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { MapPin, Layers, ZoomIn, ZoomOut, Crosshair, Loader2 } from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

export type MarkerVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';

export interface MapMarker {
  id: string | number;
  /** Latitude */
  lat: number;
  /** Longitude */
  lng: number;
  /** Marker label */
  label?: string;
  /** Popup content */
  popupContent?: string | React.ReactNode;
  /** Marker variant */
  variant?: MarkerVariant;
  /** Custom icon URL */
  iconUrl?: string;
  /** Additional data */
  data?: Record<string, unknown>;
  /** Is draggable */
  draggable?: boolean;
}

export interface MapBounds {
  north: number;
  south: number;
  east: number;
  west: number;
}

export interface MapViewport {
  center: [number, number];
  zoom: number;
}

// =============================================================================
// MAP VIEW
// =============================================================================

export interface MapViewProps {
  /** Markers to display */
  markers?: MapMarker[];
  /** Initial center [lat, lng] */
  center?: [number, number];
  /** Initial zoom level */
  zoom?: number;
  /** Map height */
  height?: string | number;
  /** Fit bounds to markers */
  fitBoundsToMarkers?: boolean;
  /** Callback when marker is clicked */
  onMarkerClick?: (marker: MapMarker) => void;
  /** Callback when marker is dragged */
  onMarkerDrag?: (marker: MapMarker, newPosition: { lat: number; lng: number }) => void;
  /** Callback when map is clicked */
  onMapClick?: (position: { lat: number; lng: number }) => void;
  /** Callback when viewport changes */
  onViewportChange?: (viewport: MapViewport) => void;
  /** Show zoom controls */
  showZoomControls?: boolean;
  /** Show layer selector */
  showLayerSelector?: boolean;
  /** Show locate button */
  showLocateButton?: boolean;
  /** Loading state */
  loading?: boolean;
  /** Error message */
  error?: string;
  /** Custom class name */
  className?: string;
  /** Tile layer (default OpenStreetMap) */
  tileLayer?: 'osm' | 'satellite' | 'terrain';
}

// Marker color variants
const MARKER_COLORS: Record<MarkerVariant, string> = {
  default: '#14b8a6', // teal
  success: '#10b981', // emerald
  warning: '#f59e0b', // amber
  danger: '#f87171', // coral
  info: '#3b82f6', // blue
};

const TILE_LAYERS = {
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors',
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '© Esri',
  },
  terrain: {
    url: 'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    attribution: '© OpenTopoMap contributors',
  },
};

export function MapView({
  markers = [],
  center = [6.5244, 3.3792], // Lagos, Nigeria default
  zoom = 12,
  height = 400,
  fitBoundsToMarkers = true,
  onMarkerClick,
  onMarkerDrag,
  onMapClick,
  onViewportChange,
  showZoomControls = true,
  showLayerSelector = false,
  showLocateButton = true,
  loading = false,
  error,
  className,
  tileLayer = 'osm',
}: MapViewProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const tileLayerRef = useRef<any>(null);
  const markersRef = useRef<Map<string | number, any>>(new Map());
  const lastSetViewRef = useRef<{ center: [number, number]; zoom: number } | null>(null);
  const [isMapReady, setIsMapReady] = useState(false);
  const [isLocating, setIsLocating] = useState(false);

  // Initialize map
  useEffect(() => {
    if (typeof window === 'undefined' || !mapContainerRef.current) return;
    let isMounted = true;

    // Dynamic import of Leaflet (client-side only)
    const initMap = async () => {
      const L = await import('leaflet');
      const container = mapContainerRef.current;
      if (!container) return;

      // Fix default marker icon issue
      delete (L.Icon.Default.prototype as any)._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
        iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
        shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
      });

      // Create map if not exists
      if (!mapRef.current) {
        mapRef.current = L.map(container, {
          center,
          zoom,
          zoomControl: false,
        });
      }

      // Update tile layer
      const tile = TILE_LAYERS[tileLayer];
      if (tileLayerRef.current) {
        tileLayerRef.current.remove();
      }
      tileLayerRef.current = L.tileLayer(tile.url, {
        attribution: tile.attribution,
      }).addTo(mapRef.current);

      // Update view only when props differ from the current map state
      const currentCenter = mapRef.current.getCenter();
      const currentZoom = mapRef.current.getZoom();
      const centerChanged =
        Math.abs(currentCenter.lat - center[0]) > 1e-6 ||
        Math.abs(currentCenter.lng - center[1]) > 1e-6;
      const zoomChanged = currentZoom !== zoom;
      if (centerChanged || zoomChanged) {
        lastSetViewRef.current = { center, zoom };
        mapRef.current.setView(center, zoom);
      }

      // Map click handler
      mapRef.current.off('click');
      mapRef.current.on('click', (e: any) => {
        onMapClick?.({ lat: e.latlng.lat, lng: e.latlng.lng });
      });

      // Viewport change handler
      mapRef.current.off('moveend');
      mapRef.current.on('moveend', () => {
        if (mapRef.current) {
          const nextCenter = mapRef.current.getCenter();
          const nextZoom = mapRef.current.getZoom();
          if (lastSetViewRef.current) {
            const { center: lastCenter, zoom: lastZoom } = lastSetViewRef.current;
            const isSameCenter =
              Math.abs(nextCenter.lat - lastCenter[0]) <= 1e-6 &&
              Math.abs(nextCenter.lng - lastCenter[1]) <= 1e-6;
            const isSameZoom = nextZoom === lastZoom;
            if (isSameCenter && isSameZoom) {
              lastSetViewRef.current = null;
              return;
            }
          }
          lastSetViewRef.current = null;
          onViewportChange?.({
            center: [nextCenter.lat, nextCenter.lng],
            zoom: nextZoom,
          });
        }
      });

      if (isMounted) {
        setIsMapReady(true);
      }
    };

    initMap().catch(console.error);

    return () => {
      isMounted = false;
    };
  }, [center, onMapClick, onViewportChange, tileLayer, zoom]);

  useEffect(() => {
    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
        tileLayerRef.current = null;
        setIsMapReady(false);
      }
    };
  }, []);

  // Update markers
  useEffect(() => {
    if (!isMapReady || !mapRef.current) return;

    const updateMarkers = async () => {
      const L = await import('leaflet');

      // Remove old markers
      markersRef.current.forEach((marker) => {
        marker.remove();
      });
      markersRef.current.clear();

      // Add new markers
      markers.forEach((markerData) => {
        const color = MARKER_COLORS[markerData.variant || 'default'];

        // Custom colored marker icon
        const icon = L.divIcon({
          className: 'custom-marker',
          html: `
            <div style="
              width: 24px;
              height: 24px;
              border-radius: 50% 50% 50% 0;
              background: ${color};
              transform: rotate(-45deg);
              border: 2px solid white;
              box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            ">
              <div style="
                width: 8px;
                height: 8px;
                background: white;
                border-radius: 50%;
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
              "></div>
            </div>
          `,
          iconSize: [24, 24],
          iconAnchor: [12, 24],
          popupAnchor: [0, -24],
        });

        const marker = L.marker([markerData.lat, markerData.lng], {
          icon,
          draggable: markerData.draggable,
        }).addTo(mapRef.current);

        // Popup
        if (markerData.popupContent || markerData.label) {
          const content =
            typeof markerData.popupContent === 'string'
              ? markerData.popupContent
              : `<strong>${markerData.label || 'Location'}</strong>`;
          marker.bindPopup(content);
        }

        // Click handler
        marker.on('click', () => {
          onMarkerClick?.(markerData);
        });

        // Drag handler
        if (markerData.draggable) {
          marker.on('dragend', (e: any) => {
            const pos = e.target.getLatLng();
            onMarkerDrag?.(markerData, { lat: pos.lat, lng: pos.lng });
          });
        }

        markersRef.current.set(markerData.id, marker);
      });

      // Fit bounds to markers
      if (fitBoundsToMarkers && markers.length > 0) {
        const bounds = L.latLngBounds(markers.map((m) => [m.lat, m.lng]));
        mapRef.current.fitBounds(bounds, { padding: [50, 50] });
      }
    };

    updateMarkers().catch(console.error);
  }, [markers, isMapReady, fitBoundsToMarkers, onMarkerClick, onMarkerDrag]);

  // Zoom controls
  const handleZoomIn = useCallback(() => {
    mapRef.current?.zoomIn();
  }, []);

  const handleZoomOut = useCallback(() => {
    mapRef.current?.zoomOut();
  }, []);

  // Locate user
  const handleLocate = useCallback(() => {
    if (!mapRef.current || !navigator.geolocation) return;

    setIsLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        mapRef.current?.setView([position.coords.latitude, position.coords.longitude], 15);
        setIsLocating(false);
      },
      () => {
        setIsLocating(false);
      },
      { enableHighAccuracy: true }
    );
  }, []);

  return (
    <div className={cn('relative rounded-xl overflow-hidden', className)}>
      {/* Map Container */}
      <div
        ref={mapContainerRef}
        style={{ height: typeof height === 'number' ? `${height}px` : height }}
        className="w-full bg-slate-elevated"
      />

      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 bg-slate-deep/50 backdrop-blur-sm flex items-center justify-center z-[1000]">
          <Loader2 className="w-8 h-8 text-teal-electric animate-spin" />
        </div>
      )}

      {/* Error Overlay */}
      {error && (
        <div className="absolute inset-0 bg-slate-deep/90 flex items-center justify-center z-[1000]">
          <div className="text-center p-4">
            <MapPin className="w-12 h-12 text-coral-alert mx-auto mb-2" />
            <p className="text-coral-alert text-sm">{error}</p>
          </div>
        </div>
      )}

      {/* Controls */}
      <div className="absolute top-3 right-3 flex flex-col gap-2 z-[1000]">
        {/* Zoom Controls */}
        {showZoomControls && (
          <div className="flex flex-col bg-background border border-slate-border rounded-lg shadow-lg overflow-hidden">
            <button
              type="button"
              onClick={handleZoomIn}
              className="p-2 hover:bg-slate-elevated border-b border-slate-border transition-colors"
              title="Zoom in"
            >
              <ZoomIn className="w-4 h-4 text-foreground" />
            </button>
            <button
              type="button"
              onClick={handleZoomOut}
              className="p-2 hover:bg-slate-elevated transition-colors"
              title="Zoom out"
            >
              <ZoomOut className="w-4 h-4 text-foreground" />
            </button>
          </div>
        )}

        {/* Layer Selector */}
        {showLayerSelector && (
          <button
            type="button"
            className="p-2 bg-background border border-slate-border rounded-lg shadow-lg hover:bg-slate-elevated transition-colors"
            title="Change map style"
          >
            <Layers className="w-4 h-4 text-foreground" />
          </button>
        )}

        {/* Locate Button */}
        {showLocateButton && (
          <button
            type="button"
            onClick={handleLocate}
            disabled={isLocating}
            className={cn(
              'p-2 bg-background border border-slate-border rounded-lg shadow-lg transition-colors',
              isLocating ? 'opacity-50' : 'hover:bg-slate-elevated'
            )}
            title="My location"
          >
            {isLocating ? (
              <Loader2 className="w-4 h-4 text-foreground animate-spin" />
            ) : (
              <Crosshair className="w-4 h-4 text-foreground" />
            )}
          </button>
        )}
      </div>

      {/* Marker Count Badge */}
      {markers.length > 0 && (
        <div className="absolute bottom-3 left-3 z-[1000] px-2 py-1 bg-background/90 backdrop-blur-sm border border-slate-border rounded-lg text-xs text-slate-muted">
          {markers.length} location{markers.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// STATIC MAP (No interaction, for previews)
// =============================================================================

export interface StaticMapProps {
  lat: number;
  lng: number;
  zoom?: number;
  width?: number;
  height?: number;
  marker?: boolean;
  className?: string;
}

export function StaticMap({
  lat,
  lng,
  zoom = 15,
  width = 300,
  height = 200,
  marker = true,
  className,
}: StaticMapProps) {
  // Using OpenStreetMap static image tiles
  const tileUrl = `https://static-maps.yandex.ru/1.x/?ll=${lng},${lat}&size=${width},${height}&z=${zoom}&l=map${marker ? `&pt=${lng},${lat},pm2rdm` : ''}`;

  return (
    <div
      className={cn(
        'relative rounded-lg overflow-hidden bg-slate-elevated',
        className
      )}
      style={{ width, height }}
    >
      {/* Fallback using OpenStreetMap embed */}
      <iframe
        width={width}
        height={height}
        style={{ border: 0 }}
        loading="lazy"
        src={`https://www.openstreetmap.org/export/embed.html?bbox=${lng - 0.01}%2C${lat - 0.01}%2C${lng + 0.01}%2C${lat + 0.01}&layer=mapnik${marker ? `&marker=${lat}%2C${lng}` : ''}`}
        title="Map"
      />
    </div>
  );
}

export default MapView;
