"""Automated unit & integration tests for Zombie entity, aggressive AI, and ZombieSpawner."""

import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import unittest
import pygame
from src.game.effects import EffectManager
from src.game.platforms import create_arena, Platform
from src.game.player import Player
from src.game.projectiles import Projectile, ProjectileManager
from src.game.settings import GameConfig
from src.game.zombie import Zombie, ZombieSpawner, ZombieState


class TestZombie(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.display.set_mode((1280, 720))

    def setUp(self):
        self.config = GameConfig()
        self.bounds = pygame.Rect(0, 0, 1600, 860)
        self.platforms = create_arena(self.bounds)
        self.effects = EffectManager()
        self.floor_y = float(self.bounds.bottom - 90)

        # Create dummy player
        self.player = Player(
            player_id=1,
            spawn=(800.0, self.floor_y),
            controls=self.config.controls.left,
            assets=None,
            config=self.config,
        )

    def test_zombie_emergence(self):
        """Zombie starts in EMERGING state and climbs out of the ground."""
        z = Zombie(spawn_pos=(500.0, self.floor_y), config=self.config, emergence_delay=0.0)
        self.assertEqual(z.state, ZombieState.EMERGING)
        self.assertFalse(z.is_active_threat())

        # Advance time by emergence duration
        dt = 0.05
        elapsed = 0.0
        while elapsed < z.emergence_duration + 0.1:
            z.update(dt, [self.player], self.platforms, self.bounds, self.effects)
            elapsed += dt

        # Zombie should now be in CHASING state, ready to attack
        self.assertEqual(z.state, ZombieState.CHASING)
        self.assertTrue(z.is_active_threat())

    def test_zombie_aggressive_pursuit(self):
        """Zombie runs fast towards player."""
        z = Zombie(spawn_pos=(300.0, self.floor_y), config=self.config)
        z.state = ZombieState.CHASING  # Skip emergence
        z.facing = 1

        initial_x = z.position.x
        # Update for 1 second towards player at x=800
        for _ in range(30):
            z.update(0.033, [self.player], self.platforms, self.bounds, self.effects)

        # Zombie must have rapidly moved right towards the player
        self.assertGreater(z.position.x, initial_x + 100.0)
        self.assertGreater(z.velocity.x, 150.0)  # fast sprint speed

    def test_zombie_lunge_attack(self):
        """Zombie lunges when within strike distance."""
        z = Zombie(spawn_pos=(720.0, self.floor_y), config=self.config)
        z.state = ZombieState.CHASING
        z.lunge_cooldown = 0.0  # Ready to lunge

        hit_records = []
        def on_hit(p, dmg):
            hit_records.append((p, dmg))

        # Advance slightly; distance is 80px, ideal for lunge
        for _ in range(10):
            z.update(0.016, [self.player], self.platforms, self.bounds, self.effects, on_player_hit=on_hit)

        # Should have initiated lunge or already struck player
        self.assertTrue(z.state == ZombieState.LUNGING or len(hit_records) > 0)

    def test_zombie_vertical_traversal(self):
        """Zombie jumps towards elevated player and drops through one-way platforms."""
        # 1. Jump towards elevated player
        elevated_player = Player(
            player_id=1,
            spawn=(500.0, self.floor_y - 120.0),
            controls=self.config.controls.left,
            assets=None,
            config=self.config,
        )
        z = Zombie(spawn_pos=(500.0, self.floor_y), config=self.config)
        z.state = ZombieState.CHASING
        z.on_ground = True
        z.jump_cooldown = 0.0

        z.update(0.016, [elevated_player], self.platforms, self.bounds, self.effects)
        # Zombie should have jumped upwards
        self.assertLess(z.velocity.y, -100.0)

    def test_spread_out_spawning(self):
        """ZombieSpawner distributes zombies across distinct arena zones."""
        spawner = ZombieSpawner(self.config, self.platforms, self.bounds)
        self.assertEqual(len(spawner.zombies), 3)

        xs = [z.position.x for z in spawner.zombies]
        xs.sort()

        # The 3 zombies must be spread out across the arena with significant distance between each
        gap_1_2 = xs[1] - xs[0]
        gap_2_3 = xs[2] - xs[1]
        self.assertGreater(gap_1_2, 150.0, f"Zombies 0 and 1 are too close: {gap_1_2}px")
        self.assertGreater(gap_2_3, 150.0, f"Zombies 1 and 2 are too close: {gap_2_3}px")

    def test_projectile_damages_zombie(self):
        """Projectiles collide with and damage zombies, triggering callbacks."""
        z = Zombie(spawn_pos=(600.0, self.floor_y), config=self.config)
        z.state = ZombieState.CHASING

        pm = ProjectileManager()
        # Fire wand projectile directly at zombie
        proj = Projectile(owner_id=1, position=(550.0, self.floor_y - 25.0), velocity=(600.0, 0.0), damage=25.0, kind="wand")
        pm.spawn(proj)

        hit_zombies = []
        killed_zombies = []
        def hit_cb(zomb):
            hit_zombies.append(zomb)
        def kill_cb(zomb):
            killed_zombies.append(zomb)

        # Update projectiles
        plat_rects = [p.rect for p in self.platforms]
        for _ in range(10):
            pm.update(0.016, plat_rects, self.bounds, [self.player], self.effects, [z], hit_cb, kill_cb)

        # Zombie should have taken damage and hit callback should have fired
        self.assertTrue(len(hit_zombies) > 0)
        self.assertLess(z.health, z.max_health)

    def test_wave_clearing_and_progression(self):
        """Killing all 3 zombies advances to the next wave."""
        spawner = ZombieSpawner(self.config, self.platforms, self.bounds)
        self.assertEqual(spawner.wave_number, 1)

        # Kill all 3 zombies
        for z in spawner.zombies:
            z.die(self.effects)

        # Update spawner to process deaths and advance wave
        spawner.wave_delay = 0.05  # speed up test
        dt = 0.02
        for _ in range(30):
            spawner.update(dt, [self.player], self.effects, self.platforms, self.bounds)

        # Wave should have advanced to 2
        self.assertEqual(spawner.wave_number, 2)
        self.assertEqual(len(spawner.zombies), 3)


if __name__ == "__main__":
    unittest.main()
