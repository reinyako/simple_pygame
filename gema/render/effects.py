"""Efek layar: vignette yang menyempit mengikuti stres, film grain, dan fade hitam."""

import numpy as np
import pygame

from .. import config as C

VIGNETTE_LEVELS = 6


def _vignette(level):
    w, h = C.SCREEN_W // 4, C.SCREEN_H // 4
    y, x = np.ogrid[:h, :w]
    nx = (x - w / 2 + 0.5) / (w / 2)
    ny = (y - h / 2 + 0.5) / (h / 2)
    d = np.sqrt(nx * nx + ny * ny) / np.sqrt(2)
    inner = 0.52 - 0.075 * level
    strength = 150 + 20 * level
    alpha = (np.clip((d - inner) / (1.0 - inner), 0, 1) ** 1.4) * strength
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    px = pygame.surfarray.pixels_alpha(surf)
    px[:] = alpha.T.astype(np.uint8)
    del px
    return pygame.transform.smoothscale(surf, (C.SCREEN_W, C.SCREEN_H))


def _grain(rng):
    w, h = C.SCREEN_W // 2, C.SCREEN_H // 2
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((210, 205, 195, 0))
    px = pygame.surfarray.pixels_alpha(surf)
    px[:] = (rng.random((w, h)) ** 6 * 18).astype(np.uint8)
    del px
    return pygame.transform.scale(surf, (C.SCREEN_W, C.SCREEN_H))


class Effects:
    def __init__(self, seed=3):
        rng = np.random.default_rng(seed)
        self.vignettes = [_vignette(k) for k in range(VIGNETTE_LEVELS)]
        self.grains = [_grain(rng) for _ in range(4)]
        self.black = pygame.Surface((C.SCREEN_W, C.SCREEN_H))
        self.black.fill((0, 0, 0))

    def vignette(self, screen, stress):
        level = min(VIGNETTE_LEVELS - 1, int(stress / 100.0 * VIGNETTE_LEVELS))
        screen.blit(self.vignettes[level], (0, 0))

    def grain(self, screen, t):
        screen.blit(self.grains[int(t * 12) % len(self.grains)], (0, 0))

    def fade(self, screen, amount):
        if amount <= 0:
            return
        self.black.set_alpha(int(255 * min(1.0, amount)))
        screen.blit(self.black, (0, 0))
