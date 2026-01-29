import psutil

def debug_chrome_memory():
    """
    Compara diferentes métodos de medición de RAM para Chrome
    """
    print("=" * 60)
    print("DIAGNÓSTICO DE MEMORIA - CHROME")
    print("=" * 60)
    
    chrome_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'memory_full_info']):
        try:
            if proc.info['name'].lower() == 'chrome.exe':
                chrome_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    print(f"\n✅ Procesos de Chrome encontrados: {len(chrome_processes)}")
    print("-" * 60)
    
    total_rss = 0
    total_private = 0
    total_wset = 0
    
    for i, proc in enumerate(chrome_processes[:5], 1):  # Mostrar primeros 5
        try:
            mem_info = proc.memory_info()
            mem_full = proc.memory_full_info()
            
            rss_mb = mem_info.rss / (1024 * 1024)
            private_mb = getattr(mem_full, 'private', 0) / (1024 * 1024)
            wset_mb = getattr(mem_full, 'wset', 0) / (1024 * 1024)
            
            total_rss += rss_mb
            total_private += private_mb
            total_wset += wset_mb
            
            print(f"\nProceso {i} (PID: {proc.pid}):")
            print(f"  RSS (básico):     {rss_mb:.1f} MB")
            print(f"  Private (Admin):  {private_mb:.1f} MB ⭐")
            print(f"  Working Set:      {wset_mb:.1f} MB")
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError) as e:
            print(f"  Error: {e}")
    
    # Calcular totales para TODOS los procesos
    for proc in chrome_processes:
        try:
            mem_full = proc.memory_full_info()
            total_rss += proc.memory_info().rss / (1024 * 1024)
            total_private += getattr(mem_full, 'private', 0) / (1024 * 1024)
            total_wset += getattr(mem_full, 'wset', 0) / (1024 * 1024)
        except:
            pass
    
    print("\n" + "=" * 60)
    print(f"TOTALES CHROME ({len(chrome_processes)} procesos):")
    print("-" * 60)
    print(f"RSS Total:            {total_rss:.1f} MB")
    print(f"Private Total:        {total_private:.1f} MB ⭐ (Admin de Tareas)")
    print(f"Working Set Total:    {total_wset:.1f} MB")
    print("=" * 60)
    
    print("\n📋 CONCLUSIÓN:")
    print(f"El valor que Firebase debería mostrar es: {total_private:.1f} MB")
    print("Compará este número con el Administrador de Tareas")
    print("\n💡 TIP: En el Admin de Tareas, mirá la columna 'Memoria' (no 'Memoria activa')")

if __name__ == "__main__":
    debug_chrome_memory()