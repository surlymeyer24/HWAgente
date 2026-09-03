import re


def parsear_procesador(nombre):
    """
    Parsea el nombre comercial del procesador.
    Devuelve fabricante, gama (i5, Ryzen 5, etc.), modelo y generación.
    """
    if not nombre or not str(nombre).strip():
        return {
            'fabricante': 'Desconocido',
            'gama': None,
            'modelo': None,
            'generacion': None,
        }

    nombre = str(nombre).strip()
    lower = nombre.lower()

    if 'intel' in lower:
        return _parsear_intel(nombre, lower)
    if 'amd' in lower or 'ryzen' in lower:
        return _parsear_amd(nombre, lower)

    return {
        'fabricante': 'Desconocido',
        'gama': None,
        'modelo': None,
        'generacion': None,
    }


def _inferir_generacion_intel(modelo_num):
    if not modelo_num or not modelo_num.isdigit():
        return None
    n = len(modelo_num)
    if n >= 5:
        gen = int(modelo_num[:2])
    elif n >= 3:
        gen = int(modelo_num[0])
    else:
        return None
    return gen if gen >= 1 else None


def _parsear_intel(nombre, lower):
    m = re.search(r'\bi([3579])\s*-\s*(\d{3,5})([A-Z]*)', nombre, re.IGNORECASE)
    if m:
        gama = f'i{m.group(1)}'
        modelo_num = m.group(2)
        sufijo = (m.group(3) or '').upper()
        return {
            'fabricante': 'Intel',
            'gama': gama,
            'modelo': modelo_num + sufijo,
            'generacion': _inferir_generacion_intel(modelo_num),
        }

    for gama in ('Xeon', 'Celeron', 'Pentium'):
        if gama.lower() in lower:
            return {
                'fabricante': 'Intel',
                'gama': gama,
                'modelo': None,
                'generacion': None,
            }

    return {
        'fabricante': 'Intel',
        'gama': None,
        'modelo': None,
        'generacion': None,
    }


def _parsear_amd(nombre, lower):
    m = re.search(
        r'ryzen\s*([3579])\s*(?:pro\s*)?(\d{4})([A-Z]*)',
        nombre,
        re.IGNORECASE,
    )
    if m:
        gama = f'Ryzen {m.group(1)}'
        modelo_num = m.group(2)
        sufijo = (m.group(3) or '').upper()
        generacion = int(modelo_num[0]) if modelo_num[0].isdigit() else None
        return {
            'fabricante': 'AMD',
            'gama': gama,
            'modelo': modelo_num + sufijo,
            'generacion': generacion,
        }

    for gama in ('Threadripper', 'EPYC', 'Athlon'):
        if gama.lower() in lower:
            return {
                'fabricante': 'AMD',
                'gama': gama,
                'modelo': None,
                'generacion': None,
            }

    return {
        'fabricante': 'AMD',
        'gama': None,
        'modelo': None,
        'generacion': None,
    }
