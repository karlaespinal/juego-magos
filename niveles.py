"""
niveles.py - Definición de los niveles de la Etapa 1.

Cada nivel se construye con una cuadrícula de bloques de 40x40 px (18 filas = 720 px).
Para editar o crear niveles basta con usar los métodos de la clase Nivel:

    suelo(c0, c1, fila_tope)   -> columna de roca desde 'fila_tope' hasta el fondo de la pantalla
    plat(c0, c1, fila)         -> plataforma flotante de 1 bloque de alto
    bloque(c0, c1, f0, f1)     -> muro rectangular
    pinchos(c0, c1, fila)      -> pinchos (dañan al jugador)
    cristales(c0, c1, fila)    -> cristales (100 puntos)
    corazon(c, fila)           -> recupera 1 corazón
    checkpoint(c, fila)        -> punto de reaparición
    enemigo(tipo, c, fila)     -> F = Mago de Fuego, L = Mago de Rayos (disparan)
                                  G, H, I = Gorgonas (persiguen y atacan cuerpo a cuerpo)
    inicio(c, fila) / salida(c, fila)

'fila' en objetos/enemigos es la fila donde "están de pie" (la fila justo encima del suelo).

Para comprobar que los niveles se pueden completar:   python niveles.py
"""

TILE = 40
FILAS = 18


class Nivel:
    def __init__(self, nombre, fondo, cols, colores, hp_enemigos=2, pista=""):
        self.nombre = nombre
        self.fondo = fondo              # número de fondo (1-4)
        self.cols = cols
        self.colores = colores          # dict: roca, roca_oscura, borde (color de la hierba/cima)
        self.hp_enemigos = hp_enemigos
        self.pista = pista
        self.grid = [[' '] * cols for _ in range(FILAS)]
        self.inicio_pos = (2, 14)
        self.salida_pos = (cols - 3, 14)
        self.enemigos = []              # (tipo, col, fila)
        self.items = []                 # (tipo, col, fila)  tipo: 'C' cristal, 'H' corazón
        self.checkpoints = []           # (col, fila)

    # ---- construcción -------------------------------------------------
    def suelo(self, c0, c1, tope):
        for f in range(tope, FILAS):
            for c in range(c0, c1 + 1):
                self.grid[f][c] = '#'

    def plat(self, c0, c1, fila):
        for c in range(c0, c1 + 1):
            self.grid[fila][c] = '#'

    def bloque(self, c0, c1, f0, f1):
        for f in range(f0, f1 + 1):
            for c in range(c0, c1 + 1):
                self.grid[f][c] = '#'

    def pinchos(self, c0, c1, fila):
        for c in range(c0, c1 + 1):
            self.grid[fila][c] = '^'

    def cristales(self, c0, c1, fila):
        for c in range(c0, c1 + 1):
            self.items.append(('C', c, fila))

    def corazon(self, c, fila):
        self.items.append(('H', c, fila))

    def checkpoint(self, c, fila):
        self.checkpoints.append((c, fila))

    def enemigo(self, tipo, c, fila):
        self.enemigos.append((tipo, c, fila))

    def inicio(self, c, fila):
        self.inicio_pos = (c, fila)

    def salida(self, c, fila):
        self.salida_pos = (c, fila)


# ======================================================================
# NIVEL 1 - Valle Brumoso  (tutorial: saltos cortos, pocos enemigos)
# ======================================================================
def nivel_1():
    n = Nivel("Nivel 1 - Valle Brumoso", 1, 120,
              dict(roca=(92, 66, 84), roca_oscura=(70, 48, 66), borde=(110, 170, 120)),
              hp_enemigos=2,
              pista="A/D mover, ESPACIO saltar, J magia, 1-2-3 magias especiales (gastan MAGIA)")
    n.suelo(0, 24, 15)
    n.inicio(3, 14)
    n.cristales(8, 12, 13)

    n.suelo(28, 52, 15)                    # hueco 25-27
    n.cristales(30, 34, 13)
    n.enemigo('F', 42, 14)
    n.checkpoint(48, 14)

    n.plat(56, 59, 13)                     # hueco 53-55
    n.cristales(56, 59, 11)
    n.plat(63, 66, 11)
    n.cristales(63, 66, 9)

    n.suelo(70, 98, 15)                    # hueco 67-69
    n.corazon(73, 13)
    n.pinchos(78, 80, 14)
    n.cristales(77, 81, 11)
    n.enemigo('L', 88, 14)
    n.cristales(92, 96, 13)

    n.suelo(102, 119, 15)                  # hueco 99-101
    n.enemigo('F', 110, 14)
    n.salida(116, 14)
    return n


# ======================================================================
# NIVEL 2 - Colinas Rojizas  (escaleras, pinchos y torres flotantes)
# ======================================================================
def nivel_2():
    n = Nivel("Nivel 2 - Colinas Rojizas", 2, 140,
              dict(roca=(112, 76, 70), roca_oscura=(84, 54, 54), borde=(176, 140, 96)),
              hp_enemigos=3,
              pista="Cuidado con los pinchos. Usa SHIFT para correr y saltar mas lejos")
    n.suelo(0, 20, 15)
    n.inicio(3, 14)
    n.cristales(8, 11, 13)

    n.suelo(21, 24, 14)
    n.suelo(25, 28, 13)
    n.suelo(29, 36, 12)
    n.enemigo('F', 33, 11)
    n.cristales(29, 31, 10)
    n.checkpoint(35, 11)

    n.plat(41, 45, 12)                     # hueco 37-40
    n.cristales(41, 45, 10)

    n.suelo(49, 70, 15)                    # hueco 46-48
    n.pinchos(55, 56, 14)
    n.pinchos(62, 64, 14)
    n.cristales(53, 57, 11)
    n.enemigo('L', 59, 14)
    n.corazon(58, 12)
    n.checkpoint(67, 14)

    n.plat(74, 76, 13)                     # torres flotantes
    n.cristales(74, 76, 11)
    n.plat(80, 82, 11)
    n.cristales(80, 82, 9)
    n.plat(86, 88, 13)
    n.cristales(86, 88, 11)
    n.plat(92, 94, 11)
    n.cristales(92, 94, 9)

    n.suelo(98, 139, 15)                   # hueco 95-97
    n.checkpoint(101, 14)
    n.enemigo('F', 105, 14)
    n.pinchos(108, 110, 14)
    n.cristales(107, 111, 11)
    n.enemigo('L', 114, 14)
    n.pinchos(118, 119, 14)
    n.corazon(121, 13)
    n.bloque(124, 125, 12, 14)
    n.enemigo('F', 130, 14)
    n.cristales(127, 133, 13)
    n.salida(136, 14)
    return n


# ======================================================================
# NIVEL 3 - Bosque Nocturno  (islas de roca y enemigos en altura)
# ======================================================================
def nivel_3():
    n = Nivel("Nivel 3 - Bosque Nocturno", 3, 150,
              dict(roca=(40, 46, 74), roca_oscura=(28, 32, 56), borde=(66, 120, 110)),
              hp_enemigos=3,
              pista="Los magos disparan: esquiva sus bolas de magia saltando")
    n.suelo(0, 18, 15)
    n.inicio(3, 14)
    n.cristales(7, 10, 13)
    n.enemigo('L', 14, 14)

    n.suelo(22, 30, 14)                    # hueco 19-21
    n.pinchos(25, 26, 13)
    n.cristales(24, 27, 10)

    n.plat(34, 36, 12)                     # hueco 31-33
    n.cristales(34, 36, 10)
    n.plat(40, 42, 10)
    n.enemigo('F', 41, 9)
    n.plat(46, 48, 12)
    n.cristales(46, 48, 10)

    n.suelo(52, 70, 14)                    # hueco 49-51
    n.checkpoint(54, 13)
    n.pinchos(57, 58, 13)
    n.enemigo('L', 60, 13)
    n.corazon(63, 12)
    n.enemigo('F', 66, 13)
    n.cristales(60, 68, 11)

    n.suelo(74, 77, 13)                    # islas
    n.cristales(74, 77, 11)
    n.suelo(81, 84, 14)
    n.cristales(81, 84, 12)
    n.suelo(88, 91, 12)
    n.enemigo('F', 90, 11)
    n.suelo(95, 98, 14)
    n.cristales(95, 98, 12)
    n.suelo(102, 106, 12)
    n.checkpoint(104, 11)

    n.suelo(110, 149, 15)                  # hueco 107-109
    n.enemigo('L', 116, 14)
    n.pinchos(119, 121, 14)
    n.cristales(118, 122, 11)
    n.corazon(124, 13)
    n.enemigo('F', 126, 14)
    n.pinchos(129, 130, 14)
    n.bloque(133, 134, 12, 14)
    n.enemigo('L', 139, 14)
    n.cristales(136, 142, 13)
    n.salida(146, 14)
    return n


# ======================================================================
# NIVEL 4 - Cascada Mística  (nivel final: saltos largos y muchos magos)
# ======================================================================
def nivel_4():
    n = Nivel("Nivel 4 - Cascada Mistica", 4, 160,
              dict(roca=(62, 58, 108), roca_oscura=(44, 40, 82), borde=(96, 168, 178)),
              hp_enemigos=4,
              pista="Nivel final. Derrota a los magos y llega al portal")
    n.suelo(0, 16, 15)
    n.inicio(3, 14)
    n.cristales(6, 9, 13)
    n.enemigo('F', 13, 14)

    n.suelo(21, 27, 14)                    # hueco 17-20 (4 bloques: usa SHIFT)
    n.enemigo('L', 25, 13)
    n.cristales(22, 26, 11)
    n.suelo(31, 33, 12)
    n.suelo(37, 39, 10)
    n.enemigo('F', 38, 9)
    n.suelo(43, 45, 12)
    n.cristales(43, 45, 10)

    n.suelo(49, 62, 14)                    # hueco 46-48
    n.checkpoint(51, 13)
    n.pinchos(55, 56, 13)
    n.cristales(54, 57, 10)
    n.corazon(53, 12)
    n.enemigo('L', 58, 13)
    n.enemigo('F', 61, 13)

    n.suelo(67, 80, 15)                    # hueco 63-66 (4 bloques)
    n.pinchos(70, 71, 14)
    n.pinchos(75, 77, 14)
    n.cristales(69, 78, 11)
    n.enemigo('L', 79, 14)

    n.plat(84, 86, 13)                     # hueco 81-83
    n.plat(90, 92, 11)
    n.enemigo('F', 91, 10)
    n.cristales(90, 92, 9)
    n.plat(96, 98, 13)
    n.cristales(96, 98, 11)

    n.suelo(102, 120, 15)                  # hueco 99-101
    n.checkpoint(104, 14)
    n.pinchos(107, 108, 14)
    n.enemigo('L', 110, 14)
    n.corazon(111, 12)
    n.pinchos(113, 114, 14)
    n.enemigo('F', 116, 14)
    n.cristales(106, 118, 11)

    n.suelo(121, 124, 14)                  # escalera final
    n.suelo(125, 128, 13)
    n.suelo(129, 159, 12)
    n.checkpoint(131, 11)
    n.enemigo('F', 135, 11)
    n.enemigo('L', 140, 11)
    n.pinchos(143, 144, 11)
    n.enemigo('F', 148, 11)
    n.corazon(146, 10)
    n.cristales(133, 150, 9)
    n.bloque(152, 153, 9, 11)
    n.salida(157, 11)
    return n


# ======================================================================
# NIVEL 5 - Pantano Embrujado  (primeras gorgonas)
# ======================================================================
def nivel_5():
    n = Nivel("Nivel 5 - Pantano Embrujado", 5, 130,
              dict(roca=(60, 66, 38), roca_oscura=(42, 48, 26), borde=(124, 196, 64)),
              hp_enemigos=3,
              pista="Las gorgonas te persiguen y atacan con la cola: dispara de lejos o usa 1, 2 y 3")
    n.suelo(0, 22, 15)
    n.inicio(3, 14)
    n.cristales(7, 11, 13)
    n.enemigo('G', 17, 14)

    n.suelo(26, 50, 15)                    # hueco 23-25
    n.pinchos(32, 33, 14)
    n.cristales(29, 35, 11)
    n.enemigo('F', 40, 14)
    n.corazon(43, 13)
    n.checkpoint(47, 14)

    n.plat(54, 58, 13)                     # hueco 51-53
    n.cristales(54, 58, 11)
    n.plat(62, 66, 11)
    n.cristales(62, 66, 9)

    n.suelo(70, 100, 15)                   # hueco 67-69
    n.checkpoint(72, 14)
    n.enemigo('G', 78, 14)
    n.pinchos(82, 83, 14)
    n.enemigo('L', 87, 14)
    n.pinchos(92, 94, 14)
    n.cristales(80, 98, 12)
    n.corazon(96, 13)

    n.suelo(104, 129, 15)                  # hueco 101-103
    n.enemigo('H', 112, 14)
    n.bloque(116, 117, 12, 14)
    n.enemigo('F', 121, 14)
    n.cristales(106, 124, 11)
    n.salida(126, 14)
    return n


# ======================================================================
# NIVEL 6 - Bosque de Telarañas  (plataformas altas y gorgonas oscuras)
# ======================================================================
def nivel_6():
    n = Nivel("Nivel 6 - Bosque de Telaranas", 6, 140,
              dict(roca=(76, 46, 58), roca_oscura=(52, 32, 42), borde=(176, 62, 74)),
              hp_enemigos=3,
              pista="Las gorgonas oscuras son mas resistentes. Vigila tu barra de MAGIA")
    n.suelo(0, 18, 15)
    n.inicio(3, 14)
    n.cristales(7, 10, 13)
    n.enemigo('H', 14, 14)

    n.suelo(22, 30, 14)                    # hueco 19-21
    n.pinchos(26, 27, 13)
    n.cristales(24, 28, 10)

    n.plat(34, 38, 12)                     # hueco 31-33
    n.cristales(34, 38, 10)
    n.plat(42, 46, 10)
    n.enemigo('L', 44, 9)
    n.plat(50, 54, 12)
    n.cristales(50, 54, 10)

    n.suelo(58, 80, 14)                    # hueco 55-57
    n.checkpoint(60, 13)
    n.enemigo('G', 66, 13)
    n.pinchos(70, 71, 13)
    n.enemigo('F', 75, 13)
    n.corazon(77, 12)
    n.cristales(62, 78, 10)

    n.suelo(84, 88, 13)                    # escalones
    n.suelo(92, 96, 12)
    n.enemigo('H', 94, 11)
    n.suelo(100, 104, 14)
    n.suelo(108, 112, 12)
    n.checkpoint(110, 11)
    n.cristales(84, 88, 11)

    n.suelo(116, 139, 15)                  # hueco 113-115
    n.corazon(120, 13)
    n.enemigo('I', 123, 14)
    n.pinchos(126, 127, 14)
    n.enemigo('L', 129, 14)
    n.bloque(131, 132, 12, 14)
    n.cristales(117, 135, 11)
    n.salida(136, 14)
    return n


# ======================================================================
# NIVEL 7 - Cementerio Espectral  (muchos enemigos mezclados)
# ======================================================================
def nivel_7():
    n = Nivel("Nivel 7 - Cementerio Espectral", 7, 150,
              dict(roca=(40, 58, 76), roca_oscura=(26, 40, 56), borde=(92, 172, 192)),
              hp_enemigos=4,
              pista="Combina tus magias: la Tormenta de Rayos golpea a varios enemigos")
    n.suelo(0, 16, 15)
    n.inicio(3, 14)
    n.cristales(6, 9, 13)
    n.enemigo('G', 12, 14)

    n.suelo(20, 26, 14)                    # hueco 17-19
    n.enemigo('L', 24, 13)
    n.cristales(21, 25, 11)
    n.suelo(30, 34, 12)
    n.suelo(38, 42, 10)
    n.enemigo('F', 40, 9)
    n.suelo(46, 50, 12)
    n.cristales(46, 50, 10)

    n.suelo(54, 72, 14)                    # hueco 51-53
    n.checkpoint(56, 13)
    n.pinchos(60, 61, 13)
    n.enemigo('I', 64, 13)
    n.corazon(66, 12)
    n.enemigo('L', 69, 13)
    n.cristales(58, 70, 10)

    n.suelo(77, 82, 15)                    # hueco 73-76 (usa SHIFT)
    n.enemigo('H', 79, 14)
    n.cristales(77, 82, 12)

    n.plat(86, 90, 13)                     # hueco 83-85
    n.plat(94, 98, 11)
    n.enemigo('F', 96, 10)
    n.plat(102, 106, 13)
    n.cristales(86, 106, 9)

    n.suelo(110, 149, 15)                  # hueco 107-109
    n.checkpoint(112, 14)
    n.enemigo('G', 118, 14)
    n.pinchos(121, 123, 14)
    n.enemigo('I', 127, 14)
    n.corazon(130, 13)
    n.enemigo('L', 134, 14)
    n.bloque(137, 138, 12, 14)
    n.enemigo('F', 142, 14)
    n.cristales(112, 146, 11)
    n.salida(146, 14)
    return n


# ======================================================================
# NIVEL 8 - Cabana Embrujada  (nivel final de la etapa)
# ======================================================================
def nivel_8():
    n = Nivel("Nivel 8 - Cabana Embrujada", 8, 170,
              dict(roca=(96, 62, 38), roca_oscura=(68, 42, 26), borde=(216, 130, 42)),
              hp_enemigos=4,
              pista="Nivel final de la Etapa 1. Administra tu magia y llega al portal")
    n.suelo(0, 16, 15)
    n.inicio(3, 14)
    n.cristales(6, 9, 13)
    n.enemigo('H', 13, 14)

    n.suelo(21, 27, 14)                    # hueco 17-20 (4 bloques: usa SHIFT)
    n.enemigo('G', 25, 13)
    n.suelo(31, 35, 12)
    n.suelo(39, 43, 10)
    n.enemigo('L', 41, 9)
    n.suelo(47, 51, 12)
    n.cristales(31, 35, 10)

    n.suelo(55, 70, 14)                    # hueco 52-54
    n.checkpoint(57, 13)
    n.corazon(59, 12)
    n.pinchos(61, 62, 13)
    n.enemigo('I', 65, 13)
    n.enemigo('F', 69, 13)
    n.cristales(58, 68, 10)

    n.suelo(75, 90, 15)                    # hueco 71-74 (4 bloques)
    n.pinchos(78, 79, 14)
    n.enemigo('G', 81, 14)
    n.pinchos(84, 86, 14)
    n.enemigo('L', 89, 14)
    n.cristales(76, 88, 11)

    n.plat(94, 98, 13)                     # hueco 91-93
    n.plat(102, 106, 11)
    n.enemigo('F', 104, 10)
    n.plat(110, 114, 13)
    n.cristales(94, 114, 9)

    n.suelo(118, 140, 15)                  # hueco 115-117
    n.checkpoint(120, 14)
    n.enemigo('H', 124, 14)
    n.pinchos(127, 128, 14)
    n.enemigo('I', 131, 14)
    n.corazon(133, 13)
    n.enemigo('L', 137, 14)

    n.suelo(141, 144, 14)                  # escalera final
    n.suelo(145, 148, 13)
    n.suelo(149, 169, 12)
    n.checkpoint(151, 11)
    n.enemigo('I', 155, 11)
    n.enemigo('F', 159, 11)
    n.pinchos(162, 163, 11)
    n.enemigo('L', 165, 11)
    n.corazon(157, 10)
    n.cristales(150, 168, 9)
    n.salida(168, 11)
    return n


NIVELES = [nivel_1, nivel_2, nivel_3, nivel_4, nivel_5, nivel_6, nivel_7, nivel_8]


# ======================================================================
# Verificador: ¿se puede llegar desde el inicio hasta la salida?
# ======================================================================
def _superficies(n):
    segs = []
    for f in range(FILAS):
        c = 0
        while c < n.cols:
            if n.grid[f][c] == '#' and (f == 0 or n.grid[f - 1][c] != '#'):
                c0 = c
                while c < n.cols and n.grid[f][c] == '#' and (f == 0 or n.grid[f - 1][c] != '#'):
                    c += 1
                segs.append((c0, c - 1, f))
            else:
                c += 1
    return segs


def verificar(n):
    """Devuelve lista de problemas (vacía si el nivel es completable)."""
    problemas = []
    segs = _superficies(n)

    def seg_de(c, fila_pies):
        for s in segs:
            if s[0] <= c <= s[1] and s[2] == fila_pies + 1:
                return s
        return None

    ini = seg_de(n.inicio_pos[0], n.inicio_pos[1])
    sal = seg_de(n.salida_pos[0], n.salida_pos[1])
    if not ini:
        problemas.append("El inicio no está sobre el suelo")
    if not sal:
        problemas.append("La salida no está sobre el suelo")
    for t, c, f in n.enemigos:
        if not seg_de(c, f):
            problemas.append(f"Enemigo {t} en ({c},{f}) flotando")
    for c, f in n.checkpoints:
        if not seg_de(c, f):
            problemas.append(f"Checkpoint en ({c},{f}) flotando")
    for t, c, f in n.items:
        if n.grid[f][c] == '#':
            problemas.append(f"Objeto {t} dentro de un bloque en ({c},{f})")
    # espacio libre sobre cada superficie (el jugador mide ~2.5 bloques)
    for c0, c1, f in segs:
        for c in range(c0, c1 + 1):
            for ff in range(max(0, f - 3), f):
                if n.grid[ff][c] == '#':
                    problemas.append(f"Techo bajo en columna {c}, fila {f}")
                    break
    if not ini or not sal:
        return problemas

    def alcanzable(a, b):
        hueco = max(b[0] - a[1] - 1, a[0] - b[1] - 1, 0)
        subida = a[2] - b[2]                 # >0: b está más alto
        if subida > 3:
            return False
        if subida >= 2:
            return hueco <= 3
        return hueco <= 4

    visto = {ini}
    cola = [ini]
    while cola:
        a = cola.pop()
        for b in segs:
            if b not in visto and alcanzable(a, b):
                visto.add(b)
                cola.append(b)
    if sal not in visto:
        problemas.append("La salida NO es alcanzable desde el inicio")
    return problemas


if __name__ == "__main__":
    ok = True
    for fn in NIVELES:
        nv = fn()
        p = verificar(nv)
        print(f"{nv.nombre}: {'OK' if not p else 'PROBLEMAS'}"
              f"  ({nv.cols * TILE}px, {len(nv.enemigos)} enemigos, "
              f"{sum(1 for i in nv.items if i[0] == 'C')} cristales)")
        for x in p:
            print("   -", x)
            ok = False
    print("Todos los niveles son completables" if ok else "Revisar los problemas indicados")
