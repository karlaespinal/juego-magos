"""
Videojuego de plataformas con magos - Etapa 1 (8 niveles)

Ejecutar en PyCharm:  abrir esta carpeta como proyecto y correr main.py
Requiere:             pip install pygame

Controles
    A / D o flechas ..... mover
    SHIFT ............... correr
    ESPACIO / W / ARRIBA  saltar (mantener = salto mas alto)
    J / Z / X ........... lanzar magia
    1 / 2 / 3 ........... magias especiales (gastan MAGIA y tienen enfriamiento)
    P / ESC ............. pausa
    ENTER ............... confirmar
"""
import os
import sys
import math
import random
import asyncio          # necesario para Pygbag (web)

import pygame

import niveles
from niveles import TILE, FILAS

# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------
ANCHO, ALTO = 1280, 720
FPS = 60
WEB = sys.platform == "emscripten"      # True cuando corre en el navegador (Pygbag)
BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_PERS = os.path.join(BASE, "Datos", "Assents", "Personajes")
RUTA_FONDOS = os.path.join(BASE, "Datos", "Assents", "Fondos")
RUTA_FX = os.path.join(BASE, "Datos", "Assents", "Efectos")

N_FONDOS = 8            # fondo_1..4: zonas originales, fondo_5..8: zonas Halloween
ESCALA = 1.6            # escala de los sprites (cada cuadro original mide 128x128)
FRAME = 128
ANCLA_X = 50            # x (en el cuadro original) donde está el centro del cuerpo del mago

GRAVEDAD = 2200
VEL_CAIDA_MAX = 1000
VEL_CAMINAR = 270
VEL_CORRER = 400
VEL_SALTO = 860
VIDAS_INICIALES = 3
VIDA_MAX = 5

# --- Magia y habilidades especiales (teclas 1, 2 y 3)
MANA_MAX = 100
MANA_REGEN = 5.0         # magia que se recupera por segundo
MANA_CRISTAL = 4         # magia que da cada cristal
TIEMPO_HECHIZO = 0.5     # duración de la animación de lanzamiento
ESPECIALES = [
    dict(nombre="Ola de Choque", coste=20, cd=4.0),
    dict(nombre="Nova Arcana", coste=35, cd=8.0),
    dict(nombre="Tormenta de Rayos", coste=50, cd=14.0),
]

BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)


def signo(v):
    return (v > 0) - (v < 0)


# ----------------------------------------------------------------------
# Sprites y animaciones
# ----------------------------------------------------------------------
class Hoja:
    """Animación cargada desde una hoja de sprites horizontal (cuadros de 128 px)."""

    def __init__(self, ruta, fps, ancla=ANCLA_X):
        img = pygame.image.load(ruta).convert_alpha()
        n = img.get_width() // FRAME
        w = int(FRAME * ESCALA)
        h = int(img.get_height() * ESCALA)
        self.der = []
        self.izq = []
        for i in range(n):
            f = img.subsurface((i * FRAME, 0, FRAME, img.get_height())).copy()
            f = pygame.transform.scale(f, (w, h))
            self.der.append(f)
            self.izq.append(pygame.transform.flip(f, True, False))
        self.n = n
        self.fps = fps
        self.ancho = w
        self.alto = h
        self.ancla_der = ancla * ESCALA
        self.ancla_izq = w - self.ancla_der

    def frame_ciclo(self, t):
        return int(t * self.fps) % self.n

    def frame_progreso(self, p):
        return max(0, min(self.n - 1, int(p * self.n)))

    def dibujar(self, pantalla, idx, centro_x, pies_y, dir_, cam_x):
        if dir_ >= 0:
            img, ancla = self.der[idx], self.ancla_der
        else:
            img, ancla = self.izq[idx], self.ancla_izq
        pantalla.blit(img, (centro_x - ancla - cam_x, pies_y - self.alto))


def cargar_personaje(carpeta, anims, ancla=ANCLA_X):
    return {nombre: Hoja(os.path.join(RUTA_PERS, carpeta, archivo), fps, ancla)
            for nombre, (archivo, fps) in anims.items()}


def cargar_efectos():
    """Efectos de las magias especiales (explosiones y rayos)."""
    def serie(prefijo, n, dos_digitos):
        fmt = "{}_{:02d}.png" if dos_digitos else "{}_{}.png"
        return [pygame.image.load(os.path.join(RUTA_FX, fmt.format(prefijo, i))).convert_alpha()
                for i in range(1, n + 1)]
    return dict(nova=serie("nova", 10, True), ola=serie("ola", 10, True),
                rayo_a=serie("rayo_a", 5, False), rayo_b=serie("rayo_b", 6, False),
                impacto=serie("impacto", 4, False))


# ----------------------------------------------------------------------
# Mundo (colisiones con la cuadrícula)
# ----------------------------------------------------------------------
class Mundo:
    def __init__(self, nivel):
        self.nivel = nivel
        self.grid = nivel.grid
        self.cols = nivel.cols
        self.ancho_px = nivel.cols * TILE
        self.pinchos = []
        for f in range(FILAS):
            for c in range(self.cols):
                if self.grid[f][c] == '^':
                    self.pinchos.append(pygame.Rect(c * TILE + 6, f * TILE + 16, TILE - 12, TILE - 16))

    def solido(self, c, f):
        if c < 0 or c >= self.cols:
            return True                      # muros invisibles a los lados
        if f < 0 or f >= FILAS:
            return False
        return self.grid[f][c] == '#'


class Cuerpo:
    """Caja con física: gravedad y colisión con bloques."""

    def __init__(self, cx, pies_y, w, h):
        self.w, self.h = w, h
        self.x = cx - w / 2
        self.y = pies_y - h
        self.vx = 0.0
        self.vy = 0.0
        self.suelo = False
        self.choque_x = False

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def pies(self):
        return self.y + self.h

    def mover(self, dt, mundo):
        # --- eje X
        self.x += self.vx * dt
        self.choque_x = False
        r = self.rect
        hit = False
        for c in range(r.left // TILE, (r.right - 1) // TILE + 1):
            for f in range(r.top // TILE, (r.bottom - 1) // TILE + 1):
                if mundo.solido(c, f):
                    if self.vx > 0:
                        self.x = c * TILE - self.w
                    elif self.vx < 0:
                        self.x = (c + 1) * TILE
                    self.choque_x = True
                    hit = True
                    break
            if hit:
                break
        if hit:
            self.vx = 0
        # --- eje Y
        self.y += self.vy * dt
        self.suelo = False
        r = self.rect
        hit = False
        for c in range(r.left // TILE, (r.right - 1) // TILE + 1):
            for f in range(r.top // TILE, (r.bottom - 1) // TILE + 1):
                if mundo.solido(c, f):
                    if self.vy > 0:
                        self.y = f * TILE - self.h
                        self.suelo = True
                    elif self.vy < 0:
                        self.y = (f + 1) * TILE
                    hit = True
                    break
            if hit:
                break
        if hit:
            self.vy = 0
        elif self.vy >= 0:
            # Sonda de suelo: la caja usa enteros pero la posición es decimal, así que
            # a veces queda a <1 px del suelo sin "tocarlo". Sin esto, 'suelo' parpadea
            # estando quieto (y se activa la animación de salto).
            fila = int(self.y + self.h + 1) // TILE
            if fila * TILE - (self.y + self.h) <= 1.0:
                for c in range(r.left // TILE, (r.right - 1) // TILE + 1):
                    if mundo.solido(c, fila):
                        self.y = fila * TILE - self.h
                        self.vy = 0
                        self.suelo = True
                        break


# ----------------------------------------------------------------------
# Efectos: partículas y proyectiles
# ----------------------------------------------------------------------
class Particulas:
    def __init__(self):
        self.lista = []

    def explosion(self, x, y, color, n=12, vel=220, vida=0.5, tam=5):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(vel * 0.3, vel)
            self.lista.append([x, y, math.cos(a) * v, math.sin(a) * v - 60,
                               random.uniform(vida * 0.5, vida), vida, color, tam])

    def update(self, dt):
        for p in self.lista:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 500 * dt
            p[4] -= dt
        self.lista = [p for p in self.lista if p[4] > 0]

    def dibujar(self, pantalla, cam_x):
        for x, y, _, _, vida, vida_max, color, tam in self.lista:
            r = max(1, int(tam * vida / vida_max))
            pygame.draw.circle(pantalla, color, (int(x - cam_x), int(y)), r)


_glow_cache = {}


def glow(radio, color):
    clave = (radio, color)
    if clave not in _glow_cache:
        s = pygame.Surface((radio * 4, radio * 4), pygame.SRCALPHA)
        c = radio * 2
        pygame.draw.circle(s, (*color, 40), (c, c), int(radio * 2))
        pygame.draw.circle(s, (*color, 90), (c, c), int(radio * 1.5))
        pygame.draw.circle(s, (*color, 220), (c, c), radio)
        pygame.draw.circle(s, (255, 255, 255, 255), (c, c), max(2, int(radio * 0.5)))
        _glow_cache[clave] = s
    return _glow_cache[clave]


class Proyectil:
    def __init__(self, x, y, vx, dueno, color, radio=11, dano=1):
        self.x, self.y = x, y
        self.vx = vx
        self.dueno = dueno          # 'jugador' o 'enemigo'
        self.color = color
        self.radio = radio
        self.dano = dano
        self.vida = 2.5
        self.vivo = True

    @property
    def rect(self):
        r = self.radio
        return pygame.Rect(int(self.x - r), int(self.y - r), r * 2, r * 2)

    def update(self, dt, mundo, particulas):
        self.x += self.vx * dt
        self.vida -= dt
        if self.vida <= 0:
            self.vivo = False
        elif mundo.solido(int(self.x) // TILE, int(self.y) // TILE):
            self.vivo = False
            particulas.explosion(self.x, self.y, self.color, 8, 160, 0.35, 4)

    def dibujar(self, pantalla, cam_x):
        g = glow(self.radio, self.color)
        # pequeña estela
        for i in range(1, 4):
            s = glow(max(3, self.radio - i * 2), self.color)
            pantalla.blit(s, (self.x - self.vx * 0.012 * i - s.get_width() / 2 - cam_x,
                              self.y - s.get_height() / 2), special_flags=0)
        pantalla.blit(g, (self.x - g.get_width() / 2 - cam_x, self.y - g.get_height() / 2))


# ----------------------------------------------------------------------
# Efectos de las magias especiales
# ----------------------------------------------------------------------
class FxOla:
    """Magia 1 - Ola de Choque: cúpulas de energía que avanzan por el suelo."""

    def __init__(self, fx, x, pies, retraso, golpeados):
        self.frames = fx['ola']
        self.x, self.pies = x, pies
        self.t = -retraso
        self.dur = 0.62
        self.golpeados = golpeados      # compartido: 1 golpe por enemigo y lanzamiento
        self.vivo = True

    def update(self, dt, esc):
        self.t += dt
        if self.t >= self.dur:
            self.vivo = False
        elif 0.14 <= self.t <= 0.42:
            esc.dano_area(pygame.Rect(int(self.x - 105), int(self.pies - 170), 210, 170), 2, self.golpeados)

    def dibujar(self, pantalla, cam_x):
        if self.t < 0 or not self.vivo:
            return
        img = self.frames[min(len(self.frames) - 1, int(self.t / self.dur * len(self.frames)))]
        # la base de la cúpula está al ~77% de la altura del cuadro
        pantalla.blit(img, (self.x - img.get_width() / 2 - cam_x, self.pies - img.get_height() * 0.776))


class FxNova:
    """Magia 2 - Nova Arcana: explosión alrededor del mago que daña y limpia proyectiles."""
    RADIO = 205

    def __init__(self, fx, cx, cy):
        self.frames = fx['nova']
        self.cx, self.cy = cx, cy
        self.t = 0.0
        self.dur = 0.75
        self.golpeo = False
        self.vivo = True

    def update(self, dt, esc):
        self.t += dt
        if not self.golpeo and self.t >= 0.2:
            self.golpeo = True
            esc.dano_circulo(self.cx, self.cy, self.RADIO, 3)
            esc.sacudida = 0.35
            esc.particulas.explosion(self.cx, self.cy, (140, 210, 255), 30, 420, 0.8, 6)
        if self.t >= self.dur:
            self.vivo = False

    def dibujar(self, pantalla, cam_x):
        img = self.frames[min(len(self.frames) - 1, int(self.t / self.dur * len(self.frames)))]
        pantalla.blit(img, (self.cx - img.get_width() / 2 - cam_x, self.cy - img.get_height() / 2))


class FxRayo:
    """Magia 3 - Tormenta de Rayos: cae un rayo del cielo sobre cada objetivo."""
    FPS = 26

    def __init__(self, fx, x, pies, retraso, golpeados):
        self.golpeados = golpeados
        self.x, self.pies = x, pies
        alto = max(140, int(pies))
        self.frames = [pygame.transform.scale(f, (120, alto)) for f in fx['rayo_a'] + fx['rayo_b']]
        self.impacto = [pygame.transform.scale(f, (130, 130)) for f in fx['impacto']]
        self.t = -retraso
        self.golpeo = False
        self.vivo = True

    def update(self, dt, esc):
        self.t += dt
        idx = int(self.t * self.FPS)
        if self.t >= 0 and not self.golpeo and idx >= 6:
            self.golpeo = True
            esc.dano_area(pygame.Rect(int(self.x - 65), 0, 130, int(self.pies) + 12), 4, self.golpeados)
            esc.sacudida = max(esc.sacudida, 0.2)
            esc.particulas.explosion(self.x, self.pies - 10, (190, 230, 255), 16, 320, 0.6, 5)
        if idx >= len(self.frames) + 6:
            self.vivo = False

    def dibujar(self, pantalla, cam_x):
        if self.t < 0 or not self.vivo:
            return
        idx = int(self.t * self.FPS)
        if idx < len(self.frames):
            pantalla.blit(self.frames[idx], (self.x - 60 - cam_x, 0))
        if idx >= 5:
            im = self.impacto[min(len(self.impacto) - 1, (idx - 5) // 2)]
            pantalla.blit(im, (self.x - im.get_width() / 2 - cam_x, self.pies - im.get_height() * 0.75))


# ----------------------------------------------------------------------
# Jugador
# ----------------------------------------------------------------------
class Jugador(Cuerpo):
    ANCHO_CAJA, ALTO_CAJA = 36, 100

    def __init__(self, anims):
        super().__init__(0, 0, self.ANCHO_CAJA, self.ALTO_CAJA)
        self.anims = anims
        self.hp = VIDA_MAX
        self.dir = 1
        self.vivo = True
        self.inv = 0.0           # invulnerabilidad tras recibir daño
        self.herido = 0.0
        self.cd_disparo = 0.0
        self.t_ataque = 0.0
        self.disparo_pend = -1.0
        self.coyote = 0.0
        self.buffer_salto = 0.0
        self.t_anim = 0.0
        self.t_muerte = 0.0
        self.corriendo = False
        self._contada = False    # la vida perdida ya se descontó
        # magia y habilidades especiales
        self.mana = float(MANA_MAX)
        self.mana_vis = float(MANA_MAX)      # valor mostrado: baja de forma progresiva
        self.cd_esp = [0.0] * len(ESPECIALES)
        self.t_hechizo = 0.0
        self.hechizo_pend = -1.0
        self.hechizo_idx = -1
        self.especial_listo = None           # índice de la magia que debe aparecer ahora
        self.sin_mana = 0.0                  # parpadeo de aviso "magia insuficiente"

    def colocar(self, cx, pies_y):
        self.x = cx - self.w / 2
        self.y = pies_y - self.h
        self.vx = self.vy = 0
        self.hp = VIDA_MAX
        self.vivo = True
        self.inv = 1.5
        self.herido = 0
        self.t_ataque = 0
        self.disparo_pend = -1
        self.t_muerte = 0
        self.t_hechizo = 0
        self.hechizo_pend = -1
        self.especial_listo = None
        self.mana = max(self.mana, MANA_MAX * 0.5)
        self.mana_vis = self.mana

    # --- entrada
    def pulsar_salto(self):
        self.buffer_salto = 0.12

    def soltar_salto(self):
        if self.vy < -250:
            self.vy *= 0.5

    def dar_mana(self, n):
        self.mana = min(float(MANA_MAX), self.mana + n)

    def lanzar_especial(self, i):
        """Teclas 1, 2, 3. Gasta magia y activa el enfriamiento de esa habilidad."""
        if not self.vivo or self.herido > 0 or self.t_hechizo > 0:
            return
        esp = ESPECIALES[i]
        if self.cd_esp[i] > 0:
            return
        if self.mana < esp['coste']:
            self.sin_mana = 0.5
            return
        self.mana -= esp['coste']
        self.cd_esp[i] = esp['cd']
        self.t_hechizo = TIEMPO_HECHIZO
        self.hechizo_pend = TIEMPO_HECHIZO * 0.45
        self.hechizo_idx = i
        self.t_ataque = 0
        self.disparo_pend = -1

    def lanzar(self):
        if self.vivo and self.cd_disparo <= 0 and self.herido <= 0 and self.t_hechizo <= 0:
            self.cd_disparo = 0.38
            self.t_ataque = 0.35
            self.disparo_pend = 0.14

    def recibir_dano(self, n, origen_x, particulas):
        if self.inv > 0 or not self.vivo:
            return False
        self.hp -= n
        self.inv = 1.3
        particulas.explosion(self.cx, self.y + 50, (255, 90, 90), 14, 240, 0.5, 5)
        if self.hp <= 0:
            self.hp = 0
            self.vivo = False
            self.vx = 0
            self.vy = -300
            return True
        self.herido = 0.3
        self.t_ataque = 0
        self.disparo_pend = -1
        self.t_hechizo = 0
        self.hechizo_pend = -1
        self.vx = -signo(origen_x - self.cx) * 260 or 260
        self.vy = -380
        return True

    def update(self, dt, teclas, mundo, proyectiles):
        self.t_anim += dt
        self.inv = max(0, self.inv - dt)
        self.cd_disparo = max(0, self.cd_disparo - dt)
        self.t_ataque = max(0, self.t_ataque - dt)
        self.buffer_salto = max(0, self.buffer_salto - dt)
        self.t_hechizo = max(0, self.t_hechizo - dt)
        self.sin_mana = max(0, self.sin_mana - dt)
        self.cd_esp = [max(0.0, c - dt) for c in self.cd_esp]
        if self.vivo:
            self.mana = min(float(MANA_MAX), self.mana + MANA_REGEN * dt)
        # la barra mostrada se vacía poco a poco y se llena al instante
        if self.mana_vis > self.mana:
            self.mana_vis = max(self.mana, self.mana_vis - 70 * dt)
        else:
            self.mana_vis = self.mana

        if not self.vivo:
            self.t_muerte += dt
            self.vx *= 0.9
            self.vy = min(VEL_CAIDA_MAX, self.vy + GRAVEDAD * dt)
            self.mover(dt, mundo)
            return

        if self.herido > 0:
            self.herido -= dt
        else:
            izq = teclas[pygame.K_a] or teclas[pygame.K_LEFT]
            der = teclas[pygame.K_d] or teclas[pygame.K_RIGHT]
            self.corriendo = bool(teclas[pygame.K_LSHIFT] or teclas[pygame.K_RSHIFT])
            vel = VEL_CORRER if self.corriendo else VEL_CAMINAR
            objetivo = (der - izq) * vel
            acel = 3200 if self.suelo else 2200
            if self.vx < objetivo:
                self.vx = min(objetivo, self.vx + acel * dt)
            elif self.vx > objetivo:
                self.vx = max(objetivo, self.vx - acel * dt)
            if der - izq != 0:
                self.dir = der - izq

        # salto con "coyote time" y buffer
        self.coyote = 0.1 if self.suelo else self.coyote - dt
        if self.buffer_salto > 0 and self.coyote > 0 and self.herido <= 0:
            self.vy = -VEL_SALTO
            self.coyote = 0
            self.buffer_salto = 0
            self.suelo = False

        # magia especial diferida (sincronizada con la animación de lanzamiento)
        if self.hechizo_pend >= 0:
            self.hechizo_pend -= dt
            if self.hechizo_pend < 0:
                self.especial_listo = self.hechizo_idx
                self.hechizo_pend = -1

        # disparo diferido (sincronizado con la animación)
        if self.disparo_pend >= 0:
            self.disparo_pend -= dt
            if self.disparo_pend < 0:
                proyectiles.append(Proyectil(self.cx + self.dir * 46, self.y + 44, 720 * self.dir,
                                             'jugador', (150, 170, 255), 11))
                self.disparo_pend = -1

        self.vy = min(VEL_CAIDA_MAX, self.vy + GRAVEDAD * dt)
        self.mover(dt, mundo)

    def dibujar(self, pantalla, cam_x):
        a = self.anims
        if not self.vivo:
            h = a['dead']
            idx = h.frame_progreso(min(1.0, self.t_muerte / 0.9))
        elif self.herido > 0:
            h = a['hurt']
            idx = h.frame_progreso(1 - self.herido / 0.3)
        elif self.t_hechizo > 0:
            h = a['cast']
            idx = h.frame_progreso(1 - self.t_hechizo / TIEMPO_HECHIZO)
        elif self.t_ataque > 0:
            h = a['attack']
            idx = h.frame_progreso(1 - self.t_ataque / 0.35)
        elif not self.suelo:
            h = a['jump']
            idx = max(0, min(h.n - 1, int((self.vy + 900) / 1800 * h.n)))
        elif abs(self.vx) > 330:
            h = a['run']
            idx = h.frame_ciclo(self.t_anim)
        elif abs(self.vx) > 20:
            h = a['walk']
            idx = h.frame_ciclo(self.t_anim)
        else:
            h = a['idle']
            idx = h.frame_ciclo(self.t_anim)
        if self.inv > 0 and self.vivo and int(self.inv * 14) % 2 == 0:
            return                      # parpadeo
        h.dibujar(pantalla, idx, self.cx, self.pies, self.dir, cam_x)


# ----------------------------------------------------------------------
# Enemigos
# ----------------------------------------------------------------------
ANIMS_MAGO = {
    'idle': ("Idle.png", 8), 'walk': ("Walk.png", 9), 'attack': ("Attack_1.png", 10),
    'hurt': ("Hurt.png", 10), 'dead': ("Dead.png", 8)}
ANIMS_GORGONA = {
    'idle': ("Idle.png", 8), 'walk': ("Walk.png", 14), 'attack': ("Attack_2.png", 10),
    'hurt': ("Hurt.png", 8), 'dead': ("Dead.png", 5)}

# F, L: magos que disparan.  G, H, I: gorgonas que persiguen y atacan con la cola (cuerpo a cuerpo)
TIPOS_ENEMIGO = {
    'F': dict(carpeta="Fire_Wizard", color=(255, 150, 40), vel_proy=360, cd=2.0, dur=0.7,
              puntos=250, rango=520, anims=ANIMS_MAGO),
    'L': dict(carpeta="Lightning_Mage", color=(120, 220, 255), vel_proy=500, cd=1.6, dur=0.8,
              puntos=250, rango=560, anims=ANIMS_MAGO),
    'G': dict(carpeta="Gorgon_1", color=(150, 210, 70), melee=True, vel=60, vel_persecucion=120,
              cd=1.3, dur=0.7, puntos=300, rango=380, hp_extra=0, ancla=56, anims=ANIMS_GORGONA),
    'H': dict(carpeta="Gorgon_2", color=(170, 120, 210), melee=True, vel=60, vel_persecucion=140,
              cd=1.2, dur=0.7, puntos=350, rango=400, hp_extra=1, ancla=62, anims=ANIMS_GORGONA),
    'I': dict(carpeta="Gorgon_3", color=(240, 210, 120), melee=True, vel=70, vel_persecucion=170,
              cd=1.1, dur=0.85, puntos=450, rango=420, hp_extra=2, ancla=58, anims=ANIMS_GORGONA),
}


class Enemigo(Cuerpo):
    def __init__(self, tipo, col, fila, anims, hp):
        super().__init__((col + 0.5) * TILE, (fila + 1) * TILE, 36, 100)
        self.tipo = tipo
        self.cfg = TIPOS_ENEMIGO[tipo]
        self.anims = anims
        self.hp = hp
        self.dir = random.choice((-1, 1))
        self.x0 = self.cx
        self.rango_patrulla = 130
        self.estado = 'patrulla'
        self.t_estado = 0.0
        self.t_anim = random.random() * 3
        self.cd = random.uniform(0.8, self.cfg['cd'])
        self.disparado = False
        self.t_muerto = 0.0
        self.eliminar = False
        self.golpe = False        # las gorgonas lo activan al acertar con la cola

    def recibir_dano(self, n, particulas):
        if self.estado == 'muerto':
            return False
        self.hp -= n
        particulas.explosion(self.cx, self.y + 50, self.cfg['color'], 10, 200, 0.4, 4)
        if self.hp <= 0:
            self.estado = 'muerto'
            self.t_estado = 0
            self.vx = 0
            return True
        self.estado = 'herido'
        self.t_estado = 0.3
        self.disparado = False
        return False

    def update(self, dt, mundo, jugador, proyectiles):
        self.t_anim += dt
        if self.estado == 'muerto':
            self.t_estado += dt
            self.vx = 0
            self.vy = min(VEL_CAIDA_MAX, self.vy + GRAVEDAD * dt)
            self.mover(dt, mundo)
            if self.t_estado > 1.4:
                self.eliminar = True
            return

        self.cd -= dt
        if self.estado == 'herido':
            self.t_estado -= dt
            self.vx = 0
            if self.t_estado <= 0:
                self.estado = 'patrulla'
        elif self.estado == 'ataque':
            self.t_estado += dt
            self.vx = 0
            dur = self.cfg['dur']
            if not self.disparado and self.t_estado >= dur * 0.55:
                self.disparado = True
                proyectiles.append(Proyectil(self.cx + self.dir * 48, self.y + 42,
                                             self.cfg['vel_proy'] * self.dir, 'enemigo',
                                             self.cfg['color'], 12))
            if self.t_estado >= dur:
                self.estado = 'patrulla'
                self.cd = self.cfg['cd']
        else:
            dx = jugador.cx - self.cx
            ve = (jugador.vivo and abs(dx) < self.cfg['rango']
                  and abs(jugador.rect.centery - self.rect.centery) < 110)
            if ve:
                self.dir = signo(dx) or self.dir
                self.vx = 0
                if self.cd <= 0:
                    self.estado = 'ataque'
                    self.t_estado = 0
                    self.disparado = False
            else:
                self.vx = self.dir * 70
                frente = int(self.cx + self.dir * (self.w / 2 + 4)) // TILE
                fila_pies = int(self.pies + 2) // TILE
                fila_medio = int(self.y + self.h / 2) // TILE
                if (mundo.solido(frente, fila_medio) or not mundo.solido(frente, fila_pies)
                        or (self.cx - self.x0) * self.dir > self.rango_patrulla):
                    self.dir = -self.dir
                    self.vx = 0

        self.vy = min(VEL_CAIDA_MAX, self.vy + GRAVEDAD * dt)
        self.mover(dt, mundo)

    def dibujar(self, pantalla, cam_x):
        a = self.anims
        if self.estado == 'muerto':
            h = a['dead']
            idx = h.frame_progreso(min(1.0, self.t_estado / 0.8))
            img = h.der[idx] if self.dir >= 0 else h.izq[idx]
            if self.t_estado > 0.9:
                img = img.copy()
                img.set_alpha(max(0, int(255 * (1.4 - self.t_estado) / 0.5)))
            ancla = h.ancla_der if self.dir >= 0 else h.ancla_izq
            pantalla.blit(img, (self.cx - ancla - cam_x, self.pies - h.alto))
            return
        if self.estado == 'herido':
            h = a['hurt']
            idx = h.frame_progreso(1 - self.t_estado / 0.3)
        elif self.estado == 'ataque':
            h = a['attack']
            idx = h.frame_progreso(self.t_estado / self.cfg['dur'])
        elif abs(self.vx) > 5:
            h = a['walk']
            idx = h.frame_ciclo(self.t_anim)
        else:
            h = a['idle']
            idx = h.frame_ciclo(self.t_anim)
        h.dibujar(pantalla, idx, self.cx, self.pies, self.dir, cam_x)


class Gorgona(Enemigo):
    """Enemigo cuerpo a cuerpo: patrulla, persigue al jugador y ataca con la cola."""

    def __init__(self, tipo, col, fila, anims, hp):
        super().__init__(tipo, col, fila, anims, hp)
        self.w, self.h = 44, 104
        self.x = (col + 0.5) * TILE - self.w / 2
        self.y = (fila + 1) * TILE - self.h

    def _obstaculo(self, mundo):
        frente = int(self.cx + self.dir * (self.w / 2 + 4)) // TILE
        fila_pies = int(self.pies + 2) // TILE
        fila_medio = int(self.y + self.h / 2) // TILE
        return mundo.solido(frente, fila_medio) or not mundo.solido(frente, fila_pies)

    def alcance(self):
        x = self.cx if self.dir > 0 else self.cx - 125
        return pygame.Rect(int(x), int(self.y + 20), 125, self.h - 20)

    def update(self, dt, mundo, jugador, proyectiles):
        self.t_anim += dt
        if self.estado == 'muerto':
            self.t_estado += dt
            self.vx = 0
            self.vy = min(VEL_CAIDA_MAX, self.vy + GRAVEDAD * dt)
            self.mover(dt, mundo)
            if self.t_estado > 1.4:
                self.eliminar = True
            return

        self.cd -= dt
        if self.estado == 'herido':
            self.t_estado -= dt
            self.vx = 0
            if self.t_estado <= 0:
                self.estado = 'patrulla'
        elif self.estado == 'ataque':
            self.t_estado += dt
            self.vx = 0
            dur = self.cfg['dur']
            p = self.t_estado / dur
            if not self.disparado and 0.45 <= p <= 0.9 and jugador.vivo \
                    and self.alcance().colliderect(jugador.rect):
                self.disparado = True
                self.golpe = True
            if self.t_estado >= dur:
                self.estado = 'patrulla'
                self.cd = self.cfg['cd']
        else:
            dx = jugador.cx - self.cx
            ve = (jugador.vivo and abs(dx) < self.cfg['rango']
                  and abs(jugador.rect.centery - self.rect.centery) < 120)
            if ve:
                self.dir = signo(dx) or self.dir
                if abs(dx) < 100:
                    self.vx = 0
                    if self.cd <= 0:
                        self.estado = 'ataque'
                        self.t_estado = 0
                        self.disparado = False
                else:
                    self.vx = 0 if self._obstaculo(mundo) else self.dir * self.cfg['vel_persecucion']
            else:
                self.vx = self.dir * self.cfg['vel']
                if self._obstaculo(mundo) or (self.cx - self.x0) * self.dir > self.rango_patrulla:
                    self.dir = -self.dir
                    self.vx = 0

        self.vy = min(VEL_CAIDA_MAX, self.vy + GRAVEDAD * dt)
        self.mover(dt, mundo)


# ----------------------------------------------------------------------
# Escena de juego (un nivel)
# ----------------------------------------------------------------------
class Escena:
    def __init__(self, juego, indice):
        self.juego = juego
        self.indice = indice
        self.nivel = niveles.NIVELES[indice]()
        self.mundo = Mundo(self.nivel)
        self.particulas = Particulas()
        self.proyectiles = []
        self.t = 0.0
        self.cam_x = 0.0
        self.completado = False
        self.t_fin = 0.0
        self.cristales = 0
        self.matados = 0
        self.total_enemigos = len(self.nivel.enemigos)
        self.total_cristales = sum(1 for i in self.nivel.items if i[0] == 'C')
        self.puntos_inicio = juego.puntos

        self.jugador = Jugador(juego.anim_jugador)
        c, f = self.nivel.inicio_pos
        self.respawn = ((c + 0.5) * TILE, (f + 1) * TILE)
        self.jugador.colocar(*self.respawn)

        self.efectos = []            # efectos de las magias especiales
        self.sacudida = 0.0          # temblor de cámara
        self.enemigos = []
        for t, c, f in self.nivel.enemigos:
            cfg = TIPOS_ENEMIGO[t]
            clase = Gorgona if cfg.get('melee') else Enemigo
            self.enemigos.append(clase(t, c, f, juego.anim_enemigos[t],
                                       self.nivel.hp_enemigos + cfg.get('hp_extra', 0)))
        self.items = [dict(tipo=t, x=(c + 0.5) * TILE, y=(f + 0.5) * TILE, tomado=False,
                           fase=random.random() * 6.28) for t, c, f in self.nivel.items]
        self.checks = [dict(x=(c + 0.5) * TILE, y=(f + 1) * TILE, activo=False)
                       for c, f in self.nivel.checkpoints]
        sc, sf = self.nivel.salida_pos
        self.salida = pygame.Rect(int(sc * TILE - 10), int((sf + 1) * TILE - 110), TILE + 20, 110)
        # zona de contacto más alta que el dibujo, para que no se pueda "saltar por encima"
        self.zona_salida = pygame.Rect(self.salida.x, self.salida.bottom - 260, self.salida.w, 260)

        # tiles pre-renderizados
        col = self.nivel.colores
        self.tile_cuerpo = self._tile_roca(col['roca'], col['roca_oscura'], None)
        self.tile_tope = self._tile_roca(col['roca'], col['roca_oscura'], col['borde'])
        self.fondo = juego.obtener_fondo(self.nivel.fondo - 1)
        self.msg_pista = 5.0

    @staticmethod
    def _tile_roca(c1, c2, borde):
        rnd = random.Random(7)
        s = pygame.Surface((TILE, TILE))
        s.fill(c1)
        for _ in range(14):
            x, y = rnd.randrange(TILE), rnd.randrange(TILE)
            pygame.draw.rect(s, c2, (x, y, rnd.randint(3, 9), rnd.randint(2, 5)))
        pygame.draw.line(s, c2, (0, TILE - 1), (TILE, TILE - 1))
        pygame.draw.line(s, c2, (TILE - 1, 0), (TILE - 1, TILE))
        if borde:
            pygame.draw.rect(s, borde, (0, 0, TILE, 9))
            claro = tuple(min(255, v + 40) for v in borde)
            pygame.draw.rect(s, claro, (0, 0, TILE, 3))
            for x in range(0, TILE, 6):
                pygame.draw.rect(s, borde, (x, 9, 4, 3 + (x * 7) % 4))
        return s

    # --- eventos
    def evento(self, e):
        j = self.jugador
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                j.pulsar_salto()
            elif e.key in (pygame.K_j, pygame.K_z, pygame.K_x):
                j.lanzar()
            elif e.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                j.lanzar_especial(e.key - pygame.K_1)
            elif e.key in (pygame.K_p, pygame.K_ESCAPE):
                self.juego.estado = 'pausa'
        elif e.type == pygame.KEYUP:
            if e.key in (pygame.K_SPACE, pygame.K_w, pygame.K_UP):
                j.soltar_salto()

    # --- lógica
    def update(self, dt):
        self.t += dt
        self.msg_pista = max(0, self.msg_pista - dt)
        j = self.jugador
        teclas = pygame.key.get_pressed()
        if not self.completado:
            j.update(dt, teclas, self.mundo, self.proyectiles)
            if j.especial_listo is not None:
                self.crear_especial(j.especial_listo)
                j.especial_listo = None
        else:
            j.vx = 0
            j.vy = min(VEL_CAIDA_MAX, j.vy + GRAVEDAD * dt)
            j.mover(dt, self.mundo)
            j.t_anim += dt
            self.t_fin += dt
            if self.t_fin > 1.2:
                self.juego.estado = 'nivel_completo'

        for e in self.enemigos:
            e.update(dt, self.mundo, j, self.proyectiles)
            if (e.estado != 'muerto' and j.vivo and not self.completado
                    and j.rect.colliderect(e.rect.inflate(-6, -6))):
                j.recibir_dano(1, e.cx, self.particulas)
            if e.golpe:
                e.golpe = False
                if j.vivo and not self.completado:
                    j.recibir_dano(1, e.cx, self.particulas)
        self.enemigos = [e for e in self.enemigos if not e.eliminar]

        # proyectiles
        for p in self.proyectiles:
            p.update(dt, self.mundo, self.particulas)
            if not p.vivo:
                continue
            if p.dueno == 'jugador':
                for e in self.enemigos:
                    if e.estado != 'muerto' and p.rect.colliderect(e.rect):
                        p.vivo = False
                        self.particulas.explosion(p.x, p.y, p.color, 10, 200, 0.4, 4)
                        self.herir_enemigo(e, p.dano)
                        break
            else:
                if j.vivo and not self.completado and p.rect.colliderect(j.rect):
                    p.vivo = False
                    j.recibir_dano(p.dano, p.x - p.vx, self.particulas)
        self.proyectiles = [p for p in self.proyectiles if p.vivo]

        # pinchos
        if j.vivo and not self.completado:
            hb = j.rect.inflate(-8, -4)
            for pr in self.mundo.pinchos:
                if hb.colliderect(pr):
                    if j.recibir_dano(1, j.cx - j.dir * 10, self.particulas):
                        j.vy = -520
                    break

        # objetos
        if j.vivo:
            jr = j.rect
            for it in self.items:
                if not it['tomado'] and abs(it['x'] - j.cx) < 36 and jr.top - 10 < it['y'] < jr.bottom + 10:
                    if it['tipo'] == 'H' and j.hp >= VIDA_MAX:
                        continue
                    it['tomado'] = True
                    if it['tipo'] == 'C':
                        self.cristales += 1
                        self.juego.puntos += 100
                        j.dar_mana(MANA_CRISTAL)
                        self.particulas.explosion(it['x'], it['y'], (120, 230, 255), 10, 180, 0.4, 4)
                    else:
                        j.hp = min(VIDA_MAX, j.hp + 1)
                        self.particulas.explosion(it['x'], it['y'], (255, 110, 150), 12, 200, 0.5, 5)
            for ck in self.checks:
                if not ck['activo'] and abs(ck['x'] - j.cx) < 50 and abs(ck['y'] - j.pies) < 80:
                    ck['activo'] = True
                    self.respawn = (ck['x'], ck['y'])
                    self.particulas.explosion(ck['x'], ck['y'] - 60, (255, 220, 90), 16, 220, 0.7, 5)
            if not self.completado and jr.colliderect(self.zona_salida):
                self.completado = True
                self.juego.puntos += 500
                self.particulas.explosion(self.salida.centerx, self.salida.centery,
                                          (200, 150, 255), 30, 300, 0.9, 6)

        # caída al vacío / muerte
        if not self.completado:
            if j.vivo and j.y > ALTO + 80:
                j.hp = 0
                j.vivo = False
                j.t_muerte = 99
                self.juego.vidas -= 1
                self._tras_muerte()
            elif not j.vivo:
                if j.t_muerte > 1.4:
                    if not j._contada:
                        j._contada = True
                        self.juego.vidas -= 1
                    self._tras_muerte()

        # cámara
        objetivo = j.cx - ANCHO * 0.42
        objetivo = max(0, min(self.mundo.ancho_px - ANCHO, objetivo))
        self.cam_x += (objetivo - self.cam_x) * min(1.0, 8 * dt)
        self.particulas.update(dt)
        for ef in self.efectos:
            ef.update(dt, self)
        self.efectos = [ef for ef in self.efectos if ef.vivo]
        self.sacudida = max(0.0, self.sacudida - dt)

    # --- magias especiales ---------------------------------------------
    def herir_enemigo(self, e, n):
        """Daño a un enemigo (magia normal o especial). Gestiona puntos y magia recuperada."""
        j = self.jugador
        if e.estado == 'muerto':
            return
        j.dar_mana(1)
        if e.recibir_dano(n, self.particulas):
            self.matados += 1
            self.juego.puntos += e.cfg['puntos']
            j.dar_mana(5)

    def dano_area(self, rect, n, golpeados):
        """Daña a los enemigos que toquen 'rect' (una vez cada uno) y destruye sus proyectiles."""
        for e in list(self.enemigos):
            if e.estado != 'muerto' and id(e) not in golpeados and rect.colliderect(e.rect):
                golpeados.add(id(e))
                self.herir_enemigo(e, n)
        self._limpiar_proyectiles(lambda p: rect.colliderect(p.rect))

    def dano_circulo(self, cx, cy, radio, n):
        for e in list(self.enemigos):
            if e.estado == 'muerto':
                continue
            dx, dy = e.rect.centerx - cx, e.rect.centery - cy
            if math.hypot(dx, dy) <= radio + 30:
                self.herir_enemigo(e, n)
        self._limpiar_proyectiles(lambda p: math.hypot(p.x - cx, p.y - cy) <= radio + 30)

    def _limpiar_proyectiles(self, cond):
        for p in self.proyectiles:
            if p.dueno == 'enemigo' and p.vivo and cond(p):
                p.vivo = False
                self.particulas.explosion(p.x, p.y, p.color, 8, 180, 0.4, 4)

    def _fila_suelo(self, col, pies_y):
        """Fila del bloque de suelo (con aire encima) cerca de la altura 'pies_y' en la columna 'col'."""
        fr = int(pies_y) // TILE
        for f in range(fr - 3, fr + 5):
            if self.mundo.solido(col, f) and not self.mundo.solido(col, f - 1):
                return f
        return None

    def crear_especial(self, i):
        j = self.jugador
        fx = self.juego.fx
        golpeados = set()                              # un golpe por enemigo en cada lanzamiento
        if i == 0:                                     # Ola de Choque: avanza siguiendo el suelo
            for k in range(5):
                x = j.cx + j.dir * (85 + k * 120)
                if x < 0 or x > self.mundo.ancho_px:
                    break
                col = int(x) // TILE
                fila = self._fila_suelo(col, j.pies)
                if fila is None or self.mundo.solido(col, fila - 1):
                    break                              # hueco o muro: la ola se detiene
                self.efectos.append(FxOla(fx, x, fila * TILE, k * 0.1, golpeados))
            self.sacudida = 0.15
        elif i == 1:                                   # Nova Arcana: explosión alrededor del mago
            self.efectos.append(FxNova(fx, j.cx, j.y + 52))
        else:                                          # Tormenta de Rayos: 5 rayos del cielo
            vivos = [e for e in self.enemigos
                     if e.estado != 'muerto' and abs(e.cx - j.cx) < ANCHO * 0.6]
            vivos.sort(key=lambda e: abs(e.cx - j.cx))
            objetivos = [(e.cx, e.pies) for e in vivos[:5]]
            k = 0
            while len(objetivos) < 5 and k < 10:      # si faltan enemigos, caen delante del mago
                x = j.cx + j.dir * (230 + k * 170)
                k += 1
                if 0 <= x <= self.mundo.ancho_px:
                    fila = self._fila_suelo(int(x) // TILE, j.pies)
                    if fila is not None:
                        objetivos.append((x, fila * TILE))
            for k, (x, pies) in enumerate(objetivos):
                self.efectos.append(FxRayo(fx, x, pies, k * 0.12, golpeados))

    def _tras_muerte(self):
        if self.juego.vidas <= 0:
            self.juego.estado = 'game_over'
            return
        j = self.jugador
        j._contada = False
        j.colocar(*self.respawn)
        self.proyectiles.clear()
        self.cam_x = max(0, min(self.mundo.ancho_px - ANCHO, j.cx - ANCHO * 0.42))

    # --- dibujo
    def dibujar(self, pantalla):
        cam = int(self.cam_x)
        if self.sacudida > 0:
            cam += random.randint(-1, 1) * int(2 + self.sacudida * 14)
        # fondo con parallax (tira espejada para que sea continua)
        tira = self.fondo
        ox = -(int(self.cam_x * 0.2) % tira.get_width())
        pantalla.blit(tira, (ox, 0))
        pantalla.blit(tira, (ox + tira.get_width(), 0))

        # bloques
        c0 = max(0, cam // TILE)
        c1 = min(self.mundo.cols - 1, (cam + ANCHO) // TILE + 1)
        for f in range(FILAS):
            for c in range(c0, c1 + 1):
                ch = self.mundo.grid[f][c]
                if ch == '#':
                    arriba = f > 0 and self.mundo.grid[f - 1][c] == '#'
                    pantalla.blit(self.tile_cuerpo if arriba else self.tile_tope,
                                  (c * TILE - cam, f * TILE))
                elif ch == '^':
                    self._pincho(pantalla, c * TILE - cam, f * TILE)

        self._dibujar_salida(pantalla, cam)
        for ck in self.checks:
            self._dibujar_checkpoint(pantalla, ck, cam)
        for it in self.items:
            if not it['tomado']:
                self._dibujar_item(pantalla, it, cam)

        for e in self.enemigos:
            if -300 < e.cx - cam < ANCHO + 300:
                e.dibujar(pantalla, cam)
        self.jugador.dibujar(pantalla, cam)
        for p in self.proyectiles:
            p.dibujar(pantalla, cam)
        for ef in self.efectos:
            ef.dibujar(pantalla, cam)
        self.particulas.dibujar(pantalla, cam)
        self._hud(pantalla)

    @staticmethod
    def _pincho(pantalla, x, y):
        for i in range(2):
            bx = x + i * (TILE // 2)
            pygame.draw.polygon(pantalla, (190, 195, 215),
                                [(bx, y + TILE), (bx + TILE // 4, y + 12), (bx + TILE // 2, y + TILE)])
            pygame.draw.polygon(pantalla, (235, 238, 250),
                                [(bx + 3, y + TILE), (bx + TILE // 4, y + 12), (bx + TILE // 4, y + TILE)])

    def _dibujar_item(self, pantalla, it, cam):
        bob = math.sin(self.t * 3 + it['fase']) * 5
        x, y = int(it['x'] - cam), int(it['y'] + bob)
        if x < -40 or x > ANCHO + 40:
            return
        if it['tipo'] == 'C':
            g = glow(9, (90, 210, 255))
            pantalla.blit(g, (x - g.get_width() // 2, y - g.get_height() // 2))
            pygame.draw.polygon(pantalla, (110, 225, 255), [(x, y - 13), (x + 9, y), (x, y + 13), (x - 9, y)])
            pygame.draw.polygon(pantalla, (220, 250, 255), [(x, y - 13), (x + 9, y), (x, y)])
        else:
            col = (255, 90, 130)
            pygame.draw.circle(pantalla, col, (x - 6, y - 4), 7)
            pygame.draw.circle(pantalla, col, (x + 6, y - 4), 7)
            pygame.draw.polygon(pantalla, col, [(x - 13, y - 1), (x + 13, y - 1), (x, y + 13)])
            pygame.draw.circle(pantalla, (255, 200, 215), (x - 8, y - 7), 2)

    def _dibujar_checkpoint(self, pantalla, ck, cam):
        x, y = int(ck['x'] - cam), int(ck['y'])
        if x < -60 or x > ANCHO + 60:
            return
        pygame.draw.line(pantalla, (210, 210, 220), (x, y), (x, y - 70), 4)
        col = (255, 215, 80) if ck['activo'] else (140, 140, 150)
        onda = math.sin(self.t * 5) * 3 if ck['activo'] else 0
        pygame.draw.polygon(pantalla, col, [(x + 2, y - 70), (x + 34 + onda, y - 58), (x + 2, y - 46)])

    def _dibujar_salida(self, pantalla, cam):
        r = self.salida
        x, y = r.centerx - cam, r.centery
        if x < -100 or x > ANCHO + 100:
            return
        for i in range(5):
            k = 1 - i / 5
            pulso = math.sin(self.t * 4 + i) * 3
            col = (int(120 + 100 * k), int(70 + 60 * k), 255)
            rect = pygame.Rect(0, 0, int((r.w + 6) * k + pulso), int((r.h) * k + pulso))
            rect.center = (x, y)
            pygame.draw.ellipse(pantalla, col, rect)
        pygame.draw.ellipse(pantalla, (240, 230, 255), pygame.Rect(x - 6, y - 22, 12, 44))

    def _hud(self, pantalla):
        jg = self.juego
        # corazones
        for i in range(VIDA_MAX):
            self._corazon(pantalla, 34 + i * 38, 34, i < self.jugador.hp)
        self._barra_magia(pantalla)
        self._casillas_especiales(pantalla)
        jg.texto(pantalla, f"Vidas x{jg.vidas}", 20, 152, jg.f_med, BLANCO)
        jg.texto(pantalla, f"Cristales {self.cristales}/{self.total_cristales}", 20, 178, jg.f_med, (140, 230, 255))
        jg.texto(pantalla, f"Puntos {jg.puntos}", ANCHO - 20, 20, jg.f_med, BLANCO, 'derecha')
        jg.texto(pantalla, self.nivel.nombre, ANCHO - 20, 48, jg.f_peq, (230, 230, 240), 'derecha')
        jg.texto(pantalla, f"Enemigos {self.matados}/{self.total_enemigos}", ANCHO - 20, 72, jg.f_peq,
                 (255, 190, 120), 'derecha')
        if self.msg_pista > 0 and self.nivel.pista:
            a = min(1.0, self.msg_pista)
            jg.texto(pantalla, self.nivel.pista, ANCHO // 2, ALTO - 50, jg.f_med, BLANCO, 'centro', alpha=int(255 * a))

    def _barra_magia(self, pantalla):
        """Barra de magia justo debajo de los corazones."""
        j = self.jugador
        x, y, w, h = 20, 58, 210, 16
        pygame.draw.rect(pantalla, (20, 18, 36), (x - 2, y - 2, w + 4, h + 4), border_radius=5)
        if j.mana_vis > 0:                                    # parte que se está gastando
            pygame.draw.rect(pantalla, (235, 240, 255), (x, y, int(w * j.mana_vis / MANA_MAX), h), border_radius=4)
        if j.mana > 0:
            pygame.draw.rect(pantalla, (70, 130, 255), (x, y, int(w * j.mana / MANA_MAX), h), border_radius=4)
            pygame.draw.rect(pantalla, (140, 190, 255), (x, y, int(w * j.mana / MANA_MAX), h // 3), border_radius=4)
        borde = (255, 90, 90) if (j.sin_mana > 0 and int(j.sin_mana * 16) % 2 == 0) else (170, 180, 220)
        pygame.draw.rect(pantalla, borde, (x - 2, y - 2, w + 4, h + 4), 2, border_radius=5)
        self.juego.texto(pantalla, f"MAGIA {int(j.mana)}", x + 6, y + 1, self.juego.f_peq, BLANCO, sombra=True)

    def _casillas_especiales(self, pantalla):
        """Teclas 1-3 con su icono, coste de magia y enfriamiento."""
        jg, j = self.juego, self.jugador
        tam = 54
        for i, esp in enumerate(ESPECIALES):
            x, y = 20 + i * (tam + 10), 84
            falta_mana = j.mana < esp['coste']
            pygame.draw.rect(pantalla, (24, 22, 44), (x, y, tam, tam), border_radius=6)
            ic = jg.iconos[i]
            pantalla.blit(ic, (x + (tam - ic.get_width()) // 2, y + (tam - ic.get_height()) // 2))
            cd = j.cd_esp[i]
            if cd > 0:
                alto = int(tam * cd / esp['cd'])
                velo = pygame.Surface((tam, alto), pygame.SRCALPHA)
                velo.fill((0, 0, 0, 185))
                pantalla.blit(velo, (x, y))
                jg.texto(pantalla, f"{cd:.1f}", x + tam // 2, y + 18, jg.f_med, BLANCO, 'centro')
            elif falta_mana:
                velo = pygame.Surface((tam, tam), pygame.SRCALPHA)
                velo.fill((40, 40, 70, 150))
                pantalla.blit(velo, (x, y))
            lista = cd <= 0 and not falta_mana
            pygame.draw.rect(pantalla, (255, 230, 120) if lista else (110, 110, 140), (x, y, tam, tam), 2,
                             border_radius=6)
            jg.texto(pantalla, str(i + 1), x + 5, y + 3, jg.f_peq, (255, 230, 120))
            jg.texto(pantalla, str(esp['coste']), x + tam - 5, y + tam - 20, jg.f_peq, (140, 190, 255), 'derecha')

    @staticmethod
    def _corazon(pantalla, x, y, lleno):
        col = (255, 80, 120) if lleno else (70, 60, 80)
        pygame.draw.circle(pantalla, col, (x - 7, y - 4), 8)
        pygame.draw.circle(pantalla, col, (x + 7, y - 4), 8)
        pygame.draw.polygon(pantalla, col, [(x - 15, y), (x + 15, y), (x, y + 16)])


# ----------------------------------------------------------------------
# Juego (menú, estados)
# ----------------------------------------------------------------------
class Juego:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Magos - Etapa 1")
        if WEB:
            self.pantalla = pygame.display.set_mode((ANCHO, ALTO))     # el navegador escala el lienzo
        else:
            try:
                self.pantalla = pygame.display.set_mode((ANCHO, ALTO), pygame.SCALED | pygame.RESIZABLE)
            except pygame.error:
                self.pantalla = pygame.display.set_mode((ANCHO, ALTO))
        self.reloj = pygame.time.Clock()
        self.f_gran = pygame.font.Font(None, 96)
        self.f_med = pygame.font.Font(None, 32)
        self.f_peq = pygame.font.Font(None, 26)
        self.f_tit = pygame.font.Font(None, 56)

        # fondos: se cargan bajo demanda (solo el que se usa) para ahorrar memoria, sobre todo en web
        self._fondo_i = -1
        self._fondo_tira = None

        self.anim_jugador = cargar_personaje("Wanderer_Magican", {
            'idle': ("Idle.png", 8), 'walk': ("Walk.png", 11), 'run': ("Run.png", 14),
            'jump': ("Jump.png", 10), 'attack': ("Attack_1.png", 20), 'cast': ("Attack_2.png", 18),
            'hurt': ("Hurt.png", 10), 'dead': ("Dead.png", 6)})
        self.anim_enemigos = {}
        for t, cfg in TIPOS_ENEMIGO.items():
            self.anim_enemigos[t] = cargar_personaje(cfg['carpeta'], cfg['anims'], cfg.get('ancla', ANCLA_X))

        # efectos de magias especiales e iconos de la barra de habilidades
        self.fx = cargar_efectos()
        self.iconos = [self._icono(self.fx['ola'][6]), self._icono(self.fx['nova'][5]),
                       self._icono(self.fx['rayo_b'][2])]

        self.estado = 'menu'
        self.nivel_sel = 0
        self.vidas = VIDAS_INICIALES
        self.puntos = 0
        self.escena = None
        self.t_menu = 0.0

    # --- utilidades
    def obtener_fondo(self, i):
        """Devuelve el fondo i (0-7) como tira espejada de 2x ancho (scroll continuo). Conserva solo el último."""
        if self._fondo_i != i:
            img = pygame.image.load(os.path.join(RUTA_FONDOS, f"fondo_{i + 1}.png")).convert()
            tira = pygame.Surface((ANCHO * 2, ALTO))
            tira.blit(img, (0, 0))
            tira.blit(pygame.transform.flip(img, True, False), (ANCHO, 0))
            self._fondo_tira, self._fondo_i = tira, i
        return self._fondo_tira

    @staticmethod
    def _icono(img, tam=46):
        """Reduce un cuadro de efecto a un icono cuadrado manteniendo la proporción."""
        k = min(tam / img.get_width(), tam / img.get_height())
        return pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)), max(1, int(img.get_height() * k))))

    def texto(self, pantalla, txt, x, y, fuente, color, alin='izq', alpha=255, sombra=True):
        if sombra:
            s = fuente.render(txt, True, (0, 0, 0))
            s.set_alpha(alpha)
            self._blit_alin(pantalla, s, x + 2, y + 2, alin)
        s = fuente.render(txt, True, color)
        s.set_alpha(alpha)
        self._blit_alin(pantalla, s, x, y, alin)

    @staticmethod
    def _blit_alin(pantalla, s, x, y, alin):
        r = s.get_rect()
        if alin == 'centro':
            r.midtop = (x, y)
        elif alin == 'derecha':
            r.topright = (x, y)
        else:
            r.topleft = (x, y)
        pantalla.blit(s, r)

    def velo(self, alpha=150):
        s = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        s.fill((0, 0, 0, alpha))
        self.pantalla.blit(s, (0, 0))

    def nueva_partida(self, nivel=0):
        self.vidas = VIDAS_INICIALES
        self.puntos = 0
        self.escena = Escena(self, nivel)
        self.estado = 'jugando'

    # --- bucle
    async def ejecutar(self):
        # 'await asyncio.sleep(0)' cede el control al navegador en cada cuadro (obligatorio en Pygbag;
        # en escritorio no tiene ningún efecto negativo).
        while True:
            dt = min(self.reloj.tick(FPS) / 1000.0, 1 / 30)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                self.evento(e)
            self.update(dt)
            self.dibujar()
            pygame.display.flip()
            await asyncio.sleep(0)

    def evento(self, e):
        if e.type != pygame.KEYDOWN and e.type != pygame.KEYUP:
            return
        if self.estado == 'menu' and e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_LEFT, pygame.K_a):
                self.nivel_sel = (self.nivel_sel - 1) % len(niveles.NIVELES)
            elif e.key in (pygame.K_RIGHT, pygame.K_d):
                self.nivel_sel = (self.nivel_sel + 1) % len(niveles.NIVELES)
            elif pygame.K_1 <= e.key <= pygame.K_8:
                self.nivel_sel = e.key - pygame.K_1
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.nueva_partida(self.nivel_sel)
            elif e.key == pygame.K_ESCAPE and not WEB:       # en el navegador no se "sale"
                pygame.quit()
                sys.exit()
        elif self.estado == 'jugando':
            self.escena.evento(e)
        elif self.estado == 'pausa' and e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_p, pygame.K_ESCAPE, pygame.K_RETURN):
                self.estado = 'jugando'
            elif e.key == pygame.K_m:
                self.estado = 'menu'
        elif self.estado == 'nivel_completo' and e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                sig = self.escena.indice + 1
                if sig >= len(niveles.NIVELES):
                    self.estado = 'victoria'
                else:
                    self.escena = Escena(self, sig)
                    self.estado = 'jugando'
        elif self.estado in ('game_over', 'victoria') and e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.estado = 'menu'

    def update(self, dt):
        self.t_menu += dt
        if self.estado == 'jugando':
            self.escena.update(dt)
        elif self.estado in ('nivel_completo', 'game_over', 'victoria', 'pausa') and self.escena:
            if self.estado != 'pausa':
                self.escena.particulas.update(dt)

    def dibujar(self):
        p = self.pantalla
        if self.estado == 'menu':
            self._menu(p)
            return
        self.escena.dibujar(p)
        if self.estado == 'pausa':
            self.velo(160)
            self.texto(p, "PAUSA", ANCHO // 2, 250, self.f_gran, BLANCO, 'centro')
            self.texto(p, "P / ESC: continuar      M: menu principal", ANCHO // 2, 360, self.f_med, (220, 220, 230), 'centro')
        elif self.estado == 'nivel_completo':
            self.velo(150)
            e = self.escena
            self.texto(p, "NIVEL COMPLETADO", ANCHO // 2, 190, self.f_gran, (255, 230, 120), 'centro')
            self.texto(p, e.nivel.nombre, ANCHO // 2, 270, self.f_tit, BLANCO, 'centro')
            self.texto(p, f"Cristales: {e.cristales}/{e.total_cristales}", ANCHO // 2, 340, self.f_med, (140, 230, 255), 'centro')
            self.texto(p, f"Enemigos derrotados: {e.matados}/{e.total_enemigos}", ANCHO // 2, 375, self.f_med, (255, 190, 120), 'centro')
            self.texto(p, f"Puntos: {self.puntos}", ANCHO // 2, 410, self.f_med, BLANCO, 'centro')
            self.texto(p, "ENTER para continuar", ANCHO // 2, 490, self.f_med, (220, 220, 230), 'centro')
        elif self.estado == 'game_over':
            self.velo(190)
            self.texto(p, "GAME OVER", ANCHO // 2, 230, self.f_gran, (255, 90, 90), 'centro')
            self.texto(p, f"Puntos: {self.puntos}", ANCHO // 2, 330, self.f_tit, BLANCO, 'centro')
            self.texto(p, "ENTER para volver al menu", ANCHO // 2, 420, self.f_med, (220, 220, 230), 'centro')
        elif self.estado == 'victoria':
            self.velo(170)
            self.texto(p, "VICTORIA", ANCHO // 2, 210, self.f_gran, (255, 230, 120), 'centro')
            self.texto(p, "Has completado la Etapa 1", ANCHO // 2, 300, self.f_tit, BLANCO, 'centro')
            self.texto(p, f"Puntos finales: {self.puntos}", ANCHO // 2, 360, self.f_tit, (140, 230, 255), 'centro')
            self.texto(p, "ENTER para volver al menu", ANCHO // 2, 450, self.f_med, (220, 220, 230), 'centro')

    def _menu(self, p):
        fondo = self.obtener_fondo(niveles.NIVELES[self.nivel_sel]().fondo - 1)
        ox = -int(self.t_menu * 25) % fondo.get_width()
        p.blit(fondo, (-ox, 0))
        p.blit(fondo, (fondo.get_width() - ox, 0))
        self.velo(90)
        self.texto(p, "MAGOS", ANCHO // 2, 90, self.f_gran, (255, 230, 120), 'centro')
        self.texto(p, "Etapa 1", ANCHO // 2, 170, self.f_tit, BLANCO, 'centro')
        # mago de adorno
        h = self.anim_jugador['idle']
        h.dibujar(p, h.frame_ciclo(self.t_menu), ANCHO // 2, 520, 1, 0)
        # selector de nivel
        nombre = niveles.NIVELES[self.nivel_sel]().nombre
        self.texto(p, "<   " + nombre + "   >", ANCHO // 2, 545, self.f_tit, BLANCO, 'centro')
        self.texto(p, "ENTER: jugar     A/D o flechas (o 1-8): elegir nivel" + ("" if WEB else "     ESC: salir"),
                   ANCHO // 2, 610, self.f_peq, (230, 230, 240), 'centro')
        self.texto(p, "Mover: A/D  |  Saltar: ESPACIO  |  Correr: SHIFT  |  Magia: J  |  Especiales: 1, 2, 3", ANCHO // 2, 640,
                   self.f_peq, (230, 230, 240), 'centro')


async def main():
    await Juego().ejecutar()


if __name__ == "__main__":
    asyncio.run(main())
