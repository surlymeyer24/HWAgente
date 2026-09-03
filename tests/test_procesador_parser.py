import unittest

from src.core.procesador_parser import parsear_procesador


class TestProcesadorParser(unittest.TestCase):

    def test_intel_i5_10_generacion(self):
        nombre = 'Intel(R) Core(TM) i5-10400 CPU @ 2.90GHz'
        r = parsear_procesador(nombre)
        self.assertEqual(r['fabricante'], 'Intel')
        self.assertEqual(r['gama'], 'i5')
        self.assertEqual(r['modelo'], '10400')
        self.assertEqual(r['generacion'], 10)

    def test_intel_i7_8_generacion_mobile(self):
        nombre = 'Intel(R) Core(TM) i7-8550U CPU @ 1.80GHz'
        r = parsear_procesador(nombre)
        self.assertEqual(r['gama'], 'i7')
        self.assertEqual(r['modelo'], '8550U')
        self.assertEqual(r['generacion'], 8)

    def test_intel_i5_12_generacion(self):
        nombre = 'Intel(R) Core(TM) i5-12400 CPU @ 2.50GHz'
        r = parsear_procesador(nombre)
        self.assertEqual(r['gama'], 'i5')
        self.assertEqual(r['modelo'], '12400')
        self.assertEqual(r['generacion'], 12)

    def test_intel_legacy_3_digitos(self):
        nombre = 'Intel(R) Core(TM) i5-650 CPU @ 3.20GHz'
        r = parsear_procesador(nombre)
        self.assertEqual(r['gama'], 'i5')
        self.assertEqual(r['modelo'], '650')
        self.assertEqual(r['generacion'], 6)

    def test_amd_ryzen_5_zen3(self):
        nombre = 'AMD Ryzen 5 5600X 6-Core Processor'
        r = parsear_procesador(nombre)
        self.assertEqual(r['fabricante'], 'AMD')
        self.assertEqual(r['gama'], 'Ryzen 5')
        self.assertEqual(r['modelo'], '5600X')
        self.assertEqual(r['generacion'], 5)

    def test_amd_ryzen_pro_mobile(self):
        nombre = 'AMD Ryzen 7 PRO 4750U with Radeon Graphics'
        r = parsear_procesador(nombre)
        self.assertEqual(r['gama'], 'Ryzen 7')
        self.assertEqual(r['modelo'], '4750U')
        self.assertEqual(r['generacion'], 4)

    def test_intel_celeron_sin_generacion(self):
        nombre = 'Intel(R) Celeron(R) N4020 CPU @ 1.10GHz'
        r = parsear_procesador(nombre)
        self.assertEqual(r['fabricante'], 'Intel')
        self.assertEqual(r['gama'], 'Celeron')
        self.assertIsNone(r['generacion'])

    def test_nombre_vacio(self):
        r = parsear_procesador('')
        self.assertEqual(r['fabricante'], 'Desconocido')
        self.assertIsNone(r['gama'])
        self.assertIsNone(r['generacion'])

    def test_desconocido(self):
        r = parsear_procesador('Procesador generico ARM')
        self.assertEqual(r['fabricante'], 'Desconocido')
        self.assertIsNone(r['gama'])


if __name__ == '__main__':
    unittest.main()
