export interface FirestoreTimestamp {
  seconds: number;
  nanoseconds: number;
}

export interface HWModuloRAM {
  fabricante?: string;
  modelo?: string;
  capacidad_gb?: number;
  velocidad_mhz?: number;
}

export interface HWDisco {
  tipo_disco?: string;
  dispositivo?: string;
  total_gb?: number;
  usado_gb?: number;
  libre_gb?: number;
  punto_montaje?: string;
  modelo_disco?: string;
  porcentaje_usado?: number;
  disco_fisico_index?: string | null;
}

export interface HWPerifericos {
  monitores?: Array<{
    nombre?: string;
    resolucion?: string;
    tamano_pulgadas?: number | string;
  }>;
  dispositivos_usb?: Array<{
    nombre?: string;
    categoria?: string;
    fabricante?: string;
    clase?: string;
    /** usb | bluetooth | inalambrico_usb — teclado/mouse consolidados */
    conexion?: string;
  }>;
  impresoras?: Array<{ nombre?: string; tipo?: string; estado?: string; tipo_impresora?: string; conexion_impresora?: string }>;
  audio?: { salida?: Array<{ nombre?: string }> };
  [key: string]: unknown;
}

export interface HWTarea {
  id: string;
  titulo?: string | null;
  descripcion?: string | null;
  estado?: string | null;
  maquinaId?: string | null;
  hostname?: string | null;
  fechaHora?: FirestoreTimestamp | null;
  log?: string | null;
  logs?: string[] | null;
  resultado?: string | null;
  [key: string]: unknown;
}

export interface LogActualizacion {
  id: string;
  timestamp: FirestoreTimestamp | null;
  evento: string;
  detalle: string;
  uuid: string;
  hostname: string;
  version_agente: string;
}

export interface HWSoftwareCritico {
  antivirus?: Array<{ nombre?: string; activo?: string | boolean }>;
  navegadores?: Array<{ nombre?: string; version?: string }>;
  [key: string]: unknown;
}

export interface HWRed {
  /** SSID WLAN actual (netsh), si la PC está asociada a una red Wi‑Fi */
  wifi_ssid?: string | null;
  trafico?: {
    enviado_mb?: number | string;
    recibido_mb?: number | string;
    bytes_enviados_mb?: number | string;
    bytes_recibidos_mb?: number | string;
  };
  adaptadores?: Array<{
    nombre?: string;
    ip?: string;
    ips?: string[];
    /** Nombre de perfil / SSID (Wi‑Fi) u otro nombre asignado por Windows */
    perfil_red?: string | null;
    /** p. ej. Public, Private, DomainAuthenticated */
    categoria_red?: string | null;
  }>;
  [key: string]: unknown;
}

export interface HWAplicacionActiva {
  nombre?: string | null;
  ram_mb?: number | string | null;
  cpu?: number | string | null;
  [key: string]: unknown;
}

export interface HWServicioCritico {
  nombre?: string;
  estado?: string;
  [key: string]: unknown;
}

export interface HWWindowsUpdates {
  total_pendientes?: number;
  pendientes?: unknown[];
  historial_reciente?: Array<{ titulo?: string; kb?: string; [key: string]: unknown }>;
  [key: string]: unknown;
}

export interface HWComputadora {
  id: string;
  hostname?: string | null;
  sistema_operativo?: string | null;
  so?: string | null;
  procesador?: string | null;
  cpu_uso_porcentaje?: number | null;
  cpu?: number | string | null;
  ram_total_gb?: number | null;
  ram_uso_porcentaje?: number | null;
  ram?: number | string | null;
  modulos_ram?: HWModuloRAM[] | null;
  discos?: string | HWDisco | HWDisco[] | null;
  ip_publica?: string | null;
  anydesk_id?: string | null;
  anydesk?: string | null;
  version_agente?: string | null;
  version?: string | null;
  cmd_estado?: string | null;
  estado_conexion?: string | null;
  ultima_sincronizacion?: FirestoreTimestamp | null;
  ultima_sync?: FirestoreTimestamp | null;
  perifericos?: HWPerifericos | null;
  software_critico?: HWSoftwareCritico | null;
  red?: HWRed | null;
  aplicaciones_activas?: HWAplicacionActiva[] | null;
  servicios_criticos?: HWServicioCritico[] | null;
  windows_updates?: HWWindowsUpdates | null;
  usuarios?: Record<string, string | number | boolean> | null;
  [key: string]: unknown;
}
