"""
Videojuego de plataformas con magos - Etapa 1 (4 niveles)

Ejecutar en PyCharm:  abrir esta carpeta como proyecto y correr main.py
Requiere:             pip install pygame

Controles
    A / D o flechas ..... mover
    SHIFT ............... correr
    ESPACIO / W / ARRIBA  saltar (mantener = salto mas alto)
    J / Z / X ........... lanzar magia
    P / ESC ............. pausa
    ENTER ............... confirmar
"""
import os
import sys
import math
import random

import pygame

import niveles
from niveles import TILE, FILAS

# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------
ANCHO, ALTO = 1280, 720
FPS = 60
BASE = os.path.dirname(os.path.abspath(__file__))
RUTA_PERS = os.path.join(BASE, "Datos", "Assents", "Personajes")
RUTA_FONDOS = os.path.join(BASE, "Datos", "Assents", "Fondos")

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

BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)


def signo(v):
    return (v > 0) - (v < 0)


# ----------------------------------------------------------------------
# Sprites y animaciones
# ----------------------------------------------------------------------
class Hoja:
    """Animación cargada desde una hoja de sprites horizontal (cuadros de 128 px)."""

    def __init__(self, ruta, fps):
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
        self.ancla_der = ANCLA_X * ESCALA
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


def cargar_personaje(carpeta, anims):
    return {nombre: Hoja(os.path.join(RUTA_PERS, carpeta, archivo), fps)
            for nombre, (archivo, fps) in anims.items()}


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

    # --- entrada
    def pulsar_salto(self):
        self.buffer_salto = 0.12

    def soltar_salto(self):
        if self.vy < -250:
            self.vy *= 0.5

    def lanzar(self):
        if self.vivo and self.cd_disparo <= 0 and self.herido <= 0:
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
        self.vx = -signo(origen_x - self.cx) * 260 or 260
        self.vy = -380
        return True

    def update(self, dt, teclas, mundo, proyectiles):
        self.t_anim += dt
        self.inv = max(0, self.inv - dt)
        self.cd_disparo = max(0, self.cd_disparo - dt)
        self.t_ataque = max(0, self.t_ataque - dt)
        self.buffer_salto = max(0, self.buffer_salto - dt)

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
TIPOS_ENEMIGO = {
    'F': dict(carpeta="Fire Wizard", color=(255, 150, 40), vel_proy=360, cd=2.0, dur=0.7,
              puntos=250, rango=520),
    'L': dict(carpeta="Lightning Mage", color=(120, 220, 255), vel_proy=500, cd=1.6, dur=0.8,
              puntos=250, rango=560),
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

        self.enemigos = [Enemigo(t, c, f, juego.anim_enemigos[t], self.nivel.hp_enemigos)
                         for t, c, f in self.nivel.enemigos]
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
        self.fondo = juego.fondos[self.nivel.fondo - 1]
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
                        if e.recibir_dano(p.dano, self.particulas):
                            self.matados += 1
                            self.juego.puntos += e.cfg['puntos']
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
        self.particulas.dibujar(pantalla, cam)
        self._hud(pantalla)

        # Dibujar controles táctiles encima del escenario.
        self.controles.dibujar(pantalla)

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
        jg.texto(pantalla, f"Vidas x{jg.vidas}", 20, 60, jg.f_med, BLANCO)
        jg.texto(pantalla, f"Cristales {self.cristales}/{self.total_cristales}", 20, 88, jg.f_med, (140, 230, 255))
        jg.texto(pantalla, f"Puntos {jg.puntos}", ANCHO - 20, 20, jg.f_med, BLANCO, 'derecha')
        jg.texto(pantalla, self.nivel.nombre, ANCHO - 20, 48, jg.f_peq, (230, 230, 240), 'derecha')
        jg.texto(pantalla, f"Magos {self.matados}/{self.total_enemigos}", ANCHO - 20, 72, jg.f_peq,
                 (255, 190, 120), 'derecha')
        if self.msg_pista > 0 and self.nivel.pista:
            a = min(1.0, self.msg_pista)
            jg.texto(pantalla, self.nivel.pista, ANCHO // 2, ALTO - 50, jg.f_med, BLANCO, 'centro', alpha=int(255 * a))

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
        try:
            self.pantalla = pygame.display.set_mode((ANCHO, ALTO), pygame.SCALED | pygame.RESIZABLE)
        except pygame.error:
            self.pantalla = pygame.display.set_mode((ANCHO, ALTO))
        self.reloj = pygame.time.Clock()
        self.f_gran = pygame.font.Font(None, 96)
        self.f_med = pygame.font.Font(None, 32)
        self.f_peq = pygame.font.Font(None, 26)
        self.f_tit = pygame.font.Font(None, 56)

        # fondos: se crean tiras espejadas (2x ancho) para el scroll continuo
        self.fondos = []
        for i in range(1, 5):
            img = pygame.image.load(os.path.join(RUTA_FONDOS, f"fondo_{i}.png")).convert()
            tira = pygame.Surface((ANCHO * 2, ALTO))
            tira.blit(img, (0, 0))
            tira.blit(pygame.transform.flip(img, True, False), (ANCHO, 0))
            self.fondos.append(tira)

        self.anim_jugador = cargar_personaje("Wanderer Magican", {
            'idle': ("Idle.png", 8), 'walk': ("Walk.png", 11), 'run': ("Run.png", 14),
            'jump': ("Jump.png", 10), 'attack': ("Attack_1.png", 20),
            'hurt': ("Hurt.png", 10), 'dead': ("Dead.png", 6)})
        self.anim_enemigos = {}
        for t, cfg in TIPOS_ENEMIGO.items():
            self.anim_enemigos[t] = cargar_personaje(cfg['carpeta'], {
                'idle': ("Idle.png", 8), 'walk': ("Walk.png", 9), 'attack': ("Attack_1.png", 10),
                'hurt': ("Hurt.png", 10), 'dead': ("Dead.png", 8)})

        self.estado = 'menu'
        self.nivel_sel = 0
        self.vidas = VIDAS_INICIALES
        self.puntos = 0
        self.escena = None
        self.t_menu = 0.0

    # --- utilidades
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
    def ejecutar(self):
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

    def evento(self, e):

        es_teclado = e.type in (
            pygame.KEYDOWN,
            pygame.KEYUP
        )

        es_tactil = e.type in (
            pygame.FINGERDOWN,
            pygame.FINGERMOTION,
            pygame.FINGERUP
        )

        if not es_teclado and not es_tactil:
            return

        if self.estado == 'menu':

            if e.type == pygame.KEYDOWN:

                if e.key in (pygame.K_LEFT, pygame.K_a):
                    self.nivel_sel = (
                                             self.nivel_sel - 1
                                     ) % len(niveles.NIVELES)

                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    self.nivel_sel = (
                                             self.nivel_sel + 1
                                     ) % len(niveles.NIVELES)

                elif pygame.K_1 <= e.key <= pygame.K_4:
                    self.nivel_sel = e.key - pygame.K_1

                elif e.key in (
                        pygame.K_RETURN,
                        pygame.K_KP_ENTER,
                        pygame.K_SPACE
                ):
                    self.nueva_partida(self.nivel_sel)

                elif e.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

        elif self.estado == 'jugando':

            self.escena.evento(e)

        elif self.estado == 'pausa':

            if e.type == pygame.KEYDOWN:

                if e.key in (
                        pygame.K_p,
                        pygame.K_ESCAPE,
                        pygame.K_RETURN
                ):
                    self.estado = 'jugando'

                elif e.key == pygame.K_m:
                    self.estado = 'menu'

        elif self.estado == 'nivel_completo':

            if e.type == pygame.KEYDOWN:

                if e.key in (
                        pygame.K_RETURN,
                        pygame.K_KP_ENTER,
                        pygame.K_SPACE
                ):

                    sig = self.escena.indice + 1

                    if sig >= len(niveles.NIVELES):
                        self.estado = 'victoria'

                    else:
                        self.escena = Escena(self, sig)
                        self.estado = 'jugando'

        elif self.estado in ('game_over', 'victoria'):

            if e.type == pygame.KEYDOWN:

                if e.key in (
                        pygame.K_RETURN,
                        pygame.K_KP_ENTER,
                        pygame.K_SPACE
                ):
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
            self.texto(p, f"Magos derrotados: {e.matados}/{e.total_enemigos}", ANCHO // 2, 375, self.f_med, (255, 190, 120), 'centro')
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
        fondo = self.fondos[self.nivel_sel]
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
        self.texto(p, "ENTER: jugar     A/D o flechas (o 1-4): elegir nivel     ESC: salir",
                   ANCHO // 2, 610, self.f_peq, (230, 230, 240), 'centro')
        self.texto(p, "Mover: A/D  |  Saltar: ESPACIO  |  Correr: SHIFT  |  Magia: J", ANCHO // 2, 640,
                   self.f_peq, (230, 230, 240), 'centro')


if __name__ == "__main__":
    Juego().ejecutar()
