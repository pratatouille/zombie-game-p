"""Player entity with responsive, crisp basic movement, smooth jumping, and expressive procedural animations."""

from __future__ import annotations
import math
import random
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from src.game.assets import AssetManager
    from src.game.camera import Camera
    from src.game.effects import EffectManager
    from src.game.items import Item
    from src.game.projectiles import Projectile
    from src.game.settings import GameConfig


class Player:
    """Stickman wizard player with smooth, responsive movement, reliable jumping, and lively animations."""

    def __init__(
        self,
        player_id: int,
        spawn: tuple[float, float],
        controls: dict[str, int],
        assets: AssetManager,
        config: GameConfig,
    ) -> None:
        self.player_id: int = player_id
        self.spawn: tuple[float, float] = spawn
        self.controls: dict[str, int] = controls
        self.assets: AssetManager = assets
        self.config: GameConfig = config

        # Public state required by CONTEXT.md
        self.facing: int = 1 if player_id == 1 else -1
        self.health: float = float(config.player_health)
        self.velocity: pygame.Vector2 = pygame.Vector2(0.0, 0.0)
        self.held_item: Item | None = None
        self.on_ground: bool = True

        # Dimensions & position
        self.width: int = 24
        self.height: int = 54
        self.position: pygame.Vector2 = pygame.Vector2(spawn[0], spawn[1])
        self.prev_bottom: float = self.position.y

        # Platforming controls & feel
        self.jump_buffer: float = 0.0      # Buffer window (150ms)
        self.coyote_timer: float = 0.0     # Ledge grace window (120ms)
        self.drop_timer: float = 0.0       # Drop through one-way platform window (280ms)
        self.is_dropping_down: bool = False
        self._jump_held: bool = False
        self._attack_held: bool = False
        self._move_input: int = 0

        # Visuals & Procedural Animation
        self.anim_time: float = random.uniform(0.0, 6.28)
        self.run_cycle: float = 0.0
        self.squash_stretch: pygame.Vector2 = pygame.Vector2(1.0, 1.0)
        self.damage_flash: float = 0.0
        self.shield_timer: float = 0.0
        self.attack_recoil: float = 0.0
        self._punch_cooldown: float = 0.0

        # 3-segment trailing scarf nodes
        self.scarf_nodes: list[pygame.Vector2] = [
            pygame.Vector2(spawn[0] - self.facing * 8, spawn[1] - 44),
            pygame.Vector2(spawn[0] - self.facing * 18, spawn[1] - 40),
            pygame.Vector2(spawn[0] - self.facing * 28, spawn[1] - 38),
        ]

    def bounds(self) -> pygame.Rect:
        """World bounding box for collision detection."""
        return pygame.Rect(
            int(self.position.x - self.width / 2),
            int(self.position.y - self.height),
            self.width,
            self.height,
        )

    def center(self) -> tuple[float, float]:
        """Center coordinates of player."""
        return (self.position.x, self.position.y - self.height / 2)

    def alive(self) -> bool:
        """Check if player still has health."""
        return self.health > 0

    def equip(self, item: Item | None) -> None:
        """Equip an item (or unequip by passing None)."""
        self.held_item = item

    def activate_shield(self, duration: float = 6.0) -> None:
        """Activate protective robe shield status."""
        self.shield_timer = duration

    def heal(self, amount: float) -> None:
        """Heal player, clamped to max health."""
        self.health = min(float(self.config.player_health), self.health + amount)

    def take_damage(self, amount: float, knockback: tuple[float, float] = (0, 0)) -> None:
        """Take damage with defense calculations and apply knockback."""
        if not self.alive():
            return

        final_dmg = amount
        kb_factor = 1.0

        if self.shield_timer > 0:
            final_dmg *= 0.28
            kb_factor = 0.45

        self.health = max(0.0, self.health - final_dmg)
        self.damage_flash = 0.25
        self.squash_stretch = pygame.Vector2(1.35, 0.75)

        self.velocity.x += knockback[0] * kb_factor
        self.velocity.y += knockback[1] * kb_factor
        self.on_ground = False

    def handle_event(self, event: pygame.event.Event) -> None:
        """Process keyboard events."""
        if event.type == pygame.KEYDOWN:
            if event.key == self.controls.get("jump"):
                self.jump_buffer = 0.16
                self._jump_held = True
            elif event.key in (self.controls.get("attack"), self.controls.get("attack_alt")):
                self._attack_held = True
            elif event.key == self.controls.get("down"):
                self.drop_timer = 0.28
                self.is_dropping_down = True

        elif event.type == pygame.KEYUP:
            if event.key == self.controls.get("jump"):
                self._jump_held = False
            elif event.key in (self.controls.get("attack"), self.controls.get("attack_alt")):
                self._attack_held = False
            elif event.key == self.controls.get("down"):
                self.is_dropping_down = False

    def handle_input(self, keys: pygame.key.ScancodeWrapper, dt: float) -> None:
        """Handle continuous horizontal movement, air control, and variable jump height."""
        if not self.alive():
            return

        left_key = self.controls.get("left", -1)
        right_key = self.controls.get("right", -1)
        down_key = self.controls.get("down", -1)
        jump_key = self.controls.get("jump", -1)

        # Drop-down input
        if down_key != -1 and keys[down_key]:
            self.drop_timer = 0.28
            self.is_dropping_down = True
        else:
            self.is_dropping_down = False

        # Jump hold backup from keys
        if jump_key != -1 and keys[jump_key]:
            self._jump_held = True

        # Horizontal direction
        move_dir = 0
        if left_key != -1 and keys[left_key]:
            move_dir -= 1
        if right_key != -1 and keys[right_key]:
            move_dir += 1

        self._move_input = move_dir
        if move_dir != 0:
            self.facing = move_dir
            target_vx = move_dir * self.config.movement_speeds
            # Snappy acceleration
            accel = 2800.0 if self.on_ground else 1600.0
            diff = target_vx - self.velocity.x
            self.velocity.x += max(-accel * dt, min(accel * dt, diff))
            self.run_cycle += dt * 14.0
        else:
            # Immediate friction deceleration
            decel = 2600.0 if self.on_ground else 800.0
            if self.velocity.x > 0:
                self.velocity.x = max(0.0, self.velocity.x - decel * dt)
            elif self.velocity.x < 0:
                self.velocity.x = min(0.0, self.velocity.x + decel * dt)
            self.run_cycle = 0.0

        # Variable jump height: release jump to perform short hops
        if not self._jump_held and (jump_key == -1 or not keys[jump_key]):
            if self.velocity.y < -120.0:
                self.velocity.y += (self.config.gravity * 1.6) * dt

    def attack(
        self,
        projectiles: list[Projectile],
        effects: EffectManager,
        zombies: list[any] | None = None,
        on_zombie_hit: any = None,
        on_zombie_kill: any = None,
    ) -> bool:
        """Fire or use the currently held item with visual casting recoil. Returns True if an attack was made."""
        if not self.alive():
            return False

        if self.held_item:
            prev_ammo = self.held_item.ammo
            self.held_item.use(self, projectiles, effects)
            if self.held_item and self.held_item.ammo < prev_ammo:
                self.attack_recoil = 0.16
                return True
            return False
        else:
            if self._punch_cooldown > 0:
                return False
            self._punch_cooldown = 0.32
            cx, cy = self.center()
            effects.burst((cx + self.facing * 24, cy), count=5, palette=[(255, 255, 200), (255, 210, 80)])
            self.attack_recoil = 0.14

            # Punch hitbox strikes zombies directly in front of player
            if zombies:
                fist_w = 42
                fist_x = int(self.position.x + (6 if self.facing > 0 else -fist_w - 6))
                fist_box = pygame.Rect(fist_x, int(self.position.y - self.height * 0.85), fist_w, int(self.height * 0.75))
                for z in zombies:
                    if z.alive() and fist_box.colliderect(z.bounds()):
                        kb = (self.facing * 380.0, -180.0)
                        killed = z.take_damage(25.0, knockback=kb, effects=effects)
                        effects.request_shake(intensity=4.5, duration=0.14)
                        if on_zombie_hit:
                            on_zombie_hit(z)
                        if killed and on_zombie_kill:
                            on_zombie_kill(z)
            return True

    def update(
        self,
        dt: float,
        platforms: list[any],
        world_bounds: pygame.Rect,
    ) -> None:
        """Update physics, jumping, platform landing, and lively animation timers."""
        self.anim_time += dt
        self.prev_bottom = self.position.y

        # Timers decay
        if self._punch_cooldown > 0:
            self._punch_cooldown = max(0.0, self._punch_cooldown - dt)
        if self.damage_flash > 0:
            self.damage_flash = max(0.0, self.damage_flash - dt)
        if self.shield_timer > 0:
            self.shield_timer = max(0.0, self.shield_timer - dt)
        if self.attack_recoil > 0:
            self.attack_recoil = max(0.0, self.attack_recoil - dt)
        if self.jump_buffer > 0:
            self.jump_buffer = max(0.0, self.jump_buffer - dt)
        if self.coyote_timer > 0:
            self.coyote_timer = max(0.0, self.coyote_timer - dt)
        if self.drop_timer > 0:
            self.drop_timer = max(0.0, self.drop_timer - dt)

        # Smooth return of squash and stretch
        self.squash_stretch.x += (1.0 - self.squash_stretch.x) * min(1.0, dt * 16.0)
        self.squash_stretch.y += (1.0 - self.squash_stretch.y) * min(1.0, dt * 16.0)

        # Update held item cooldown
        if self.held_item:
            self.held_item.update(dt, [], world_bounds)

        # ------------------- GRAVITY & JUMPING -------------------
        gravity = self.config.gravity

        # Jump execution (from ground or coyote grace period)
        if self.jump_buffer > 0 and (self.on_ground or self.coyote_timer > 0):
            self.velocity.y = -self.config.jump_strength
            self.on_ground = False
            self.coyote_timer = 0.0
            self.jump_buffer = 0.0
            self.squash_stretch = pygame.Vector2(0.80, 1.28)

        # Apply gravity with slight apex hang time
        if abs(self.velocity.y) < 80.0 and not self.on_ground:
            eff_gravity = gravity * 0.70  # Float at peak
        elif self.velocity.y > 0:
            eff_gravity = gravity * 1.15  # Snappy fall
        else:
            eff_gravity = gravity

        self.velocity.y += eff_gravity * dt
        self.velocity.y = min(850.0, self.velocity.y)

        # ------------------- HORIZONTAL MOVEMENT -------------------
        self.position.x += self.velocity.x * dt

        # Arena bounds clamping (smoothly bounds players within arena)
        half_w = self.width / 2.0
        if self.position.x < world_bounds.left + half_w + 10:
            self.position.x = world_bounds.left + half_w + 10
            self.velocity.x = 0.0
        elif self.position.x > world_bounds.right - half_w - 10:
            self.position.x = world_bounds.right - half_w - 10
            self.velocity.x = 0.0

        # ------------------- VERTICAL MOVEMENT & LANDING -------------------
        self.position.y += self.velocity.y * dt
        box = self.bounds()
        was_on_ground = self.on_ground
        self.on_ground = False

        # Arena floor landing
        floor_y = world_bounds.bottom - 40
        if self.position.y >= floor_y:
            self.position.y = floor_y
            self.velocity.y = 0.0
            self.on_ground = True
            if not was_on_ground:
                self.squash_stretch = pygame.Vector2(1.26, 0.76)
            box = self.bounds()

        # Platform landing (supports one-way floating platforms and solid platforms)
        for plat in platforms:
            p_rect = getattr(plat, "rect", plat)
            p_one_way = getattr(plat, "is_one_way", False)

            # Horizontal span overlap
            if box.right > p_rect.left + 2 and box.left < p_rect.right - 2:
                if p_one_way:
                    # Floating one-way platform: land on top if falling downward and not dropping down
                    if not self.is_dropping_down and self.drop_timer <= 0 and self.velocity.y > 0:
                        if self.prev_bottom <= p_rect.top + 16 and self.position.y >= p_rect.top:
                            self.position.y = p_rect.top
                            self.velocity.y = 0.0
                            self.on_ground = True
                            if not was_on_ground:
                                self.squash_stretch = pygame.Vector2(1.24, 0.78)
                            box = self.bounds()
                else:
                    # Solid platform
                    if self.velocity.y > 0 and self.prev_bottom <= p_rect.top + 16 and self.position.y >= p_rect.top:
                        self.position.y = p_rect.top
                        self.velocity.y = 0.0
                        self.on_ground = True
                        if not was_on_ground:
                            self.squash_stretch = pygame.Vector2(1.24, 0.78)
                        box = self.bounds()
                    elif self.velocity.y < 0 and box.top <= p_rect.bottom and box.top >= p_rect.top:
                        self.position.y = p_rect.bottom + self.height
                        self.velocity.y = 0.0
                        box = self.bounds()

        # Coyote timer when stepping off a ledge
        if self.on_ground:
            self.coyote_timer = 0.14
        elif was_on_ground and not self.on_ground and self.velocity.y >= 0:
            self.coyote_timer = 0.14

        # ------------------- SCARF INVERSE KINEMATICS -------------------
        neck_origin = pygame.Vector2(self.position.x - self.facing * 4, self.position.y - 44)
        target_pos = neck_origin
        wind_x = -self.facing * (16.0 + abs(self.velocity.x) * 0.06)
        wind_y = math.sin(self.anim_time * 6.0) * 4.0 - (self.velocity.y * 0.04)

        for i, node in enumerate(self.scarf_nodes):
            des_x = target_pos.x + wind_x * (0.6 + i * 0.4)
            des_y = target_pos.y + wind_y + i * 2.0
            node.x += (des_x - node.x) * min(1.0, dt * 18.0)
            node.y += (des_y - node.y) * min(1.0, dt * 18.0)
            target_pos = node

    def draw(self, surface: pygame.Surface, camera: Camera) -> None:
        """Render stickman wizard with expressive animations: breathing, sprint lean, hat sway, and scarf."""
        screen_pos = camera.apply((self.position.x, self.position.y))
        sx, sy = screen_pos

        z = camera.zoom

        # House palette
        if self.player_id == 1:
            house_primary = (196, 30, 58)    # Gryffindor Crimson
            house_accent = (255, 215, 0)     # Gryffindor Gold
            hat_color = (160, 24, 46)
        else:
            house_primary = (27, 85, 62)     # Slytherin Emerald
            house_accent = (215, 225, 230)   # Slytherin Silver
            hat_color = (20, 65, 48)

        stick_color = (255, 255, 255) if self.damage_flash > 0 else (22, 22, 26)

        # 1. Protective Robe Shield Bubble
        if self.shield_timer > 0:
            shield_radius = int(36 * z)
            shield_surf = pygame.Surface((shield_radius * 2 + 8, shield_radius * 2 + 8), pygame.SRCALPHA)
            sc = shield_surf.get_rect().center
            pulse = math.sin(pygame.time.get_ticks() * 0.01) * (4.0 * z)
            r_pulsed = max(1, int(shield_radius + pulse))
            shield_color = (100, 220, 255, 85) if self.player_id == 1 else (100, 255, 180, 85)
            pygame.draw.circle(shield_surf, shield_color, sc, r_pulsed)
            pygame.draw.circle(shield_surf, (240, 255, 255, 180), sc, r_pulsed, width=max(1, int(2 * z)))
            surface.blit(shield_surf, (sx - sc[0], sy - int(27 * z) - sc[1]))

        # Squash and stretch scale factors
        sq_x = self.squash_stretch.x
        sq_y = self.squash_stretch.y

        # Idle breathing bob
        idle_bob = math.sin(self.anim_time * 3.5) * (2.2 * z) if self.on_ground and abs(self.velocity.x) < 5 else 0.0

        # Running lean angle: body tilts forward into sprint
        lean_angle = 0.0
        if self.on_ground and abs(self.velocity.x) > 10:
            lean_angle = self.facing * min(0.24, abs(self.velocity.x) / 360.0 * 0.22)

        # Recoil displacement from attacking
        recoil_dx = -self.facing * (self.attack_recoil * 35.0 * z)

        # Anatomical joints scaled with camera zoom and squash/stretch
        hip_y = sy - int((22.0 * sq_y + idle_bob) * z)
        neck_y = sy - int((44.0 * sq_y + idle_bob) * z)
        head_cy = sy - int((52.0 * sq_y + idle_bob) * z)

        neck_x = sx + int(math.sin(lean_angle) * (22.0 * z)) + int(recoil_dx)
        head_cx = sx + int(math.sin(lean_angle) * (30.0 * z)) + int(recoil_dx)
        hip_x = sx + int(recoil_dx * 0.5)

        line_w = max(1, int(3 * z))
        heavy_w = max(2, int(4 * z))

        # 2. Articulated Legs Animation (Hip -> Knee -> Foot)
        if not self.on_ground:
            # Airborne pose: knees bent, legs trailing
            left_knee = (hip_x - int(7 * z), hip_y + int(10 * z))
            left_foot = (hip_x - int(10 * z), sy - int(6 * z))
            right_knee = (hip_x + int(7 * z), hip_y + int(12 * z))
            right_foot = (hip_x + int(8 * z), sy - int(10 * z))
            pygame.draw.lines(surface, stick_color, False, [(hip_x, hip_y), left_knee, left_foot], width=line_w)
            pygame.draw.lines(surface, stick_color, False, [(hip_x, hip_y), right_knee, right_foot], width=line_w)

        elif abs(self.velocity.x) > 10:
            # Animated 2-joint running legs
            cycle = self.run_cycle
            l_knee_x = hip_x + int(math.sin(cycle) * 12 * z)
            l_knee_y = hip_y + int(10 * z)
            l_foot_x = hip_x + int(math.sin(cycle + 0.3) * 16 * z)
            l_foot_y = sy - max(0, int(math.sin(cycle) * 8 * z))
            pygame.draw.lines(surface, stick_color, False, [(hip_x, hip_y), (l_knee_x, l_knee_y), (l_foot_x, l_foot_y)], width=line_w)

            r_knee_x = hip_x - int(math.sin(cycle) * 12 * z)
            r_knee_y = hip_y + int(10 * z)
            r_foot_x = hip_x - int(math.sin(cycle + 0.3) * 16 * z)
            r_foot_y = sy - max(0, int(-math.sin(cycle) * 8 * z))
            pygame.draw.lines(surface, stick_color, False, [(hip_x, hip_y), (r_knee_x, r_knee_y), (r_foot_x, r_foot_y)], width=line_w)

        else:
            # Idle feet stance with breathing knee flex
            stance_w = int(7 * sq_x * z)
            pygame.draw.line(surface, stick_color, (hip_x, hip_y), (hip_x - stance_w, sy), width=line_w)
            pygame.draw.line(surface, stick_color, (hip_x, hip_y), (hip_x + stance_w, sy), width=line_w)

        # 3. Torso (Leaning with sprint)
        pygame.draw.line(surface, stick_color, (hip_x, hip_y), (neck_x, neck_y), width=heavy_w)

        # 4. Expressive Multi-Segment Scarf Flutter
        scarf_pts: list[tuple[int, int]] = [(neck_x, neck_y)]
        for node in self.scarf_nodes:
            sn_pos = camera.apply((node.x, node.y))
            scarf_pts.append(sn_pos)
        if len(scarf_pts) >= 2:
            pygame.draw.lines(surface, house_primary, False, scarf_pts, width=max(2, int(4 * z)))
            pygame.draw.lines(surface, house_accent, False, scarf_pts, width=max(1, int(2 * z)))

        # 5. Head
        head_radius = max(2, int(8.5 * min(sq_x, sq_y) * z))
        pygame.draw.circle(surface, stick_color, (head_cx, head_cy), head_radius)

        # Eye looking with expression in facing direction
        eye_x = head_cx + self.facing * int(4 * z)
        eye_y = head_cy - int(1 * z)
        pygame.draw.circle(surface, (255, 255, 255), (eye_x, eye_y), max(1, int(2 * z)))
        pygame.draw.circle(surface, (0, 0, 0), (eye_x + self.facing * max(1, int(1 * z)), eye_y), max(1, int(1 * z)))

        # 6. Procedural Pointed Wizard Hat (Animated Sway & Flutter)
        hat_brim_y = head_cy - int(5 * z)
        hat_brim_w = int(14 * z)
        hat_left = (head_cx - hat_brim_w, hat_brim_y)
        hat_right = (head_cx + hat_brim_w, hat_brim_y)
        pygame.draw.line(surface, house_primary, hat_left, hat_right, width=max(1, int(3 * z)))

        # Hat peak reacts to movement and wind
        hat_sway = math.sin(self.anim_time * 2.5) * (3.0 * z)
        wind_bend = -self.facing * (abs(self.velocity.x) * 0.03 * z)
        hat_peak = (
            head_cx - self.facing * int(4 * z) + int(hat_sway + wind_bend),
            head_cy - int(24 * z),
        )
        hat_pts = [(head_cx - int(9 * z), hat_brim_y), hat_peak, (head_cx + int(9 * z), hat_brim_y)]
        pygame.draw.polygon(surface, hat_color, hat_pts)
        pygame.draw.polygon(surface, house_primary, hat_pts, width=max(1, int(1 * z)))

        # Hat accent band
        band_y2 = hat_brim_y - int(4 * z)
        band_pts = [
            (head_cx - int(8 * z), hat_brim_y - 1),
            (head_cx - int(6 * z), band_y2),
            (head_cx + int(6 * z), band_y2),
            (head_cx + int(8 * z), hat_brim_y - 1),
        ]
        pygame.draw.polygon(surface, house_accent, band_pts)

        # 7. Arms and Weapons (Whip / Thrust / Recoil)
        shoulder_y = neck_y + int(4 * z)
        hand_reach = (18.0 + (self.attack_recoil * 18.0)) * z
        hand_x = neck_x + self.facing * int(hand_reach)
        hand_y = shoulder_y + int(2 * z) - int(self.attack_recoil * 6.0 * z)

        # Back arm (swings during run)
        if abs(self.velocity.x) > 10 and self.on_ground:
            back_arm_x = neck_x - self.facing * int(12 * z)
            back_arm_y = shoulder_y + int(math.sin(self.run_cycle) * 8 * z)
            pygame.draw.line(surface, stick_color, (neck_x, shoulder_y), (back_arm_x, back_arm_y), width=line_w)

        # Front arm holding weapon
        pygame.draw.line(surface, stick_color, (neck_x, shoulder_y), (hand_x, hand_y), width=line_w)

        # Weapon in hand
        if self.held_item:
            item_type = self.held_item.item_type
            from src.game.items import ItemType

            if item_type == ItemType.BOMB:
                pygame.draw.circle(surface, (30, 30, 35), (hand_x, hand_y), max(2, int(7 * z)))
                fuse_spark = (hand_x + self.facing * int(4 * z), hand_y - int(6 * z))
                pygame.draw.circle(surface, (255, 140, 20), fuse_spark, max(1, int(3 * z)))

            elif item_type == ItemType.WAND:
                wand_len = int(18 * z)
                wand_tip = (hand_x + self.facing * wand_len, hand_y - int(4 * z))
                pygame.draw.line(surface, (140, 90, 40), (hand_x, hand_y), wand_tip, width=max(1, int(3 * z)))
                pygame.draw.circle(surface, (100, 240, 255), wand_tip, max(1, int(3.5 * z)))
                pygame.draw.circle(surface, (255, 255, 255), wand_tip, max(1, int(1.5 * z)))

            elif item_type == ItemType.MACHINE_GUN:
                gw, gh = int(18 * z), int(8 * z)
                gun_rect = pygame.Rect(hand_x - (gw if self.facing < 0 else 0), hand_y - gh // 2, gw, gh)
                pygame.draw.rect(surface, (70, 75, 80), gun_rect, border_radius=2)
                pygame.draw.rect(surface, (220, 190, 50), (gun_rect.right - int(4 * z) if self.facing > 0 else gun_rect.left, hand_y - int(2 * z), int(4 * z), int(4 * z)))

            elif item_type == ItemType.PISTOL:
                gw, gh = int(14 * z), int(7 * z)
                gun_rect = pygame.Rect(hand_x - (gw if self.facing < 0 else 0), hand_y - gh // 2, gw, gh)
                pygame.draw.rect(surface, (50, 50, 60), gun_rect, border_radius=1)
                pygame.draw.rect(surface, (220, 70, 50), (hand_x, hand_y, int(4 * z), int(5 * z)))

            elif item_type == ItemType.ROBE:
                pygame.draw.circle(surface, (100, 180, 255), (hand_x, hand_y), max(2, int(6 * z)))
                pygame.draw.circle(surface, (255, 255, 255), (hand_x, hand_y), max(1, int(3 * z)))

        else:
            # Default miniature elder wand
            wand_tip = (hand_x + self.facing * int(11 * z), hand_y - int(2 * z))
            pygame.draw.line(surface, (120, 75, 35), (hand_x, hand_y), wand_tip, width=max(1, int(2 * z)))
            sparkle_glow = max(1, int((2.0 + math.sin(self.anim_time * 8.0)) * z))
            pygame.draw.circle(surface, (255, 255, 180), wand_tip, sparkle_glow)
