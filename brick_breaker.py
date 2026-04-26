#!/usr/bin/env python3
"""
Brick Breaker
  ← / → or A / D  — move paddle
  SPACE            — launch ball / confirm screen
  ESC              — quit

Requires: pip install pygame
"""

import pygame
import sys
import math
import random

# ── Window ───────────────────────────────────────────────────────────────────
W, H   = 800, 600
FPS    = 60
HUD_H  = 55

# ── Paddle ───────────────────────────────────────────────────────────────────
PAD_W, PAD_H = 110, 14
PAD_SPEED    = 9
PAD_Y        = H - 52

# ── Ball ─────────────────────────────────────────────────────────────────────
BALL_R     = 8
BASE_SPEED = 5.5

# ── Bricks ───────────────────────────────────────────────────────────────────
COLS    = 11
BRK_W   = (W - 80) // COLS
BRK_H   = 24
BRK_PAD = 5
BRK_TOP = HUD_H + 18

# (base_color, max_hp, destroy_points)
ROW_META = [
    ((255,  55,  55), 1,  10),   # red
    ((255, 145,  35), 1,  20),   # orange
    ((245, 215,  25), 1,  30),   # yellow
    (( 55, 205,  75), 1,  40),   # green
    (( 55, 125, 255), 2,  75),   # blue   (2 HP)
    ((175,  55, 255), 3, 150),   # purple (3 HP)
]

MAX_LIVES = 3

# ── Colours ──────────────────────────────────────────────────────────────────
DARK_BG = ( 10,  10,  25)
HUD_BG  = ( 18,  18,  42)
WHITE   = (255, 255, 255)


# ─────────────────────────────────────────────────────────────────────────────
# Particle
# ─────────────────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color):
        self.x, self.y = float(x), float(y)
        self.color     = color
        a              = random.uniform(0, math.tau)
        s              = random.uniform(1.5, 6.0)
        self.vx, self.vy = math.cos(a) * s, math.sin(a) * s
        self.life = self.max_life = random.randint(18, 40)
        self.size = random.uniform(1.5, 4.5)

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vy += 0.18
        self.life -= 1

    def draw(self, surf):
        t = self.life / self.max_life
        c = tuple(int(v * t) for v in self.color)
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)),
                           max(1, int(self.size * t)))


# ─────────────────────────────────────────────────────────────────────────────
# PowerUp
# ─────────────────────────────────────────────────────────────────────────────
PU_DEFS = [
    ("WIDE", (60,  180, 255), "W"),   # wider paddle
    ("SLOW", (60,  230, 100), "S"),   # slower ball
    ("LIFE", (255,  80,  80), "+1"),  # extra life
]

class PowerUp:
    def __init__(self, x, y):
        self.kind, self.color, self.label = random.choice(PU_DEFS)
        self.x, self.y = float(x), float(y)
        self.vy   = 2.2
        self.alive = True
        self.rect  = pygame.Rect(0, 0, 38, 20)
        self.rect.center = (int(x), int(y))
        self.age = 0

    def update(self):
        self.y += self.vy
        self.rect.centery = int(self.y)
        self.age += 1
        if self.y > H + 10:
            self.alive = False

    def draw(self, surf, font):
        pulse = 0.75 + 0.25 * math.sin(self.age * 0.15)
        c = tuple(int(v * pulse) for v in self.color)
        pygame.draw.rect(surf, c, self.rect, border_radius=10)
        pygame.draw.rect(surf, WHITE, self.rect, 1, border_radius=10)
        t = font.render(self.label, True, WHITE)
        surf.blit(t, t.get_rect(center=self.rect.center))


# ─────────────────────────────────────────────────────────────────────────────
# Brick
# ─────────────────────────────────────────────────────────────────────────────
class Brick:
    def __init__(self, col, row):
        x = 40 + col * BRK_W
        y = BRK_TOP + row * BRK_H
        self.rect = pygame.Rect(x, y, BRK_W - BRK_PAD, BRK_H - BRK_PAD)
        self.base_color, self.max_hp, self.points = ROW_META[row % len(ROW_META)]
        self.hp    = self.max_hp
        self.alive = True
        self.flash = 0

    def hit(self):
        self.hp   -= 1
        self.flash = 6
        if self.hp <= 0:
            self.alive = False

    def _color(self):
        if self.flash > 0:
            self.flash -= 1
            return WHITE
        t = self.hp / self.max_hp
        f = 0.35 + 0.65 * t
        return tuple(int(v * f) for v in self.base_color)

    def draw(self, surf):
        c = self._color()
        pygame.draw.rect(surf, c, self.rect, border_radius=4)
        hi = pygame.Rect(self.rect.x + 3, self.rect.y + 3, self.rect.width - 6, 4)
        hc = tuple(min(255, v + 70) for v in c)
        pygame.draw.rect(surf, hc, hi, border_radius=2)


# ─────────────────────────────────────────────────────────────────────────────
# Ball
# ─────────────────────────────────────────────────────────────────────────────
class Ball:
    TRAIL = 14

    def __init__(self, speed=BASE_SPEED):
        self.speed  = speed
        self.trail  = []
        self.active = False
        self.x = float(W // 2)
        self.y = float(PAD_Y - BALL_R - 2)
        angle   = math.radians(random.uniform(-145, -35))
        self.vx = math.cos(angle) * speed
        self.vy = -abs(math.sin(angle) * speed)

    def snap_to(self, cx):
        if not self.active:
            self.x = float(cx)

    def launch(self):
        self.active = True

    def update(self, pad_rect, bricks, particles):
        """Returns (score_delta, lost:bool, destroyed_centers:list)."""
        if not self.active:
            return 0, False, []

        self.trail.append((int(self.x), int(self.y)))
        if len(self.trail) > self.TRAIL:
            self.trail.pop(0)

        self.x += self.vx
        self.y += self.vy

        # Normalise speed
        spd = math.hypot(self.vx, self.vy)
        if spd:
            self.vx = self.vx / spd * self.speed
            self.vy = self.vy / spd * self.speed

        # Walls
        if self.x - BALL_R <= 0:
            self.x = BALL_R + 1;  self.vx = abs(self.vx)
        elif self.x + BALL_R >= W:
            self.x = W - BALL_R - 1;  self.vx = -abs(self.vx)
        if self.y - BALL_R <= HUD_H:
            self.y = HUD_H + BALL_R + 1;  self.vy = abs(self.vy)

        # Paddle
        br = pygame.Rect(int(self.x) - BALL_R, int(self.y) - BALL_R,
                         BALL_R * 2, BALL_R * 2)
        if br.colliderect(pad_rect) and self.vy > 0:
            norm    = ((self.x - pad_rect.left) / pad_rect.width - 0.5) * 2
            deflect = norm * math.radians(65)
            self.vx = math.sin(deflect) * self.speed
            self.vy = -abs(math.cos(deflect) * self.speed)
            self.y  = pad_rect.top - BALL_R - 1

        # Bricks
        score     = 0
        destroyed = []
        br = pygame.Rect(int(self.x) - BALL_R, int(self.y) - BALL_R,
                         BALL_R * 2, BALL_R * 2)
        for brick in bricks:
            if not brick.alive or not br.colliderect(brick.rect):
                continue
            was_dead = brick.hp == 1
            brick.hit()
            score += brick.points if not brick.alive else 5
            n = 12 if not brick.alive else 4
            for _ in range(n):
                particles.append(Particle(brick.rect.centerx,
                                           brick.rect.centery,
                                           brick.base_color))
            if not brick.alive:
                destroyed.append((brick.rect.centerx, brick.rect.centery))

            # Bounce side via minimum overlap
            ol  = br.right  - brick.rect.left
            or_ = brick.rect.right - br.left
            ot  = br.bottom - brick.rect.top
            ob  = brick.rect.bottom - br.top
            mv  = min(ol, or_, ot, ob)
            if mv == ot and self.vy > 0:
                self.vy = -abs(self.vy);  self.y = brick.rect.top  - BALL_R - 1
            elif mv == ob and self.vy < 0:
                self.vy =  abs(self.vy);  self.y = brick.rect.bottom + BALL_R + 1
            elif mv == ol and self.vx > 0:
                self.vx = -abs(self.vx);  self.x = brick.rect.left  - BALL_R - 1
            else:
                self.vx =  abs(self.vx);  self.x = brick.rect.right  + BALL_R + 1
            break

        # Prevent horizontal lock
        if abs(self.vy) < 0.6:
            self.vy = math.copysign(0.6, self.vy)
            spd = math.hypot(self.vx, self.vy)
            if spd:
                self.vx = self.vx / spd * self.speed
                self.vy = self.vy / spd * self.speed

        lost = self.y > H + 30
        return score, lost, destroyed

    def draw(self, surf):
        n = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            t = (i + 1) / (n + 1)
            r = max(1, int(BALL_R * t * 0.7))
            c = (int(255 * t), int(190 * t), int(50 * t))
            pygame.draw.circle(surf, c, (tx, ty), r)
        pygame.draw.circle(surf, (255, 235, 80), (int(self.x), int(self.y)), BALL_R)
        pygame.draw.circle(surf, WHITE, (int(self.x) - 2, int(self.y) - 3), 2)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def make_bricks(level):
    rows = min(3 + level, len(ROW_META))
    return [Brick(col, row) for row in range(rows) for col in range(COLS)]


def draw_hud(surf, score, lives, level, hi, font, sfont, wide_t, slow_t):
    pygame.draw.rect(surf, HUD_BG, (0, 0, W, HUD_H))
    pygame.draw.line(surf, (50, 50, 100), (0, HUD_H), (W, HUD_H), 1)

    surf.blit(font.render(f"SCORE  {score:>6}", True, WHITE), (16, 13))

    cx = W // 2
    ht = sfont.render(f"BEST {hi:>6}", True, (140, 140, 190))
    surf.blit(ht, (cx - ht.get_width() // 2, 8))

    # active power-up indicators
    puw = []
    if wide_t > 0: puw.append(f"W:{wide_t//FPS+1}s")
    if slow_t > 0: puw.append(f"S:{slow_t//FPS+1}s")
    if puw:
        pt = sfont.render("  ".join(puw), True, (80, 230, 130))
        surf.blit(pt, (cx - pt.get_width() // 2, 30))

    surf.blit(font.render(f"LV {level}", True, (80, 210, 255)), (W - 115, 13))

    for i in range(lives):
        cx2 = W - 28 - i * 18
        pygame.draw.circle(surf, (255, 230, 60), (cx2, 43), 6)
        pygame.draw.circle(surf, (180, 150,  0), (cx2, 43), 6, 1)


def draw_overlay(surf, bfont, font, title, subtitle, tc):
    ov = pygame.Surface((W, H), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 160))
    surf.blit(ov, (0, 0))
    t = bfont.render(title, True, tc)
    surf.blit(t, (W // 2 - t.get_width() // 2, H // 2 - 70))
    if subtitle:
        s = font.render(subtitle, True, (210, 210, 210))
        surf.blit(s, (W // 2 - s.get_width() // 2, H // 2 + 10))


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def _focus_window():
    """Force the pygame window to the foreground on Windows."""
    try:
        import ctypes
        hwnd = pygame.display.get_wm_info()["window"]
        ctypes.windll.user32.ShowWindow(hwnd, 9)        # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Brick Breaker")
    clock = pygame.time.Clock()
    _focus_window()   # grab keyboard focus away from the terminal

    font  = pygame.font.SysFont("consolas", 22, bold=True)
    sfont = pygame.font.SysFont("consolas", 16)
    bfont = pygame.font.SysFont("consolas", 54, bold=True)
    pfont = pygame.font.SysFont("consolas", 13, bold=True)

    # Static star field
    stars = [(random.randint(0, W), random.randint(HUD_H, H),
              random.random()) for _ in range(90)]

    hi_score = 0

    # ── Game state ────────────────────────────────────────────────────────
    # states: READY  PLAYING  LEVEL_CLEAR  GAME_OVER
    def new_game():
        nonlocal state, level, score, lives, ball_speed
        nonlocal bricks, ball, particles, powerups
        nonlocal pad_rect, wide_timer, slow_timer
        level       = 1
        score       = 0
        lives       = MAX_LIVES
        ball_speed  = BASE_SPEED
        bricks      = make_bricks(level)
        ball        = Ball(ball_speed)
        particles   = []
        powerups    = []
        pad_rect    = pygame.Rect(W // 2 - PAD_W // 2, PAD_Y, PAD_W, PAD_H)
        wide_timer  = 0
        slow_timer  = 0
        state       = "READY"

    state      = "READY"
    level      = 1
    score      = 0
    lives      = MAX_LIVES
    ball_speed = BASE_SPEED
    bricks     = make_bricks(level)
    ball       = Ball(ball_speed)
    particles  = []
    powerups   = []
    pad_rect   = pygame.Rect(W // 2 - PAD_W // 2, PAD_Y, PAD_W, PAD_H)
    wide_timer = 0
    slow_timer = 0

    space_was_down = False
    running = True
    while running:
        clock.tick(FPS)

        # ── Events ────────────────────────────────────────────────────────
        confirm_event = False
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    running = False
                elif ev.key in (pygame.K_SPACE, pygame.K_RETURN):
                    confirm_event = True
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                confirm_event = True   # left-click also confirms

        # SPACE/ENTER via get_pressed edge-detection (reliable even when
        # the terminal briefly holds focus on Windows startup)
        keys = pygame.key.get_pressed()
        space_now      = bool(keys[pygame.K_SPACE] or keys[pygame.K_RETURN])
        space_pressed  = confirm_event or (space_now and not space_was_down)
        space_was_down = space_now

        if space_pressed:
            if state == "READY":
                ball.launch()
                state = "PLAYING"
            elif state == "LEVEL_CLEAR":
                level      += 1
                ball_speed *= 1.06
                bricks      = make_bricks(level)
                ball        = Ball(ball_speed)
                powerups    = []
                wide_timer  = 0
                slow_timer  = 0
                state       = "READY"
            elif state == "GAME_OVER":
                new_game()

        # ── Update ────────────────────────────────────────────────────────
        if state in ("READY", "PLAYING"):
            # Paddle width from power-up
            current_pad_w = PAD_W + (50 if wide_timer > 0 else 0)
            pad_rect.width = current_pad_w

            if keys[pygame.K_LEFT]  or keys[pygame.K_a]:
                pad_rect.x -= PAD_SPEED
            if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                pad_rect.x += PAD_SPEED
            pad_rect.x = max(0, min(W - current_pad_w, pad_rect.x))

            # Apply slow power-up
            ball.speed = (ball_speed * 0.55) if slow_timer > 0 else ball_speed

            ball.snap_to(pad_rect.centerx)
            gained, lost, destroyed = ball.update(pad_rect, bricks, particles)
            score    += gained
            hi_score  = max(hi_score, score)

            # Spawn power-ups from destroyed bricks
            for cx, cy in destroyed:
                if random.random() < 0.28:
                    powerups.append(PowerUp(cx, cy))

            # Power-up physics + catch
            for pu in powerups:
                pu.update()
                if pu.alive and pu.rect.colliderect(pad_rect):
                    pu.alive = False
                    if pu.kind == "WIDE":
                        wide_timer = 360
                    elif pu.kind == "SLOW":
                        slow_timer = 360
                    elif pu.kind == "LIFE" and lives < MAX_LIVES + 2:
                        lives += 1
                        for _ in range(20):
                            particles.append(Particle(pu.rect.centerx,
                                                       pu.rect.centery,
                                                       (255, 80, 80)))
            powerups = [p for p in powerups if p.alive]

            # Timers
            wide_timer = max(0, wide_timer - 1)
            slow_timer = max(0, slow_timer - 1)

            if lost:
                lives -= 1
                for _ in range(22):
                    particles.append(Particle(ball.x, ball.y, (255, 80, 80)))
                if lives <= 0:
                    state = "GAME_OVER"
                else:
                    ball       = Ball(ball_speed)
                    wide_timer = 0
                    slow_timer = 0
                    state      = "READY"

            elif all(not b.alive for b in bricks):
                state = "LEVEL_CLEAR"

        # Particles
        for p in particles:
            p.update()
        particles = [p for p in particles if p.life > 0]

        # ── Draw ──────────────────────────────────────────────────────────
        screen.fill(DARK_BG)

        for sx, sy, sb in stars:
            v = int(35 + 75 * sb)
            pygame.draw.circle(screen, (v, v, v + 25), (sx, sy), 1)

        for b in bricks:
            if b.alive:
                b.draw(screen)

        for pu in powerups:
            pu.draw(screen, pfont)

        # Paddle
        pygame.draw.rect(screen, (75, 165, 255), pad_rect, border_radius=7)
        shin = pygame.Rect(pad_rect.x + 4, pad_rect.y + 2,
                           pad_rect.width - 8, 4)
        pygame.draw.rect(screen, (180, 220, 255), shin, border_radius=3)

        ball.draw(screen)

        for p in particles:
            p.draw(screen)

        draw_hud(screen, score, lives, level, hi_score,
                 font, sfont, wide_timer, slow_timer)

        if state == "READY":
            draw_overlay(screen, bfont, font,
                         "READY?",
                         "← / → move   SPACE / click to launch   ESC quit",
                         (255, 235, 60))
        elif state == "LEVEL_CLEAR":
            draw_overlay(screen, bfont, font,
                         f"LEVEL {level} CLEAR!",
                         "SPACE  →  next level",
                         (60, 230, 100))
        elif state == "GAME_OVER":
            draw_overlay(screen, bfont, font,
                         "GAME  OVER",
                         f"Score: {score:,}    SPACE to retry",
                         (255, 70, 70))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
