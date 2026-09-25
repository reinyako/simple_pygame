"""Scene bermain: menjalankan satu lantai, menu jeda, kematian, dan pindah lantai."""

import math
import random

import pygame

from .. import config as C
from .. import notes
from ..audio.soundscape import Soundscape
from ..render.draw import FloorRenderer
from ..render.text import TypeText, draw_center, draw_left, font, wrap
from ..world.floor import Floor
from .interlude import InterludeScene
from .menu import Menu

PLAYING = "main"
DYING = "mati"
LEAVING = "keluar"


class PlayScene:
    def __init__(self, app, run):
        self.app = app
        self.run = run
        self.floor = Floor(run, C.floor_rules(run.floor, run.difficulty))
        self.floor.invulnerable = app.invulnerable
        self.renderer = FloorRenderer(self.floor)
        self.soundscape = Soundscape(app.audio)
        self.controller = app.make_controller()
        self.rng = random.Random(run.seed ^ 0x5EED)
        self.state = PLAYING
        self.timer = 0.0
        self.t = 0.0
        self.thud_played = False
        self.paused = False
        self.showing_notes = False
        self.pause_menu = Menu(["Lanjut", "Catatan", "Kembali ke judul"], y=190)
        self.note = None
        self.hint = 9.0 if run.floor == 1 else 0.0
        self.debug = app.args.debug
        p = self.floor.player
        self.cam = (p.x - C.SCREEN_W / 2, p.y - C.SCREEN_H / 2)
        app.save.record_floor(run.difficulty.key, min(run.floor, C.FLOOR_COUNT))

    def enter(self):
        pygame.mouse.set_visible(self.paused)

    def aim_at(self, mouse_pos):
        p = self.floor.player
        wx, wy = mouse_pos[0] + self.cam[0], mouse_pos[1] + self.cam[1]
        if math.hypot(wx - p.x, wy - p.y) < 2:
            return p.aim
        return math.atan2(wy - p.y, wx - p.x)

    # --- event -------------------------------------------------------------
    def set_paused(self, paused):
        self.paused = paused
        self.showing_notes = False
        pygame.mouse.set_visible(paused)
        if paused:
            self.app.audio.pause()
        else:
            self.app.audio.unpause()

    def handle_event(self, ev):
        if self.paused:
            self._pause_event(ev)
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE and self.state == PLAYING:
                self.set_paused(True)
                return
            if ev.key == pygame.K_F3:
                self.debug = not self.debug
            if self.app.args.debug and self.state == PLAYING:
                if ev.key == pygame.K_F5:
                    self.floor.debug_collect_all()
                elif ev.key == pygame.K_F6:
                    self.floor.debug_to_exit()
        self.controller.handle_event(ev)

    def _pause_event(self, ev):
        if self.showing_notes:
            done = ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE)
            if done or (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1):
                self.showing_notes = False
            return
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.set_paused(False)
            return
        choice = self.pause_menu.handle_event(ev)
        if choice == 0:
            self.set_paused(False)
        elif choice == 1:
            self.showing_notes = True
        elif choice == 2:
            self.app.audio.unpause()
            self.app.go_title()

    # --- update ------------------------------------------------------------
    def update(self, dt):
        if self.paused:
            return
        self.t += dt
        if self.state == DYING:
            self.timer += dt
            if self.timer >= C.DEATH_FADE and not self.thud_played:
                self.thud_played = True
                self.app.audio.play("thud")
            if self.timer >= C.DEATH_FADE + 1.1:
                self._after_death()
            return
        if self.state == LEAVING:
            self.timer += dt
            if self.timer >= C.EXIT_FADE:
                self._leave()
            return

        f = self.floor
        f.update(dt, self.controller.sample(self))
        for ev in f.events:
            if ev[0] == "note":
                self.note = TypeText(ev[1])
                self.run.notes.append(ev[1])
            elif ev[0] == "death":
                self._die()
            elif ev[0] == "exit":
                self.state = LEAVING
                self.timer = 0.0
        f.events.clear()
        if self.state == PLAYING:
            self.soundscape.update(dt, f)
        if self.note is not None:
            self.note.update(dt)
            if self.note.done:
                self.note = None
        self.hint = max(0.0, self.hint - dt)
        self._update_camera()

    def _update_camera(self):
        f = self.floor
        p = f.player
        sx = sy = 0.0
        s = f.stress.value
        if f.rules.tricks and s >= C.SWAY_STRESS:
            amp = (s - C.SWAY_STRESS) / (100 - C.SWAY_STRESS) * 3.0
            sx = math.sin(self.t * 0.9) * amp
            sy = math.cos(self.t * 0.7) * amp
        self.cam = (p.x - C.SCREEN_W / 2 + sx, p.y - C.SCREEN_H / 2 + sy)

    def _die(self):
        self.state = DYING
        self.timer = 0.0
        self.thud_played = False
        self.note = None
        self.soundscape.silence()
        self.run.lives -= 1
        self.run.deaths += 1
        self.app.save.kematian += 1
        self.app.save.write()

    def _after_death(self):
        run, app = self.run, self.app
        if run.lives <= 0:
            app.switch(InterludeScene(
                app, [f"Percobaan ke-{run.attempt} berakhir."], then=app.go_title, duration=3.2, size=22,
            ))
            return
        self.floor.respawn()
        self.state = PLAYING
        self.t = 0.0
        app.switch(InterludeScene(
            app, [self.rng.choice(notes.DEATH_WORDS)], then=lambda: app.switch(self),
            duration=1.8, lives=run.lives, max_lives=run.difficulty.lives,
        ))

    def _leave(self):
        from .ending import EndingScene

        self.app.audio.stop_all()
        self.run.battery = self.floor.flashlight.battery
        if self.floor.rules.final:
            self.app.switch(EndingScene(self.app, self.run))
            return
        self.run.floor += 1
        self.app.go_floor_intro(self.run)

    # --- gambar ------------------------------------------------------------
    def draw(self, screen):
        f = self.floor
        self.renderer.draw(screen, self.cam[0], self.cam[1], self.t)
        fx = self.app.effects
        fx.grain(screen, self.t)
        fx.vignette(screen, f.stress.value)

        if self.note is not None:
            self.note.draw(screen, C.SCREEN_W / 2, C.SCREEN_H - 96)
        if self.hint > 0:
            self._draw_hint(screen, min(1.0, self.hint / 2.0) * min(1.0, (9.0 - self.hint) / 1.5))
        if not self.paused and self.state == PLAYING:
            mx, my = pygame.mouse.get_pos()
            pygame.draw.circle(screen, (90, 86, 80), (mx, my), 3, 1)

        fade = max(0.0, 1.0 - self.t / 0.8)
        if self.state == DYING:
            fade = min(1.0, self.timer / C.DEATH_FADE)
        elif self.state == LEAVING:
            fade = min(1.0, self.timer / C.EXIT_FADE)
        fx.fade(screen, fade)

        if self.debug:
            self.renderer.draw_debug(screen, self.app.clock.get_fps())
        if self.paused:
            self._draw_pause(screen)

    def _draw_hint(self, screen, k):
        fnt = font(14)
        a = 255 * k * 0.8
        y = C.SCREEN_H - 30 - len(notes.CONTROLS[:5]) * 18
        for key, what in notes.CONTROLS[:5]:
            draw_left(screen, f"{key:<18} {what}", fnt, C.COL_TEXT_DIM, 24, y, a)
            y += 18

    def _draw_pause(self, screen):
        shade = pygame.Surface((C.SCREEN_W, C.SCREEN_H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 200))
        screen.blit(shade, (0, 0))
        if self.showing_notes:
            self._draw_notes(screen)
            return
        draw_center(screen, "Jeda", font(28), C.COL_TEXT, C.SCREEN_W / 2, 90)
        lives = self.run.lives
        max_lives = self.run.difficulty.lives
        gap = 18
        x0 = C.SCREEN_W / 2 - (max_lives - 1) * gap / 2
        for i in range(max_lives):
            color = C.COL_TEXT if i < lives else (60, 57, 53)
            pygame.draw.circle(screen, color, (int(x0 + i * gap), 146), 4 if i < lives else 3, 0 if i < lives else 1)
        self.pause_menu.draw(screen)
        fnt = font(13)
        y = 350
        for key, what in notes.CONTROLS:
            draw_center(screen, f"{key}: {what}", fnt, C.COL_TEXT_DIM, C.SCREEN_W / 2, y)
            y += 18

    def _draw_notes(self, screen):
        draw_center(screen, "Catatan", font(24), C.COL_TEXT, C.SCREEN_W / 2, 50)
        fnt = font(16, italic=True)
        y = 100
        if not self.run.notes:
            draw_center(screen, "Belum ada.", fnt, C.COL_TEXT_DIM, C.SCREEN_W / 2, y)
        for text in self.run.notes:
            for line in wrap(text, fnt, 780):
                y += draw_center(screen, line, fnt, C.COL_TEXT, C.SCREEN_W / 2, y)
            y += 8
        draw_center(screen, "Esc: kembali", font(13), C.COL_TEXT_DIM, C.SCREEN_W / 2, C.SCREEN_H - 36)
