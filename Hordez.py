import random
import time
import sys
import json
import os
from datetime import datetime, timedelta
import math

# ------------------ MENU SPEED SETTINGS ------------------
class MenuSettings:
    def __init__(self):
        self.menu_speed = "normal"  # "normal" or "instant"
        self.load_settings()

    def load_settings(self):
        """Load menu speed settings from file"""
        settings_file = "menu_settings.json"
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    self.menu_speed = settings.get("menu_speed", "normal")
            except:
                self.menu_speed = "normal"

    def save_settings(self):
        """Save menu speed settings to file"""
        settings_file = "menu_settings.json"
        settings = {"menu_speed": self.menu_speed}
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)

    def set_speed(self, speed):
        """Set menu speed"""
        if speed in ["normal", "instant"]:
            self.menu_speed = speed
            self.save_settings()
            return True
        return False

    def get_speed(self):
        """Get current menu speed"""
        return self.menu_speed

# Global menu settings instance
menu_settings = MenuSettings()

# Color codes for text - all empty strings (no colors)
class Colors:
    RED = ''
    GREEN = ''
    YELLOW = ''
    BLUE = ''
    PURPLE = ''
    CYAN = ''
    WHITE = ''
    BOLD = ''
    UNDERLINE = ''
    END = ''

# ------------------ TYPING SOUND IMPLEMENTATION ------------------
class TypingSound:
    """
    Handles typing sound effects for text display.
    Creates assets/audio/typing directory if missing.
    Loads typing sound files (.wav, .mp3, .ogg) from typing directory.
    """
    def __init__(self):
        self.enabled = True
        self._has_mixer = False
        self._base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "audio", "typing")
        self._typing_sounds = []
        self._current_sound_index = 0
        self._volume = 0.3
        self._min_delay = 0.02  # Minimum delay between sounds
        self._sound_chance = 0.7  # 70% chance to play sound per character

        # Ensure typing directory exists
        self.ensure_dir()

        # Try to init pygame mixer
        try:
            import pygame
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.pygame = pygame
            self._has_mixer = True
            print(f"TypingSound: Pygame mixer initialized successfully")
        except Exception as e:
            print(f"TypingSound: Failed to initialize pygame mixer: {e}")
            self._has_mixer = False

        # Load typing sounds
        self.load_sounds()

    def ensure_dir(self):
        """Create typing sound directory if it doesn't exist"""
        os.makedirs(self._base_path, exist_ok=True)
        print(f"TypingSound: Directory ensured at {self._base_path}")

    def load_sounds(self):
        """Load all supported audio files from the typing directory"""
        if not self._has_mixer:
            print("TypingSound: No mixer available, sounds disabled")
            return

        if not os.path.exists(self._base_path):
            print(f"TypingSound: Directory not found: {self._base_path}")
            return

        supported_extensions = ['.wav', '.mp3', '.ogg']

        for filename in os.listdir(self._base_path):
            filepath = os.path.join(self._base_path, filename)
            if os.path.isfile(filepath):
                ext = os.path.splitext(filename)[1].lower()
                if ext in supported_extensions:
                    try:
                        sound = self.pygame.mixer.Sound(filepath)
                        sound.set_volume(self._volume)
                        self._typing_sounds.append(sound)
                        print(f"TypingSound: Loaded {filename}")
                    except Exception as e:
                        print(f"TypingSound: Failed to load {filename}: {e}")

        if not self._typing_sounds:
            print("TypingSound: No typing sound files found in directory")
            # Create a default beep sound programmatically
            self._create_default_sound()

    def _create_default_sound(self):
        """Create a default typing sound if no files are found"""
        try:
            import pygame
            # Generate a simple beep sound
            sample_rate = 22050
            duration = 0.02  # seconds
            frequency = 800  # Hz

            n_samples = int(sample_rate * duration)
            buf = bytearray(n_samples * 2)  # 16-bit audio

            # Generate a sine wave
            for i in range(n_samples):
                sample = int(32767.0 * 0.3 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
                # Convert to 16-bit signed
                buf[2*i] = sample & 0xff
                buf[2*i+1] = (sample >> 8) & 0xff

            sound = pygame.mixer.Sound(buffer=bytes(buf))
            sound.set_volume(self._volume)
            self._typing_sounds.append(sound)
            print("TypingSound: Created default typing sound")
        except Exception as e:
            print(f"TypingSound: Failed to create default sound: {e}")

    def play(self):
        """Play a typing sound"""
        if not self.enabled or not self._has_mixer or not self._typing_sounds:
            return

        try:
            # Cycle through available sounds
            sound = self._typing_sounds[self._current_sound_index]
            sound.play()
            self._current_sound_index = (self._current_sound_index + 1) % len(self._typing_sounds)
        except Exception as e:
            print(f"TypingSound: Error playing sound: {e}")

    def set_enabled(self, enabled):
        """Enable or disable typing sounds"""
        self.enabled = bool(enabled)
        print(f"TypingSound: {'Enabled' if self.enabled else 'Disabled'}")

    def set_volume(self, volume):
        """Set typing sound volume (0.0 to 1.0)"""
        self._volume = max(0.0, min(1.0, volume))
        if self._has_mixer:
            for sound in self._typing_sounds:
                try:
                    sound.set_volume(self._volume)
                except:
                    pass

    def set_sound_chance(self, chance):
        """Set probability of playing sound per character (0.0 to 1.0)"""
        self._sound_chance = max(0.0, min(1.0, chance))

# Global typing sound instance
typing_sound = TypingSound()

# ---------------------------------------------------------------------------
# Right Shift skip system.
# Plain list-bool flag — no threading.Event, no locks, zero overhead per char.
# Background daemon thread writes _rshift_skip_flag[0]. GIL guarantees safety.
# ---------------------------------------------------------------------------
import threading as _threading

_rshift_skip_flag = [False]   # mutable bool: [True] = skip active
_rshift_watcher_started = False


def _rshift_watcher():
    """
    Daemon thread polls Right Shift at 60 Hz with 3-frame debounce (~50ms hold).
    Writes _rshift_skip_flag[0] = True/False. Single writer — GIL safe, no locks.
    """
    try:
        import ctypes
        user32 = ctypes.windll.user32
        VK_RSHIFT = 0xA1
        hold_count = 0
        while True:
            if user32.GetAsyncKeyState(VK_RSHIFT) & 0x8000:
                hold_count += 1
                if hold_count >= 3:
                    _rshift_skip_flag[0] = True
            else:
                hold_count = 0
                _rshift_skip_flag[0] = False
            time.sleep(1 / 60)
    except Exception:
        pass


def _ensure_rshift_watcher():
    global _rshift_watcher_started
    if not _rshift_watcher_started:
        t = _threading.Thread(target=_rshift_watcher, daemon=True)
        t.start()
        _rshift_watcher_started = True


def _clear_rshift():
    """Call before every input() — prevents held RShift bleeding into menu choices."""
    _rshift_skip_flag[0] = False


def type_text(text, delay=0.03, sound=True):
    """
    Smooth typewriter — per-character write+flush, exactly as original.
    Right Shift skip reads a plain bool list element: zero lock overhead.
    """
    _ensure_rshift_watcher()

    if menu_settings.get_speed() == "instant":
        print(text)
        return

    # Already held at line start — dump whole line instantly
    if _rshift_skip_flag[0]:
        _rshift_skip_flag[0] = False
        print(text)
        return

    last_sound_time = time.time()
    flag = _rshift_skip_flag  # local ref avoids repeated global lookup

    for i, char in enumerate(text):
        if flag[0]:
            flag[0] = False
            sys.stdout.write(text[i:])
            sys.stdout.flush()
            print()
            return

        # Original smooth per-char write + flush
        sys.stdout.write(char)
        sys.stdout.flush()

        if sound and typing_sound.enabled and char not in (' ', '\n'):
            current_time = time.time()
            if (current_time - last_sound_time >= typing_sound._min_delay and
                    random.random() < typing_sound._sound_chance):
                typing_sound.play()
                last_sound_time = current_time

        time.sleep(delay)

    print()


def _clear_rshift():
    """Call before every input() — prevents held RShift bleeding into menu choices."""
    _rshift_skip_flag[0] = False


def format_time(minutes):
    """Convert minutes to HH:MM:SS format"""
    total_seconds = int(minutes * 60)
    hours = total_seconds // 3600
    remaining_seconds = total_seconds % 3600
    minutes = remaining_seconds // 60
    seconds = remaining_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

# ------------------ UPDATED: AudioManager with seamless looping and TOWN support ------------------
class AudioManager:
    """
    Flexible audio manager using pygame.mixer when available.
    Creates assets/audio/{intro,battle,day,night,boss,menu,items,zombies,dialog,town} directories if missing.
    Loads ANY audio file found in these directories (supports .mp3, .wav, .ogg).
    Graceful fallback if pygame or files are missing.
    Implements seamless looping by using pygame.mixer.music for background tracks.
    """
    ASSET_SUBDIRS = ["intro", "battle", "day", "night", "boss", "menu", "horde", "items", "zombies", "dialog", "town"]
    SUPPORTED_EXTENSIONS = ['.mp3', '.wav', '.ogg', '.flac']

    def __init__(self):
        self.enabled = True
        self._has_mixer = False
        self._base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "audio")
        self._music_tracks = {}  # looped music paths
        self._sfx = {}  # small sounds
        self._current_music = None
        self._volume = 0.8
        self._fading_out = False
        self._music_channel = None

        # ensure asset subfolders exist
        self.ensure_dirs()

        # try to init pygame mixer
        try:
            import pygame
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            # Set up music channel
            pygame.mixer.set_num_channels(8)  # Reserve 8 channels for SFX
            self.pygame = pygame
            self._has_mixer = True
            print(f"AudioManager: Pygame mixer initialized successfully")
        except Exception as e:
            print(f"AudioManager: Failed to initialize pygame mixer: {e}")
            self._has_mixer = False

        # discover/load audio files (if present)
        self.load_sounds()

    def ensure_dirs(self):
        # Create main audio directories
        for sub in self.ASSET_SUBDIRS:
            path = os.path.join(self._base_path, sub)
            os.makedirs(path, exist_ok=True)

        # Create zombie class subdirectories
        zombie_classes = ["walker", "runner", "tank", "crawler", "spitter", "boss", "horde"]
        for zombie_class in zombie_classes:
            path = os.path.join(self._base_path, "zombies", zombie_class)
            os.makedirs(path, exist_ok=True)

        # Create dialog subdirectories
        dialog_types = ["npc", "player", "story"]
        for dialog_type in dialog_types:
            path = os.path.join(self._base_path, "dialog", dialog_type)
            os.makedirs(path, exist_ok=True)

        # Create town subdirectories for different settlement types
        town_types = ["refugee_camp", "abandoned_town", "military_outpost", "barricaded_city", "roadside_junkyard"]
        for town_type in town_types:
            path = os.path.join(self._base_path, "town", town_type)
            os.makedirs(path, exist_ok=True)

        # Create confirmation sounds directory
        confirm_path = os.path.join(self._base_path, "confirmation")
        os.makedirs(confirm_path, exist_ok=True)

    def _find_any_audio_file(self, subdir):
        """Find any audio file in the given subdirectory"""
        folder = os.path.join(self._base_path, subdir)
        if not os.path.exists(folder):
            return None

        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    return filepath
        return None

    def _find_all_audio_files(self, subdir):
        """Find all audio files in the given subdirectory"""
        folder = os.path.join(self._base_path, subdir)
        if not os.path.exists(folder):
            return []

        audio_files = []
        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    audio_files.append(filepath)
        return audio_files

    def _find_town_audio_file(self, town_type):
        """Find any audio file in the town subdirectory"""
        folder = os.path.join(self._base_path, "town", town_type)
        if not os.path.exists(folder):
            return None

        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    return filepath
        return None

    def load_sounds(self):
        # Load music tracks from each subdirectory
        for subdir in ["intro", "battle", "day", "night", "boss", "menu", "horde"]:
            audio_file = self._find_any_audio_file(subdir)
            if audio_file:
                self._music_tracks[subdir] = audio_file
                print(f"AudioManager: Loaded {subdir} music: {os.path.basename(audio_file)}")
            else:
                print(f"AudioManager: No audio file found in {subdir}/ directory")
                self._music_tracks[subdir] = None

        # Load town music tracks
        town_types = ["refugee_camp", "abandoned_town", "military_outpost", "barricaded_city", "roadside_junkyard"]
        for town_type in town_types:
            audio_file = self._find_town_audio_file(town_type)
            if audio_file:
                self._music_tracks[f"town_{town_type}"] = audio_file
                print(f"AudioManager: Loaded {town_type} town music: {os.path.basename(audio_file)}")
            else:
                print(f"AudioManager: No audio file found in town/{town_type}/ directory")
                self._music_tracks[f"town_{town_type}"] = None

        # Load SFX from various directories
        sfx_dirs = ['menu', 'items', 'confirmation']
        for sfx_dir in sfx_dirs:
            sfx_files = self._find_all_audio_files(sfx_dir)
            for i, sfx_file in enumerate(sfx_files):
                if self._has_mixer:
                    try:
                        sound_name = f"{sfx_dir}_sfx_{i}"
                        self._sfx[sound_name] = self.pygame.mixer.Sound(sfx_file)
                        self._sfx[sound_name].set_volume(self._volume)
                        print(f"AudioManager: Loaded {sfx_dir} SFX: {os.path.basename(sfx_file)}")
                    except Exception as e:
                        print(f"AudioManager: Failed to load {sfx_dir} SFX {sfx_file}: {e}")

        # Load zombie sounds
        zombie_files = self._find_all_audio_files('zombies')
        for zombie_file in zombie_files:
            if self._has_mixer:
                try:
                    # Extract zombie class from path
                    rel_path = os.path.relpath(zombie_file, os.path.join(self._base_path, "zombies"))
                    zombie_class = rel_path.split(os.sep)[0] if os.sep in rel_path else "generic"
                    sound_name = f"zombie_{zombie_class}_{os.path.splitext(os.path.basename(zombie_file))[0]}"
                    self._sfx[sound_name] = self.pygame.mixer.Sound(zombie_file)
                    self._sfx[sound_name].set_volume(self._volume)
                    print(f"AudioManager: Loaded zombie sound: {sound_name}")
                except Exception as e:
                    print(f"AudioManager: Failed to load zombie sound {zombie_file}: {e}")

        # Load dialog sounds
        dialog_files = self._find_all_audio_files('dialog')
        for dialog_file in dialog_files:
            if self._has_mixer:
                try:
                    # Extract dialog type from path
                    rel_path = os.path.relpath(dialog_file, os.path.join(self._base_path, "dialog"))
                    dialog_type = rel_path.split(os.sep)[0] if os.sep in rel_path else "generic"
                    sound_name = f"dialog_{dialog_type}_{os.path.splitext(os.path.basename(dialog_file))[0]}"
                    self._sfx[sound_name] = self.pygame.mixer.Sound(dialog_file)
                    self._sfx[sound_name].set_volume(self._volume)
                    print(f"AudioManager: Loaded dialog sound: {sound_name}")
                except Exception as e:
                    print(f"AudioManager: Failed to load dialog sound {dialog_file}: {e}")

    def set_volume(self, vol: float):
        self._volume = max(0.0, min(1.0, vol))
        if self._has_mixer:
            try:
                self.pygame.mixer.music.set_volume(self._volume)
                for s in self._sfx.values():
                    if s:
                        s.set_volume(self._volume)
            except Exception as e:
                print(f"AudioManager: Error setting volume: {e}")

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if not self.enabled and self._has_mixer:
            try:
                self.pygame.mixer.music.stop()
            except Exception as e:
                print(f"AudioManager: Error stopping music: {e}")

    def _play_music(self, key, loop=True):
        """Play music with seamless looping using pygame.mixer.music"""
        if not self.enabled or not self._has_mixer:
            print(f"AudioManager: Not enabled or no mixer for {key}")
            return
        path = self._music_tracks.get(key)
        if not path:
            print(f"AudioManager: No audio file found for {key}")
            # Don't stop current music if we don't have new music
            return

        # If already playing this music, don't restart it
        if self._current_music == key and self.pygame.mixer.music.get_busy():
            print(f"AudioManager: Already playing {key} music")
            return

        try:
            # Stop any currently playing music
            if self._current_music and self._current_music != key:
                self.pygame.mixer.music.fadeout(500)  # 500ms fade out
                time.sleep(0.5)  # Wait for fadeout to complete
            else:
                self.pygame.mixer.music.stop()

            time.sleep(0.1)  # Brief pause
            self.pygame.mixer.music.load(path)
            self.pygame.mixer.music.set_volume(self._volume)
            # Use -1 for infinite looping (seamless)
            self.pygame.mixer.music.play(-1)
            self._current_music = key
            print(f"AudioManager: Playing {key} music with seamless looping: {os.path.basename(path)}")
        except Exception as e:
            print(f"AudioManager: Error playing {key} music: {e}")
            # Try to recover mixer if there's an error
            try:
                self.pygame.mixer.quit()
                self.pygame.mixer.init()
            except:
                pass

    def _stop_music(self):
        if not self._has_mixer:
            return
        try:
            self.pygame.mixer.music.fadeout(500)  # 500ms fade out
            time.sleep(0.5)
            self._current_music = None
        except Exception as e:
            print(f"AudioManager: Error stopping music: {e}")

    def stop_immediately(self):
        if not self._has_mixer:
            return
        try:
            self.pygame.mixer.music.stop()
            self._current_music = None
        except Exception as e:
            print(f"AudioManager: Error stopping music immediately: {e}")

    # convenience methods
    def play_intro(self):
        self._play_music('intro', loop=True)

    def play_battle(self):
        self._play_music('battle', loop=True)

    def play_day(self):
        self._play_music('day', loop=True)

    def play_night(self):
        self._play_music('night', loop=True)

    def play_boss(self):
        self._play_music('boss', loop=True)

    def play_horde(self):
        """Play horde music like other background tracks"""
        self._play_music("horde", loop=True)

    def play_town(self, town_type):
        """Play town-specific music based on settlement type"""
        self._play_music(f'town_{town_type}', loop=True)

    def play_menu_select(self):
        if "menu_sfx_0" in self._sfx:
            self._sfx["menu_sfx_0"].play()
        else:
            self._play_sfx('menu', "select")

    def play_item_sound(self, item_name):
        self._play_sfx('items', item_name)

    def play_confirmation(self, success=True):
        if success:
            if "confirmation_sfx_0" in self._sfx:
                self._sfx["confirmation_sfx_0"].play()
            else:
                self._play_sfx('confirmation', 'positive')
        else:
            if "confirmation_sfx_1" in self._sfx:
                self._sfx["confirmation_sfx_1"].play()
            else:
                self._play_sfx('confirmation', 'negative')

    def play_zombie_sound(self, zombie_class, sound_type="groan"):
        self._play_sfx('zombie', f"{zombie_class}_{sound_type}")

    def play_dialog(self, dialog_type, character="generic"):
        self._play_sfx('dialog', f"{dialog_type}_{character}")

    def play_npc_voiceover(self, dialogue_line):
        """
        Match a dialogue line to a specific audio file in assets/audio/dialog/npc/.
        Matching priority:
          1. Exact filename match (without extension) to NPC name prefix
             e.g. "Old Man: ..." -> looks for old_man.mp3 / old_man.wav
          2. Keyword match — any word from the line found in a filename
          3. Fallback: play any file in npc/ folder (generic ambient)
        File naming convention:
          assets/audio/dialog/npc/old_man.mp3       <- plays for "Old Man: ..." lines
          assets/audio/dialog/npc/guard.mp3         <- plays for "Guard: ..." lines
          assets/audio/dialog/npc/line_001.mp3      <- plays in order if no name match
        """
        if not self.enabled or not self._has_mixer:
            return

        npc_folder = os.path.join(self._base_path, "dialog", "npc")
        if not os.path.exists(npc_folder):
            return

        # Build list of all audio files in npc folder
        audio_files = []
        for fname in sorted(os.listdir(npc_folder)):
            fpath = os.path.join(npc_folder, fname)
            if os.path.isfile(fpath):
                ext = os.path.splitext(fname)[1].lower()
                if ext in self.SUPPORTED_EXTENSIONS:
                    audio_files.append((os.path.splitext(fname)[0].lower(), fpath))

        if not audio_files:
            return

        chosen = None

        # Priority 1: match NPC name prefix to filename
        # "Old Man: 'blah'" -> prefix = "old man" -> slug = "old_man"
        if ":" in dialogue_line and dialogue_line.index(":") < 30:
            prefix = dialogue_line.split(":")[0].strip().lower().replace(" ", "_")
            for stem, fpath in audio_files:
                if stem == prefix or stem.startswith(prefix):
                    chosen = fpath
                    break

        # Priority 2: keyword match — any significant word from line in filename
        if not chosen:
            import re as _re
            words = [w.lower() for w in _re.findall(r"[a-z]{4,}", dialogue_line.lower())]
            for stem, fpath in audio_files:
                if any(w in stem for w in words):
                    chosen = fpath
                    break

        # Priority 3: fallback — any npc file
        if not chosen and audio_files:
            chosen = audio_files[0][1]

        if chosen:
            try:
                sound = self.pygame.mixer.Sound(chosen)
                sound.set_volume(self._volume)
                sound.play()
            except Exception as e:
                print(f"AudioManager: voiceover play error: {e}")

    def _play_sfx(self, category, sound_name):
        if not self.enabled or not self._has_mixer:
            return

        # Try exact match first
        exact_key = f"{category}_{sound_name}"
        if exact_key in self._sfx:
            try:
                self._sfx[exact_key].play()
                return
            except Exception as e:
                print(f"AudioManager: Error playing {exact_key}: {e}")

        # Try to find a matching sound
        for key in self._sfx:
            if category in key and sound_name in key:
                try:
                    self._sfx[key].play()
                    return
                except Exception as e:
                    print(f"AudioManager: Error playing {key}: {e}")

        # Try to find any sound in the category
        for key in self._sfx:
            if category in key:
                try:
                    self._sfx[key].play()
                    return
                except Exception as e:
                    print(f"AudioManager: Error playing {key}: {e}")

    def stop(self):
        self._stop_music()
# ---------------------------------------------------------------------------------------------

# instantiate global audio manager so menus and functions can call it
audio_manager = AudioManager()

# Print audio status for debugging
print(f"Audio enabled: {audio_manager.enabled}")
print(f"Has mixer: {audio_manager._has_mixer}")
print(f"Loaded tracks: {list(audio_manager._music_tracks.keys())}")

class SoundManager:
    BOSS_THRESHOLD = 50  # Noise level threshold for boss attraction
    BOSS_CHANCE_MODIFIER = 0.01  # Chance increase per noise point above threshold

    @staticmethod
    def calculate_boss_chance(noise_level):
        if noise_level < SoundManager.BOSS_THRESHOLD:
            return 0
        return min(0.8, (noise_level - SoundManager.BOSS_THRESHOLD) * SoundManager.BOSS_CHANCE_MODIFIER)

class Equipment:
    EQUIPMENT_STATS = {
        "Reinforced Vest": {"type": "armor", "defense": 5, "hp_bonus": 10, "noise_penalty": 0},
        "Sharpened Weapon": {"type": "weapon", "attack": 5, "damage_bonus": 3, "noise_penalty": 5},
        "Reinforced Armor": {"type": "armor", "defense": 8, "hp_bonus": 15, "noise_penalty": 3},
        "Silent Boots": {"type": "boots", "stealth": 15, "defense": 2, "noise_penalty": -10},
        "Sturdy Backpack": {"type": "accessory", "inventory_slots": 5, "noise_penalty": 2}
    }

    EQUIPMENT_DETAILS = {
        "Reinforced Vest": {
            "type": "armor",
            "defense": 5,
            "hp_bonus": 10,
            "noise_penalty": 0,
            "description": "Basic protective vest made from scavenged materials"
        },
        "Sharpened Weapon": {
            "type": "weapon",
            "attack": 5,
            "damage_bonus": 3,
            "noise_penalty": 5,
            "description": "A sharpened piece of metal, effective but noisy"
        },
        "Reinforced Armor": {
            "type": "armor",
            "defense": 8,
            "hp_bonus": 15,
            "noise_penalty": 3,
            "description": "Heavy armor offering superior protection"
        },
        "Silent Boots": {
            "type": "boots",
            "stealth": 15,
            "defense": 2,
            "noise_penalty": -10,
            "description": "Specially crafted boots that minimize noise"
        },
        "Sturdy Backpack": {
            "type": "accessory",
            "inventory_slots": 5,
            "noise_penalty": 2,
            "description": "Expanded backpack for carrying more items"
        }
    }

    DECONSTRUCT_RECIPES = {
        "Reinforced Vest": {"Scrap Metal": 2, "Cloth": 1},
        "Sharpened Weapon": {"Scrap Metal": 3},
        "Reinforced Armor": {"Scrap Metal": 4, "Mechanical Parts": 1},
        "Silent Boots": {"Cloth": 2, "Scrap Metal": 1},
        "Sturdy Backpack": {"Cloth": 3, "Scrap Metal": 2, "Electronic Parts": 1}
    }

class Character:
    CLASS_STATS = {
        "Survivor": {
            "max_hp": 60, "max_mp": 15, "attack": 12, "defense": 8, "magic": 4,
            "spells": ["First Aid"],
            "crafting_bonus": {"weapon": 1.1, "armor": 1.0, "medical": 0.9},
            "dialogue": [
                "I need to stay focused...", "This place gives me the creeps...",
                "Better keep my guard up.", "What was that noise?", "I should be prepared for anything.",
                "Running out of time...", "Need to find supplies quickly!", "Can't waste anything..."
            ]
        },
        "Scavenger": {
            "max_hp": 50, "max_mp": 20, "attack": 10, "defense": 6, "magic": 8,
            "spells": ["Molotov", "Trap Setup"],
            "crafting_bonus": {"weapon": 1.0, "armor": 1.0, "medical": 1.2},
            "dialogue": [
                "Plenty of good stuff around here...", "I can work with this.",
                "Gotta find the valuable bits.", "This looks promising...", "I know how to make use of this.",
                "Time is supplies... gotta move.", "What treasures are hiding here?"
            ]
        },
        "Medic": {
            "max_hp": 45, "max_mp": 30, "attack": 6, "defense": 5, "magic": 12,
            "spells": ["Heal Wounds", "Antidote", "Revitalize"],
            "crafting_bonus": {"weapon": 0.9, "armor": 1.0, "medical": 1.3},
            "dialogue": [
                "I need to tend to my wounds...", "Medical supplies would help.",
                "Someone might need help out here.", "I should check my condition.",
                "Health is the priority.", "Time is a limited resource...", "Need to stay in good shape."
            ]
        },
        "Infected": {
            "max_hp": 70, "max_mp": 10, "attack": 15, "defense": 5, "magic": 5,
            "spells": ["Viral Burst", "Consume", "Mutate"],
            "crafting_bonus": {"weapon": 1.2, "armor": 0.8, "medical": 0.5},
            "dialogue": [
                "The virus... it whispers to me...", "I can feel it changing me...",
                "Hunger... constant hunger...", "They fear what they don't understand...",
                "My body is not my own...", "The transformation continues...", "I must feed...",
                "The pain... it's becoming pleasure...", "I see things... differently now..."
            ]
        }
    }

    NIGHT_DIALOGUE = [
        "The night is dangerous...", "I can hear them out there...", "Need to find shelter soon.",
        "Every shadow could be one of them.", "The darkness plays tricks on me.", "What the? Gross!!.",
        "They're more active at night...", "The stench is awful!", "Red eyes...Not good!",
        "Light is faint, got to watch my footing.", "What happened here?...",
        "Might need to rest soon..", "Finally some fresh air!", "Treading lightly..."
    ]

    INFECTED_NIGHT_DIALOGUE = [
        "The night calls to me...", "I can feel them... my kind...", "The darkness is my friend...",
        "My senses are heightened...", "The hunger grows stronger...", "The virus thrives in darkness...",
        "I should hunt... feed...", "The pain subsides at night...", "My body adapts... evolves...",
        "The moonlight reveals hidden truths...", "I am becoming... more..."
    ]

    CRAFTING_RECIPES = {
        "Reinforced Vest": {"Scrap Metal": 3, "Cloth": 2},
        "Sharpened Weapon": {"Scrap Metal": 4},
        "Medkit": {"Herbs": 2, "Cloth": 1, "Purified Water": 1},
        "Molotov Cocktail": {"Herbs": 1, "Purified Water": 1, "Cloth": 1},
        "Zombie Repellent": {"Herbs": 3, "Scrap Metal": 1},
        "Rabbit's Pendant": {"Electronic Parts": 2, "Mechanical Parts": 1, "Scrap Metal": 3},
        "Advanced Medkit": {"Medkit": 1, "Herbs": 3, "Electronic Parts": 1},
        "Reinforced Armor": {"Reinforced Vest": 1, "Scrap Metal": 5, "Mechanical Parts": 2},
        "Purified Herbs": {"Herbs": 3, "Purified Water": 1},
        "Silent Boots": {"Cloth": 4, "Scrap Metal": 2},
        "Sturdy Backpack": {"Cloth": 5, "Scrap Metal": 3, "Electronic Parts": 1},
        "Zombie Bait": {"Herbs": 2, "Electronic Parts": 1, "Mechanical Parts": 1}
    }

    def __init__(self, name, job_class):
        self.name = name
        self.job_class = job_class
        self.level = 1
        self.exp = 0
        self.exp_to_next = 50
        self.crafting_level = 1
        self.crafting_exp = 0
        self.crafting_exp_to_next = 100
        self.parry_chance = 0.3
        self.parry_boost_active = False
        self.parry_boost_uses = 0
        self.molotov_dot_active = False
        self.molotov_dot_turns = 0

        # Infection system
        self.infected = False
        self.infection_timer = 0
        self.infection_damage = 5

        # Infected class specific
        self.is_infected_class = (job_class == "Infected")
        self.night_health_drain = 0  # Amount of HP lost at night for Infected class
        self.mutation_chance = 0.0  # Chance to mutate (hourly for Infected)
        self.mutations = []  # List of mutations gained
        self.mutation_benefits = {}  # Stats from mutations

        self.skill_points = 0
        self.learned_skills = []
        self.found_lore = []
        self.noise_level = 0
        self.stealth_bonus = 0
        self.collectables = {}

        # Equipment system
        self.equipped = {
            "weapon": None,
            "armor": None,
            "boots": None,
            "accessory": None
        }
        self.base_stats = {}

        # Set class-specific stats
        stats = self.CLASS_STATS[job_class]
        self.max_hp = stats["max_hp"]
        self.hp = self.max_hp
        self.max_mp = stats["max_mp"]
        self.mp = self.max_mp
        self.attack = stats["attack"]
        self.defense = stats["defense"]
        self.magic = stats["magic"]
        self.spells = stats["spells"].copy()
        self.crafting_bonus = stats["crafting_bonus"].copy()
        self.dialogue = stats["dialogue"]

        # Store base stats for equipment calculations
        self.base_stats = {
            "max_hp": self.max_hp,
            "attack": self.attack,
            "defense": self.defense,
            "magic": self.magic
        }

        self.change = 30
        self.inventory = {"Purified Water": 1, "Bandage": 2, "Scrap Metal": 3, "Cloth": 2, "Herbs": 1, "Electronic Parts": 0, "Mechanical Parts": 0}
        self.crafting_recipes = self.CRAFTING_RECIPES.copy()

        # Infected class starts infected and immune
        if self.is_infected_class:
            self.infected = True
            self.infection_timer = 0
            self.infection_damage = 0  # No damage from infection for Infected class
            self.night_health_drain = 3  # HP lost per night hour
            self.mutation_chance = 0.5  # 50% chance per hour to mutate

    def display_stats(self, sound=True):
        type_text(f"\n{self.name} - {self.job_class} Lv.{self.level} (Crafting Lv.{self.crafting_level})", sound=sound)
        type_text(f"HP: {self.hp}/{self.max_hp}  MP: {self.mp}/{self.max_mp}", sound=sound)
        type_text(f"EXP: {self.exp}/{self.exp_to_next} | Crafting EXP: {self.crafting_exp}/{self.crafting_exp_to_next}", sound=sound)
        type_text(f"Noise Level: {self.noise_level}%", sound=sound)

        if self.infected and not self.is_infected_class:
            type_text(f"INFECTED! {self.infection_timer} turns until next damage", sound=sound)

        if self.is_infected_class:
            type_text(f"VIRAL HOST - Immune to infection", sound=sound)
            if self.mutations:
                type_text(f"Mutations: {', '.join(self.mutations)}", sound=sound)

    def display_status(self, sound=True):
        type_text(f"\n=== STATUS ===", sound=sound)
        type_text(f"Attack: {self.attack}  Defense: {self.defense}  Magic: {self.magic}", sound=sound)
        type_text(f"HP: {self.hp}/{self.max_hp}  MP: {self.mp}/{self.max_mp}", sound=sound)
        type_text(f"Parry Chance: {int(self.parry_chance * 100)}%", sound=sound)
        type_text(f"Supplies: {self.change}", sound=sound)
        type_text(f"Skills: {', '.join(self.spells) if self.spells else 'None'}", sound=sound)
        type_text(f"Skill Points: {self.skill_points}", sound=sound)
        type_text(f"Stealth Bonus: +{self.stealth_bonus}%", sound=sound)
        type_text(f"Noise Level: {self.noise_level}%", sound=sound)

        # Display equipment with their bonuses
        type_text(f"\n=== EQUIPPED ===", sound=sound)
        for slot, item in self.equipped.items():
            if item:
                stats_text = []
                item_stats = Equipment.EQUIPMENT_STATS[item]

                if "defense" in item_stats:
                    stats_text.append(f"Def+{item_stats['defense']}")
                if "attack" in item_stats:
                    stats_text.append(f"Atk+{item_stats['attack']}")
                if "hp_bonus" in item_stats:
                    stats_text.append(f"HP+{item_stats['hp_bonus']}")
                if "noise_penalty" in item_stats:
                    noise_val = item_stats['noise_penalty']
                    stats_text.append(f"Noise{noise_val:+d}")
                if "stealth" in item_stats:
                    stats_text.append(f"Stealth+{item_stats['stealth']}")

                type_text(f"{slot.title()}: {item} ({', '.join(stats_text)})", sound=sound)
            else:
                type_text(f"{slot.title()}: None", sound=sound)

        if self.infected and not self.is_infected_class:
            type_text(f"INFECTED! {self.infection_timer} turns until next damage", sound=sound)

        if self.is_infected_class:
            type_text(f"=== VIRAL HOST ===", sound=sound)
            type_text(f"Night Health Drain: {self.night_health_drain} HP/hour", sound=sound)
            type_text(f"Mutation Chance: {int(self.mutation_chance * 100)}% per hour", sound=sound)
            if self.mutations:
                type_text(f"Active Mutations: {', '.join(self.mutations)}", sound=sound)
                for mutation in self.mutations:
                    if mutation in self.mutation_benefits:
                        benefits = self.mutation_benefits[mutation]
                        type_text(f"  {mutation}: {benefits['description']}", sound=sound)

    def display_inventory(self, sound=True):
        type_text(f"\n=== INVENTORY ===", sound=sound)
        if not any(qty > 0 for qty in self.inventory.values()):
            type_text("Your inventory is empty.", sound=sound)
            return

        for item, quantity in self.inventory.items():
            if quantity > 0:
                # Play item sound if available
                if item in ["Purified Water", "Bandage", "Antidote", "Medkit", "Advanced Medkit",
                           "Rabbit's Pendant", "Purified Herbs", "Reinforced Vest", "Sharpened Weapon",
                           "Reinforced Armor", "Silent Boots", "Sturdy Backpack", "Molotov Cocktail"]:
                    audio_manager.play_item_sound(item)
                type_text(f"{item}: {quantity}", sound=sound)

    def display_equipment(self, sound=True):
        type_text(f"\n=== EQUIPMENT ===", sound=sound)
        equipment_items = [item for item in self.inventory if item in Equipment.EQUIPMENT_STATS and self.inventory[item] > 0]

        if not equipment_items:
            type_text("You don't have any equipment.", sound=sound)
            return

        for i, item in enumerate(equipment_items, 1):
            equipped_mark = ""
            for slot, equipped_item in self.equipped.items():
                if equipped_item == item:
                    equipped_mark = f" [EQUIPPED in {slot.upper()}]"
                    break
            type_text(f"{i}. {item} x{self.inventory[item]}{equipped_mark}", sound=sound)

        try:
            _clear_rshift()
            choice = int(input("\nSelect equipment to manage (0 to cancel): "))
            if choice == 0:
                return
            elif 1 <= choice <= len(equipment_items):
                item = equipment_items[choice-1]
                self.manage_equipment(item)
            else:
                type_text("Invalid selection!")
                audio_manager.play_confirmation(False)
        except ValueError:
            type_text("Invalid input!")
            audio_manager.play_confirmation(False)

    def manage_equipment(self, item, sound=True):
        if item not in Equipment.EQUIPMENT_STATS:
            type_text("This item cannot be equipped!", sound=sound)
            audio_manager.play_confirmation(False)
            return

        stats = Equipment.EQUIPMENT_STATS[item]
        equipment_type = stats["type"]
        currently_equipped = self.equipped[equipment_type]

        type_text(f"\n=== {item.upper()} ===", sound=sound)
        type_text(f"Type: {equipment_type.title()}", sound=sound)

        # Display equipment stats
        if "defense" in stats:
            type_text(f"Defense: +{stats['defense']}", sound=sound)
        if "attack" in stats:
            type_text(f"Attack: +{stats['attack']}", sound=sound)
        if "hp_bonus" in stats:
            type_text(f"HP Bonus: +{stats['hp_bonus']}", sound=sound)
        if "noise_penalty" in stats:
            noise_text = f"Noise: {stats['noise_penalty']}"
            if stats["noise_penalty"] < 0:
                noise_text = f"Noise: -{abs(stats['noise_penalty'])}"
            type_text(noise_text, sound=sound)
        if "stealth" in stats:
            type_text(f"Stealth: +{stats['stealth']}", sound=sound)

        # Show comparison if something is already equipped
        if currently_equipped:
            current_stats = Equipment.EQUIPMENT_STATS[currently_equipped]
            type_text(f"\nCurrently equipped: {currently_equipped}", sound=sound)

            # Compare stats
            if "defense" in stats and "defense" in current_stats:
                diff = stats["defense"] - current_stats["defense"]
                if diff != 0:
                    type_text(f"Defense: {diff:+d}", sound=sound)

            if "attack" in stats and "attack" in current_stats:
                diff = stats["attack"] - current_stats["attack"]
                if diff != 0:
                    type_text(f"Attack: {diff:+d}", sound=sound)

            if "hp_bonus" in stats and "hp_bonus" in current_stats:
                diff = stats["hp_bonus"] - current_stats["hp_bonus"]
                if diff != 0:
                    type_text(f"HP Bonus: {diff:+d}", sound=sound)

            if "noise_penalty" in stats and "noise_penalty" in current_stats:
                diff = stats["noise_penalty"] - current_stats["noise_penalty"]
                if diff != 0:
                    type_text(f"Noise: {diff:+d}", sound=sound)

            if "stealth" in stats and "stealth" in current_stats:
                diff = stats["stealth"] - current_stats["stealth"]
                if diff != 0:
                    type_text(f"Stealth: {diff:+d}", sound=sound)

        type_text("\n1. Equip", sound=sound)
        type_text("2. Deconstruct", sound=sound)
        type_text("3. Back", sound=sound)

        try:
            _clear_rshift()
            choice = int(input("\nEnter your choice: "))
            if choice == 1:
                self.equip_item(item)
            elif choice == 2:
                self.deconstruct_item(item)
            elif choice == 3:
                return
            else:
                type_text("Invalid choice!")
                audio_manager.play_confirmation(False)
        except ValueError:
            type_text("Invalid input!")
            audio_manager.play_confirmation(False)

    def equip_item(self, item, sound=True):
        if item not in Equipment.EQUIPMENT_STATS:
            type_text("This item cannot be equipped!", sound=sound)
            audio_manager.play_confirmation(False)
            return

        equipment_type = Equipment.EQUIPMENT_STATS[item]["type"]
        currently_equipped = self.equipped[equipment_type]

        # Unequip current item if any
        if currently_equipped:
            self.unequip_item(currently_equipped)

        # Equip new item
        self.equipped[equipment_type] = item
        self.inventory[item] -= 1
        if self.inventory[item] <= 0:
            del self.inventory[item]

        # Apply equipment bonuses
        stats = Equipment.EQUIPMENT_STATS[item]
        if "defense" in stats:
            self.defense = self.base_stats["defense"] + stats["defense"]
        if "attack" in stats:
            self.attack = self.base_stats["attack"] + stats["attack"]
        if "hp_bonus" in stats:
            self.max_hp = self.base_stats["max_hp"] + stats["hp_bonus"]
            self.hp = min(self.hp, self.max_hp)
        if "stealth" in stats:
            self.stealth_bonus += stats["stealth"]
        if "noise_penalty" in stats:
            self.noise_level = max(0, self.noise_level + stats["noise_penalty"])

        # Play item sound
        audio_manager.play_item_sound(item)
        type_text(f"You equipped {item}!", sound=sound)
        audio_manager.play_confirmation(True)

    def unequip_item(self, item, sound=True):
        if item not in Equipment.EQUIPMENT_STATS:
            return

        equipment_type = Equipment.EQUIPMENT_STATS[item]["type"]

        # Remove equipment bonuses
        stats = Equipment.EQUIPMENT_STATS[item]
        if "defense" in stats:
            self.defense = self.base_stats["defense"]
        if "attack" in stats:
            self.attack = self.base_stats["attack"]
        if "hp_bonus" in stats:
            self.max_hp = self.base_stats["max_hp"]
            self.hp = min(self.hp, self.max_hp)
        if "stealth" in stats:
            self.stealth_bonus -= stats["stealth"]
        if "noise_penalty" in stats:
            self.noise_level = max(0, self.noise_level - stats["noise_penalty"])

        # Add to inventory
        self.inventory[item] = self.inventory.get(item, 0) + 1
        self.equipped[equipment_type] = None

        # Play item sound
        audio_manager.play_item_sound(item)
        type_text(f"You unequipped {item}!", sound=sound)
        audio_manager.play_confirmation(True)

    def deconstruct_item(self, item, sound=True):
        if item not in Equipment.DECONSTRUCT_RECIPES:
            type_text("This item cannot be deconstructed!", sound=sound)
            audio_manager.play_confirmation(False)
            return

        recipe = Equipment.DECONSTRUCT_RECIPES[item]
        success_chance = 0.6 + (self.crafting_level * 0.05)

        type_text(f"\nYou attempt to deconstruct {item}...", sound=sound)
        time.sleep(1)

        if random.random() > success_chance:
            type_text("Deconstruction failed! The item was destroyed.", sound=sound)
            audio_manager.play_confirmation(False)
            self.inventory[item] -= 1
            if self.inventory[item] <= 0:
                del self.inventory[item]
            return

        # Successful deconstruction
        type_text("Deconstruction successful! You recovered:", sound=sound)
        audio_manager.play_confirmation(True)
        for material, amount in recipe.items():
            self.inventory[material] = self.inventory.get(material, 0) + amount
            type_text(f"- {amount} {material}", sound=sound)
            # Play material sound if available
            audio_manager.play_item_sound(material)

        self.inventory[item] -= 1
        if self.inventory[item] <= 0:
            del self.inventory[item]

        # Gain crafting EXP
        exp_gained = 15 + (self.crafting_level * 3)
        self.gain_crafting_exp(exp_gained)

    def display_lore(self, sound=True):
        if not self.found_lore:
            type_text("\nYou haven't found any lore documents yet.", sound=sound)
            return

        type_text(f"\n=== LORE DOCUMENTS FOUND ({len(self.found_lore)}) ===", sound=sound)
        for i, lore in enumerate(self.found_lore, 1):
            type_text(f"{i}. {lore['title']}", sound=sound)

        try:
            _clear_rshift()
            choice = int(input("\nSelect document to read (0 to cancel): "))
            if choice == 0:
                return
            elif 1 <= choice <= len(self.found_lore):
                lore = self.found_lore[choice-1]
                type_text(f"\n=== {lore['title'].upper()} ===", sound=False)  # No sound for reading
                type_text(lore['content'], sound=False)  # No sound for reading
                # Play document reading sound
                audio_manager.play_dialog("story", "document")
            else:
                type_text("Invalid selection!")
                audio_manager.play_confirmation(False)
        except ValueError:
            type_text("Invalid input!")
            audio_manager.play_confirmation(False)

    def display_collectables(self, sound=True):
        if not self.collectables:
            type_text("\nYou haven't found any collectables yet.", sound=sound)
            return

        type_text(f"\n=== COLLECTABLES FOUND ({len(self.collectables)}) ===", sound=sound)
        for i, (collectable, details) in enumerate(self.collectables.items(), 1):
            type_text(f"{i}. {collectable}", sound=sound)

        try:
            _clear_rshift()
            choice = int(input("\nSelect collectable to view (0 to cancel): "))
            if choice == 0:
                return
            elif 1 <= choice <= len(self.collectables):
                collectable_name = list(self.collectables.keys())[choice-1]
                details = self.collectables[collectable_name]
                type_text(f"\n=== {collectable_name.upper()} ===", sound=False)  # No sound for reading
                type_text(f"{details['description']}", sound=False)  # No sound for reading
                type_text(f"\n{details['quote']}", sound=False)  # No sound for reading
                # Play collectable sound
                audio_manager.play_item_sound("collectable")
            else:
                type_text("Invalid selection!")
                audio_manager.play_confirmation(False)
        except ValueError:
            type_text("Invalid input!")
            audio_manager.play_confirmation(False)

    def use_item(self, item, sound=True):
        item_effects = {
            "Purified Water": {"heal": 30, "mp_heal": 0, "cure": False, "message": f"{self.name} used Purified Water and recovered 30 HP!"},
            "Bandage": {"heal": 15, "mp_heal": 0, "cure": False, "message": f"{self.name} used a Bandage and recovered 15 HP!"},
            "Antidote": {"heal": 0, "mp_heal": 0, "cure": True, "message": f"{self.name} used an Antidote and cured the infection!"},
            "Medkit": {"heal": 50, "mp_heal": 0, "cure": False, "message": f"{self.name} used a Medkit and recovered 50 HP!"},
            "Advanced Medkit": {"heal": 80, "mp_heal": 0, "cure": True, "message": f"{self.name} used an Advanced Medkit and recovered 80 HP and cured the infection!"},
            "Rabbit's Pendant": {"heal": 0, "mp_heal": 0, "cure": False, "message": f"{self.name} used a Rabbit's Pendant! Next 3 parries will have 70-100% success chance!"},
            "Purified Herbs": {"heal": 25, "mp_heal": 10, "cure": False, "message": f"{self.name} used Purified Herbs and recovered 25 HP and 10 MP!"},
            "Molotov Cocktail": {"heal": 0, "mp_heal": 0, "cure": False, "message": f"{self.name} throws a Molotov Cocktail!"}
        }

        if item not in self.inventory or self.inventory[item] <= 0:
            type_text("You don't have that item!", sound=sound)
            audio_manager.play_confirmation(False)
            return False

        effect = item_effects.get(item)
        if not effect:
            type_text("This item cannot be used!", sound=sound)
            audio_manager.play_confirmation(False)
            return False

        if item == "Rabbit's Pendant":
            if self.parry_boost_uses > 0:
                type_text("You already have an active Rabbit's Pendant effect!", sound=sound)
                audio_manager.play_confirmation(False)
                return False
            self.parry_boost_active = True
            self.parry_boost_uses = 3
        elif item == "Molotov Cocktail":
            # Molotov cocktail can be used in battle - it will be handled in the battle function
            type_text("Molotov Cocktail can only be used during battle!", sound=sound)
            audio_manager.play_confirmation(False)
            return False
        else:
            if effect["heal"] > 0:
                heal_amount = effect["heal"]
                if self.hp < self.max_hp:
                    self.hp = min(self.max_hp, self.hp + heal_amount)
                    type_text(f"Recovered {heal_amount} HP!", sound=sound)
                else:
                    type_text("You're already at full health!", sound=sound)
                    audio_manager.play_confirmation(False)
                    return False

            if effect["mp_heal"] > 0:
                mp_heal_amount = effect["mp_heal"]
                if self.mp < self.max_mp:
                    self.mp = min(self.max_mp, self.mp + mp_heal_amount)
                    type_text(f"Recovered {mp_heal_amount} MP!", sound=sound)

            if effect["cure"] and self.infected and not self.is_infected_class:
                self.infected = False
                self.infection_timer = 0
                type_text("Infection cured!", sound=sound)

        self.inventory[item] -= 1

        # Play item sound
        audio_manager.play_item_sound(item)
        type_text(effect["message"], sound=sound)
        audio_manager.play_confirmation(True)
        return True

    def gain_exp(self, amount, sound=True):
        self.exp += amount
        type_text(f"{self.name} gained {amount} experience!", sound=sound)
        audio_manager.play_confirmation(True)

        if self.exp >= self.exp_to_next:
            self.level_up()

    def gain_crafting_exp(self, amount, sound=True):
        self.crafting_exp += amount
        type_text(f"{self.name} gained {amount} crafting experience!", sound=sound)
        audio_manager.play_confirmation(True)

        if self.crafting_exp >= self.crafting_exp_to_next:
            self.crafting_level_up()

    def level_up(self, sound=True):
        self.level += 1
        self.exp -= self.exp_to_next
        self.exp_to_next = int(self.exp_to_next * 1.5)
        self.skill_points += 1

        # Stat increases
        self.base_stats["max_hp"] += random.randint(8, 12)
        self.base_stats["attack"] += random.randint(2, 4)
        self.base_stats["defense"] += random.randint(1, 3)
        self.base_stats["magic"] += random.randint(1, 3)

        # Apply base stats and equipment bonuses
        self.max_hp = self.base_stats["max_hp"]
        self.attack = self.base_stats["attack"]
        self.defense = self.base_stats["defense"]
        self.magic = self.base_stats["magic"]

        # Apply equipment bonuses if any
        for slot, item in self.equipped.items():
            if item and item in Equipment.EQUIPMENT_STATS:
                stats = Equipment.EQUIPMENT_STATS[item]
                if "defense" in stats:
                    self.defense += stats["defense"]
                if "attack" in stats:
                    self.attack += stats["attack"]
                if "hp_bonus" in stats:
                    self.max_hp += stats["hp_bonus"]

        # Restore HP and MP on level up
        self.hp = self.max_hp
        self.mp = self.max_mp

        # Learn new skills at certain levels
        if self.level == 3:
            new_skills = {
                "Survivor": "Bash",
                "Scavenger": "Silent Takedown",
                "Medic": "Group Heal",
                "Infected": "Viral Surge"
            }
            if self.job_class in new_skills:
                self.spells.append(new_skills[self.job_class])
                type_text(f"{self.name} learned a new skill: {new_skills[self.job_class]}!", sound=sound)

        # Play level up sound
        audio_manager.play_item_sound("level_up")
        type_text(f"\nLevel up! {self.name} is now level {self.level}!", sound=sound)
        type_text(f"HP increased to {self.max_hp}!", sound=sound)
        type_text(f"MP increased to {self.max_mp}!", sound=sound)
        type_text(f"Attack increased to {self.attack}!", sound=sound)
        type_text(f"Defense increased to {self.defense}!", sound=sound)
        type_text(f"Magic increased to {self.magic}!", sound=sound)
        type_text(f"You gained 1 skill point! Total: {self.skill_points}", sound=sound)

    def crafting_level_up(self, sound=True):
        self.crafting_level += 1
        self.crafting_exp -= self.crafting_exp_to_next
        self.crafting_exp_to_next = int(self.crafting_exp_to_next * 1.5)

        # Increase parry chance with crafting level
        self.parry_chance = min(0.5, 0.3 + (self.crafting_level * 0.05))

        # Unlock new recipes at certain crafting levels
        new_recipes = {
            2: {"Advanced Medkit": {"Medkit": 1, "Herbs": 3, "Electronic Parts": 1}},
            3: {"Reinforced Armor": {"Reinforced Vest": 1, "Scrap Metal": 5, "Mechanical Parts": 2}},
            4: {"Silent Boots": {"Cloth": 4, "Scrap Metal": 2}},
            5: {"Sturdy Backpack": {"Cloth": 5, "Scrap Metal": 3, "Electronic Parts": 1}},
            6: {"Zombie Bait": {"Herbs": 2, "Electronic Parts": 1, "Mechanical Parts": 1}}
        }

        if self.crafting_level in new_recipes:
            for recipe, materials in new_recipes[self.crafting_level].items():
                self.crafting_recipes[recipe] = materials
                type_text(f"{self.name} learned to craft {recipe}!", sound=sound)

        # Play crafting level up sound
        audio_manager.play_item_sound("crafting_level")
        type_text(f"\nCrafting level up! {self.name} is now crafting level {self.crafting_level}!", sound=sound)
        type_text(f"Parry chance increased to {int(self.parry_chance * 100)}%!", sound=sound)

    def show_skill_tree(self, sound=True):
        skill_trees = {
            "Survivor": {
                "Combat": {
                    "Heavy Swing": {"cost": 1, "description": "Deal 150% damage with your next attack", "requires": []},
                    "Second Wind": {"cost": 2, "description": "Recover 20% HP when below 30% health", "requires": ["Heavy Swing"]},
                    "Unbreakable": {"cost": 3, "description": "Reduce all damage by 15%", "requires": ["Second Wind"]}
                },
                "Survival": {
                    "Forage": {"cost": 1, "description": "Find extra materials when scavenging", "requires": []},
                    "Keen Eye": {"cost": 2, "description": "Higher chance to find rare items", "requires": ["Forage"]},
                    "Resourceful": {"cost": 3, "description": "Crafting requires 20% fewer materials", "requires": ["Keen Eye"]}
                }
            },
            "Scavenger": {
                "Stealth": {
                    "Silent Movement": {"cost": 1, "description": "Reduced noise when moving", "requires": []},
                    "Shadow Blend": {"cost": 2, "description": "Higher chance to avoid encounters", "requires": ["Silent Movement"]},
                    "Ghost": {"cost": 3, "description": "Can sometimes completely avoid detection", "requires": ["Shadow Blend"]}
                },
                "Traps": {
                    "Improved Traps": {"cost": 1, "description": "Traps deal 50% more damage", "requires": []},
                    "Quick Setup": {"cost": 2, "description": "Set traps in half the time", "requires": ["Improved Traps"]},
                    "Master Trapper": {"cost": 3, "description": "Can set multiple traps at once", "requires": ["Quick Setup"]}
                }
            },
            "Medic": {
                "Healing": {
                    "Improved Healing": {"cost": 1, "description": "Healing skills are 25% more effective", "requires": []},
                    "Preventative Care": {"cost": 2, "description": "Reduced chance of infection", "requires": ["Improved Healing"]},
                    "Field Surgery": {"cost": 3, "description": "Can heal critical injuries in combat", "requires": ["Preventative Care"]}
                },
                "Alchemy": {
                    "Herbal Knowledge": {"cost": 1, "description": "Identify rare herbs with special properties", "requires": []},
                    "Purification": {"cost": 2, "description": "Create stronger healing items", "requires": ["Herbal Knowledge"]},
                    "Elixir Mastery": {"cost": 3, "description": "Create powerful buff potions", "requires": ["Purification"]}
                }
            },
            "Infected": {
                "Viral Evolution": {
                    "Enhanced Senses": {"cost": 1, "description": "Increased stealth and detection", "requires": []},
                    "Regenerative Tissue": {"cost": 2, "description": "Passive health regeneration", "requires": ["Enhanced Senses"]},
                    "Adaptive Mutations": {"cost": 3, "description": "Increased mutation chance and benefits", "requires": ["Regenerative Tissue"]}
                },
                "Viral Control": {
                    "Controlled Hunger": {"cost": 1, "description": "Reduced night health drain", "requires": []},
                    "Viral Mastery": {"cost": 2, "description": "Viral skills are 25% more effective", "requires": ["Controlled Hunger"]},
                    "Alpha Strain": {"cost": 3, "description": "Zombies are less aggressive toward you", "requires": ["Viral Mastery"]}
                }
            }
        }

        type_text(f"\n=== SKILL TREE ===", sound=sound)
        type_text(f"Available Skill Points: {self.skill_points}", sound=sound)

        tree = skill_trees[self.job_class]
        for category, skills in tree.items():
            type_text(f"\n{category}:", sound=sound)
            for skill, details in skills.items():
                learned = " [LEARNED]" if skill in self.learned_skills else ""
                type_text(f"  {skill} (Cost: {details['cost']}){learned}", sound=sound)
                type_text(f"    - {details['description']}", sound=sound)

        if self.skill_points > 0:
            type_text(f"\nEnter the name of a skill to learn it (or 'back' to return):", sound=sound)
            _clear_rshift()
            choice = input("Skill: ").strip()

            if choice.lower() == 'back':
                return

            # Find the skill in the tree
            for category, skills in tree.items():
                if choice in skills:
                    skill_data = skills[choice]

                    # Check if already learned
                    if choice in self.learned_skills:
                        type_text("You've already learned this skill!", sound=sound)
                        audio_manager.play_confirmation(False)
                        return

                    # Check requirements
                    for req in skill_data['requires']:
                        if req not in self.learned_skills:
                            type_text(f"You need to learn {req} first!", sound=sound)
                            audio_manager.play_confirmation(False)
                            return

                    # Check if enough skill points
                    if self.skill_points >= skill_data['cost']:
                        self.skill_points -= skill_data['cost']
                        self.learned_skills.append(choice)
                        type_text(f"You learned {choice}!", sound=sound)
                        audio_manager.play_confirmation(True)

                        # Apply skill effects
                        if choice == "Silent Movement":
                            self.stealth_bonus += 15
                        elif choice == "Shadow Blend":
                            self.stealth_bonus += 25
                        elif choice == "Ghost":
                            self.stealth_bonus += 40
                        elif choice == "Controlled Hunger":
                            self.night_health_drain = max(1, self.night_health_drain - 1)
                        elif choice == "Adaptive Mutations":
                            self.mutation_chance += 0.1
                    else:
                        type_text("Not enough skill points!", sound=sound)
                        audio_manager.play_confirmation(False)
                    return

            type_text("Skill not found!", sound=sound)
            audio_manager.play_confirmation(False)

    def craft_item(self, recipe_name, sound=True):
        if recipe_name not in self.crafting_recipes:
            type_text("You don't know how to craft that!", sound=sound)
            audio_manager.play_confirmation(False)
            return False

        recipe = self.crafting_recipes[recipe_name]

        # Check if player has all required materials
        for material, amount_needed in recipe.items():
            if material not in self.inventory or self.inventory[material] < amount_needed:
                type_text(f"You don't have enough {material} to craft {recipe_name}!", sound=sound)
                audio_manager.play_confirmation(False)
                return False

        # Crafting process with chance of failure
        base_success_chance = 0.7 + (self.crafting_level * 0.05)

        # Add detailed crafting description
        type_text(f"\nYou begin crafting {recipe_name}...", sound=sound)
        time.sleep(1)

        if recipe_name == "Reinforced Vest":
            type_text("Gathering scrap metal and cloth...", sound=sound)
            time.sleep(1)
            type_text("Measuring and cutting the materials...", sound=sound)
            time.sleep(1)
            type_text("Reinforcing the vest with additional layers...", sound=sound)
        elif recipe_name == "Sharpened Weapon":
            type_text("Selecting the right piece of scrap metal...", sound=sound)
            time.sleep(1)
            type_text("Grinding the edge to a sharp point...", sound=sound)
            time.sleep(1)
            type_text("Testing the balance and sharpness...", sound=sound)
        elif recipe_name == "Medkit":
            type_text("Preparing the herbs for medicinal use...", sound=sound)
            time.sleep(1)
            type_text("Sterilizing the cloth with purified water...", sound=sound)
            time.sleep(1)
            type_text("Assembling the medical components...", sound=sound)
        elif recipe_name == "Molotov Cocktail":
            type_text("Gathering herbs, cloth, and purified water...", sound=sound)
            time.sleep(1)
            type_text("Creating the flammable mixture...", sound=sound)
            time.sleep(1)
            type_text("Preparing the cloth wick...", sound=sound)
        elif recipe_name == "Purified Herbs":
            type_text("Cleaning the herbs thoroughly...", sound=sound)
            time.sleep(1)
            type_text("Applying alchemical purification techniques...", sound=sound)
            time.sleep(1)
            type_text("Testing the herb potency...", sound=sound)
        else:
            type_text("Assembling the components...", sound=sound)
            time.sleep(1)
            type_text("Following the crafting process...", sound=sound)
            time.sleep(1)

        time.sleep(1)

        if random.random() > base_success_chance:
            # Crafting failed - lose some materials
            type_text("Crafting failed! You lost some materials...", sound=sound)
            audio_manager.play_confirmation(False)
            for material, amount_needed in recipe.items():
                lost_amount = max(1, amount_needed // 2)
                self.inventory[material] -= lost_amount
                if self.inventory[material] <= 0:
                    del self.inventory[material]
                type_text(f"Lost {lost_amount} {material}!", sound=sound)
            return False

        # Deduct materials and add crafted item
        for material, amount_needed in recipe.items():
            self.inventory[material] -= amount_needed
            if self.inventory[material] <= 0:
                del self.inventory[material]

        # Add crafted item to inventory
        self.inventory[recipe_name] = self.inventory.get(recipe_name, 0) + 1

        # Gain crafting EXP
        exp_gained = 20 + (self.crafting_level * 5)
        self.gain_crafting_exp(exp_gained)

        # Play crafting success sound
        audio_manager.play_item_sound("crafting_success")
        type_text(f"You successfully crafted a {recipe_name}!", sound=sound)
        audio_manager.play_confirmation(True)
        return True

    def get_dialogue(self, is_night=False):
        if self.is_infected_class and is_night:
            return random.choice(self.INFECTED_NIGHT_DIALOGUE)
        return random.choice(self.NIGHT_DIALOGUE) if is_night else random.choice(self.dialogue)

    def process_infection(self, sound=True):
        if self.infected and not self.is_infected_class:
            self.infection_timer -= 1
            if self.infection_timer <= 0:
                self.hp -= self.infection_damage
                type_text(f"The infection spreads! You take {self.infection_damage} damage!", sound=sound)
                audio_manager.play_item_sound("infection_damage")
                self.infection_timer = 3

                if self.hp <= 0:
                    type_text(f"The infection has overwhelmed you...", sound=sound)
                    return False
            else:
                type_text(f"The infection is spreading... {self.infection_timer} turns until next damage", sound=sound)
        return True

    def process_night_effects(self, hours, sound=True):
        """Process night effects for Infected class"""
        if self.is_infected_class:
            # Health drain at night
            drain_amount = self.night_health_drain * hours
            self.hp -= drain_amount
            type_text(f"The viral strain consumes your energy at night... Lost {drain_amount} HP.", sound=sound)
            audio_manager.play_item_sound("viral_drain")

            # Chance to mutate each hour
            for hour in range(hours):
                if random.random() < self.mutation_chance:
                    self.gain_mutation(sound=sound)

            if self.hp <= 0:
                type_text(f"The viral strain has consumed you completely...", sound=sound)
                return False
        return True

    def gain_mutation(self, sound=True):
        """Gain a random mutation for Infected class"""
        mutations = {
            "Enhanced Claws": {"attack": 3, "description": "+3 Attack from sharpened appendages"},
            "Tough Hide": {"defense": 3, "description": "+3 Defense from thickened skin"},
            "Regenerative Cells": {"max_hp": 10, "description": "+10 Max HP from accelerated healing"},
            "Hyper Senses": {"stealth": 20, "description": "+20 Stealth from enhanced awareness"},
            "Viral Potency": {"magic": 3, "description": "+3 Magic from concentrated virus"},
            "Adrenal Glands": {"attack": 2, "max_hp": 5, "description": "+2 Attack, +5 Max HP from adrenaline production"}
        }

        available_mutations = [m for m in mutations.keys() if m not in self.mutations]

        if not available_mutations:
            type_text(f"You've reached your maximum mutations!", sound=sound)
            return

        mutation = random.choice(available_mutations)
        self.mutations.append(mutation)
        benefits = mutations[mutation]
        self.mutation_benefits[mutation] = benefits

        # Apply mutation benefits
        if "attack" in benefits:
            self.attack += benefits["attack"]
            self.base_stats["attack"] += benefits["attack"]
        if "defense" in benefits:
            self.defense += benefits["defense"]
            self.base_stats["defense"] += benefits["defense"]
        if "max_hp" in benefits:
            self.max_hp += benefits["max_hp"]
            self.base_stats["max_hp"] += benefits["max_hp"]
            self.hp += benefits["max_hp"]
        if "magic" in benefits:
            self.magic += benefits["magic"]
            self.base_stats["magic"] += benefits["magic"]
        if "stealth" in benefits:
            self.stealth_bonus += benefits["stealth"]

        # Play mutation sound
        audio_manager.play_item_sound("mutation")
        type_text(f"You've developed a new mutation: {mutation}!", sound=sound)
        type_text(f"{benefits['description']}", sound=sound)

class Zombie:
    def __init__(self, name, hp, attack, defense, change_reward, exp_reward, infection_chance=0.1, is_boss=False):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.attack = attack
        self.defense = defense
        self.change_reward = change_reward
        self.exp_reward = exp_reward
        self.infection_chance = infection_chance
        self.on_fire = False
        self.fire_turns = 0
        self.grappling = False
        self.is_boss = is_boss
        self.reward_type = None

        # For boss zombies, determine reward type
        if is_boss:
            self.determine_reward_type()

    def determine_reward_type(self):
        # Boss zombies have a 60% chance for resource rewards, 40% for XP rewards
        if random.random() < 0.6:
            self.reward_type = 'resources'
            # Reduce XP for resource-rich bosses
            self.exp_reward = max(10, int(self.exp_reward * 0.7))
        else:
            self.reward_type = 'xp'
            # Reduce resources for XP-rich bosses
            self.change_reward = max(15, int(self.change_reward * 0.6))

    def display_stats(self, sound=True):
        status = " [ON FIRE]" if self.on_fire else " [GRAPPLING]" if self.grappling else ""
        boss_indicator = " [BOSS]" if self.is_boss else ""
        type_text(f"\n{self.name} - HP: {self.hp}/{self.max_hp}{status}{boss_indicator}", sound=sound)
        # Play zombie sound based on type
        if self.is_boss:
            audio_manager.play_zombie_sound("boss", "roar")
        else:
            audio_manager.play_zombie_sound("generic", "groan")

# ------------------ NEW ENEMY TYPES ------------------
class Animal:
    def __init__(self, name, hp, attack, defense, change_reward, exp_reward, special_effect=None):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.attack = attack
        self.defense = defense
        self.change_reward = change_reward
        self.exp_reward = exp_reward
        self.special_effect = special_effect

    def display_stats(self, sound=True):
        type_text(f"\n{self.name} - HP: {self.hp}/{self.max_hp}", sound=sound)

class Insect:
    def __init__(self, name, hp, attack, defense, change_reward, exp_reward, special_effect=None):
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.attack = attack
        self.defense = defense
        self.change_reward = change_reward
        self.exp_reward = exp_reward
        self.special_effect = special_effect

    def display_stats(self, sound=True):
        type_text(f"\n{self.name} - HP: {self.hp}/{self.max_hp}", sound=sound)


# ===========================================================================
# PROCEDURAL GENERATION ENGINE
# Generates unique settlements, zombies, and encounters each day.
# Seeded by (day + location) so results are varied but never random-undefined.
# ===========================================================================

import hashlib as _hashlib

def _proc_seed(day, salt=""):
    """Deterministic seed from day + salt string."""
    raw = f"{day}{salt}"
    return int(_hashlib.md5(raw.encode()).hexdigest(), 16) % (2**32)


# ---------------------------------------------------------------------------
# PROCEDURAL ZOMBIE GENERATOR
# ---------------------------------------------------------------------------

_ZOMBIE_PREFIXES = [
    "Bloated", "Charred", "Hollow", "Festering", "Gaunt", "Rotting",
    "Lurching", "Screaming", "Shambling", "Pallid", "Maddened", "Withered",
    "Mutilated", "Blackened", "Rabid", "Sinewy", "Corroded", "Viral",
]
_ZOMBIE_TYPES = [
    "Corpse", "Carrier", "Walker", "Crawler", "Husk", "Wraith",
    "Brute", "Stalker", "Runner", "Aberration", "Revenant", "Shade",
    "Amalgam", "Prophet", "Titan", "Drifter", "Horror", "Specter",
]
_BOSS_PREFIXES = [
    "Apex", "Ancient", "Prime", "Colossal", "Sovereign", "Abyssal",
    "Primordial", "Vile", "Nightmare", "Infernal",
]
_BOSS_TYPES = [
    "Behemoth", "Dreadnought", "Colossus", "Leviathan", "Monstrosity",
    "Overlord", "Abomination", "Tyrant", "Harbinger", "Patriarch",
]
_ZOMBIE_FLAVOUR = [
    "Its eyes glow a sickly yellow.",
    "Patches of bone show through rotting flesh.",
    "A low, rattling moan escapes its throat.",
    "Black veins spider-web across its face.",
    "It moves with unsettling, jerky speed.",
    "Thick grey fluid drips from its mouth.",
    "Its limbs are grotesquely elongated.",
    "A smell of rot and copper fills the air.",
    "It tilts its head and stares directly at you.",
    "Flies swarm the gaping wound in its side.",
    "Its jaw is unhinged, dragging against the ground.",
    "It lets out a shriek that curdles your blood.",
]


def generate_zombie(day, index=0, is_boss=False, danger=1.0):
    """
    Procedurally generate a unique Zombie instance.
    danger: float multiplier 0.5 (easy) to 3.0 (brutal) scaling stats.
    """
    rng = random.Random(_proc_seed(day, f"zombie{index}{is_boss}"))

    if is_boss:
        name = rng.choice(_BOSS_PREFIXES) + " " + rng.choice(_BOSS_TYPES)
        base_hp   = int(rng.randint(100, 200) * danger)
        base_atk  = int(rng.randint(22, 40)  * danger)
        base_def  = int(rng.randint(10, 20)  * danger)
        change_r  = int(rng.randint(80, 160) * danger)
        exp_r     = int(rng.randint(60, 120) * danger)
        inf_ch    = round(min(0.9, rng.uniform(0.3, 0.7)), 2)
    else:
        name = rng.choice(_ZOMBIE_PREFIXES) + " " + rng.choice(_ZOMBIE_TYPES)
        base_hp   = int(rng.randint(20, 55)  * danger)
        base_atk  = int(rng.randint(6, 16)   * danger)
        base_def  = int(rng.randint(1, 6)    * danger)
        change_r  = int(rng.randint(8, 30)   * danger)
        exp_r     = int(rng.randint(6, 25)   * danger)
        inf_ch    = round(min(0.6, rng.uniform(0.05, 0.3)), 2)

    flavour = rng.choice(_ZOMBIE_FLAVOUR)
    z = Zombie(name, base_hp, base_atk, base_def, change_r, exp_r, inf_ch, is_boss=is_boss)
    z._flavour = flavour
    return z


def get_daily_zombies(day, danger=1.0):
    """
    Return a daily set of 5 regular + 5 boss procedural zombies.
    Replaces get_zombie_types() pool for the current day.
    """
    regulars = [generate_zombie(day, i, is_boss=False, danger=danger) for i in range(5)]
    bosses   = [generate_zombie(day, i, is_boss=True,  danger=danger) for i in range(5)]
    return regulars + bosses


# ---------------------------------------------------------------------------
# PROCEDURAL SETTLEMENT GENERATOR
# ---------------------------------------------------------------------------

_SETTLE_ADJ = [
    "Crumbling", "Fortified", "Abandoned", "Overgrown", "Scorched",
    "Flooded", "Fog-Covered", "Rusted", "Makeshift", "Silent",
    "Hidden", "Quarantined", "Barricaded", "Gutted", "Looted",
]
_SETTLE_NOUNS = [
    "Outpost", "Waypoint", "Stronghold", "Refuge", "Colony",
    "Enclave", "Depot", "Compound", "Settlement", "Holdout",
    "Bastion", "Checkpoint", "Camp", "Station", "Haven",
]
_SETTLE_DESCS = [
    "Survivors move between cover, eyes scanning the perimeter.",
    "The smell of smoke and unwashed bodies hangs in the air.",
    "A hand-painted sign warns: 'INFECTED — DO NOT ENTER'. Someone crossed it out.",
    "Makeshift walls of corrugated iron and salvaged cars ring the area.",
    "Children peek from behind a rusted school bus. Adults keep weapons close.",
    "A generator coughs and sputters in the distance. Power, but barely.",
    "Tarps and rope form a market of sorts — goods spread on folding tables.",
    "Watch fires burn on elevated platforms. Tired eyes follow your approach.",
    "Half the structures here are rubble. The other half are held up by hope.",
    "A painted mural covers one wall — faces of the lost, names beneath each.",
    "Dogs prowl the perimeter. They were trained before the fall, still remember.",
    "The gate opens a crack. A rifle barrel slides through the gap first.",
]
_TRADER_LINES = [
    "Got a few things left. Buyers are running low too.",
    "Supplies are scarce. Got what you need, if the price is right.",
    "Trade fast. I don't like standing in the open long.",
    "Been a rough week. But I always manage to find something worth selling.",
    "Don't ask where I found it. You want it or not?",
    "Last of the good stuff. After this, I'm out.",
]
_WORKSHOP_LINES = [
    "Give me something to work with and I'll make it better.",
    "My hands are the only tools still working around here.",
    "Reinforced gear keeps you alive. Simple as that.",
    "Scrap and sweat — that's all crafting is now.",
    "I can improve it. Costs supplies, but worth the edge.",
]
_SANCTUARY_LINES = [
    "Safe here. For a price. Nothing's free anymore.",
    "Beds are full, but I can find you a corner.",
    "Rest now. The dead never do.",
    "Sleep with one eye open. Even here.",
    "Quiet for now. Enjoy it while it lasts.",
]
_ALCHEMIST_LINES = [
    "I can purify that for you. Might even improve it.",
    "Plants hold power most people forgot about.",
    "Crude materials, careful hands — remarkable results.",
    "The old chemistry still applies. I paid attention in school.",
    "Bring me herbs and I'll bring you something useful.",
]

# Trader stock tables — randomised per settlement per day
_TRADE_POOLS = {
    "medical":   ["Bandage", "Antidote", "Medkit", "Herbs", "Purified Water"],
    "combat":    ["Molotov Cocktail", "Scrap Metal", "Mechanical Parts"],
    "general":   ["Cloth", "Electronic Parts", "Rabbit's Pendant", "Purified Water"],
}
_SETTLE_TYPES = [
    "refugee_camp", "abandoned_town", "military_outpost",
    "barricaded_city", "roadside_junkyard"
]
_SETTLE_SERVICES = ["trader", "workshop", "sanctuary", "alchemist"]


def generate_settlement(day, slot=0):
    """
    Procedurally generate a unique settlement dict compatible with
    visit_settlement(). Each day+slot combo produces a distinct location.
    """
    rng = random.Random(_proc_seed(day, f"settle{slot}"))

    adj   = rng.choice(_SETTLE_ADJ)
    noun  = rng.choice(_SETTLE_NOUNS)
    name  = f"{adj} {noun}"
    desc  = rng.choice(_SETTLE_DESCS)

    # Danger level scales with day number, capped at 3.0
    danger = min(3.0, 1.0 + (day - 1) * 0.08)

    # Services available — always at least trader; others 60–80% chance
    services = ["trader"]
    for svc in ["workshop", "sanctuary", "alchemist"]:
        if rng.random() < 0.70:
            services.append(svc)

    # Loot table: pick 3–5 items from pools weighted by settlement character
    pool_key = rng.choice(list(_TRADE_POOLS.keys()))
    loot_items = rng.sample(_TRADE_POOLS[pool_key] + _TRADE_POOLS["general"], k=min(5, len(_TRADE_POOLS[pool_key] + _TRADE_POOLS["general"])))
    price_range = (max(3, int(5 * danger)), max(8, int(25 * danger)))

    # Pick a base settlement type for audio/NPC pool fallback
    base_type = rng.choice(_SETTLE_TYPES)

    # NPC count for this settlement: 2–5 unique NPCs
    npc_count = rng.randint(2, 5)

    return {
        "name":                name,
        "description":         desc,
        "base_type":           base_type,
        "danger":              danger,
        "services":            services,
        "loot_items":          loot_items,
        "price_range":         price_range,
        "npc_count":           npc_count,
        "trader_dialogue":     f"Trader: '{rng.choice(_TRADER_LINES)}'",
        "workshop_dialogue":   f"Workshop: '{rng.choice(_WORKSHOP_LINES)}'",
        "sanctuary_dialogue":  f"Sanctuary: '{rng.choice(_SANCTUARY_LINES)}'",
        "alchemist_dialogue":  f"Alchemist: '{rng.choice(_ALCHEMIST_LINES)}'",
        # Legacy key so existing visit_settlement dict lookups still work
        "name_full":           name,
    }


# ---------------------------------------------------------------------------
# PROCEDURAL ENCOUNTER GENERATOR
# ---------------------------------------------------------------------------

_ENCOUNTER_EVENTS = [
    {"type": "loot",    "msg": "You find an untouched supply cache hidden under debris.",   "loot": ("Bandage", 2)},
    {"type": "loot",    "msg": "A backpack caught on a fence — still packed.",              "loot": ("Purified Water", 2)},
    {"type": "loot",    "msg": "Vending machine, glass cracked. A few cans inside.",       "loot": ("Herbs", 3)},
    {"type": "loot",    "msg": "Jacket left hanging on a door. Something heavy in the pocket.", "loot": ("Scrap Metal", 4)},
    {"type": "hazard",  "msg": "You slip through a rotted floor. Something cuts your leg.", "dmg": (8, 18)},
    {"type": "hazard",  "msg": "A gas leak hisses nearby. Your eyes sting and burn.",       "dmg": (5, 12)},
    {"type": "hazard",  "msg": "You trigger a tripwire. A can avalanche crashes down.",     "dmg": (10, 20), "noise": 30},
    {"type": "hazard",  "msg": "Broken glass. You misjudge the dark. Deep cut.",            "dmg": (6, 14)},
    {"type": "neutral", "msg": "A photograph on the ground. A family. You leave it.",       "dmg": None},
    {"type": "neutral", "msg": "Graffiti on the wall: 'THEY REMEMBER FACES'. You move on.","dmg": None},
    {"type": "neutral", "msg": "A radio crackles in an empty room. Static. Then silence.",  "dmg": None},
    {"type": "neutral", "msg": "Animal tracks in the dust. Something still living here.",   "dmg": None},
    {"type": "bonus",   "msg": "A survivor's journal. Last entry: coordinates.",            "change": (15, 35)},
    {"type": "bonus",   "msg": "Hidden stash behind a false wall. Former owner won't mind.","loot": ("Medkit", 1)},
    {"type": "bonus",   "msg": "Working hand-crank radio. Faint signal — morale lifts.",    "hp": (5, 15)},
]


def generate_encounter(day, index=0):
    """Return a procedural encounter event dict for the given day."""
    rng = random.Random(_proc_seed(day, f"enc{index}"))
    event = rng.choice(_ENCOUNTER_EVENTS).copy()
    # Randomise numeric ranges
    if "dmg" in event and event["dmg"]:
        lo, hi = event["dmg"]
        event["dmg_value"] = rng.randint(lo, hi)
    if "loot" in event and event["loot"]:
        item, qty = event["loot"]
        event["loot_item"]  = item
        event["loot_qty"]   = qty
    if "change" in event:
        lo, hi = event["change"]
        event["change_value"] = rng.randint(lo, hi)
    if "hp" in event:
        lo, hi = event["hp"]
        event["hp_value"] = rng.randint(lo, hi)
    if "noise" in event:
        event["noise_value"] = event["noise"]
    return event


def apply_encounter(player, event, sound=True):
    """Apply a generated encounter event to the player."""
    type_text(f"\n{event['msg']}", sound=sound)
    if event["type"] == "hazard":
        dmg = event.get("dmg_value", 10)
        player.hp = max(0, player.hp - dmg)
        type_text(f"You take {dmg} damage.", sound=sound)
        noise = event.get("noise_value", 0)
        if noise:
            player.noise_level = min(100, player.noise_level + noise)
            type_text(f"Noise level increased by {noise}!", sound=sound)
    elif event["type"] == "loot":
        item = event.get("loot_item", "Scrap Metal")
        qty  = event.get("loot_qty", 1)
        player.inventory[item] = player.inventory.get(item, 0) + qty
        type_text(f"You pick up {qty}x {item}.", sound=sound)
    elif event["type"] == "bonus":
        if "change_value" in event:
            player.change += event["change_value"]
            type_text(f"You find {event['change_value']} supplies!", sound=sound)
        if "hp_value" in event:
            player.hp = min(player.max_hp, player.hp + event["hp_value"])
            type_text(f"HP restored by {event['hp_value']}.", sound=sound)
    # neutral — message already printed, no stat change



def get_zombie_types():
    return [
        # Regular zombies (non-boss)
        Zombie("Lesser Zombie", 30, 8, 3, 15, 10, 0.1),
        Zombie("Zombie Scout", 25, 10, 2, 12, 8, 0.15),
        Zombie("Zombie General", 40, 12, 4, 20, 15, 0.2),
        Zombie("Infected Hound", 20, 12, 1, 10, 12, 0.25),
        Zombie("Mutated Corpse", 35, 14, 2, 17, 21, 0.35),

        # Boss zombies
        Zombie("Abomination", 120, 25, 10, 100, 75, 0.4, is_boss=True),
        Zombie("Necrotic Behemoth", 150, 30, 15, 150, 100, 0.5, is_boss=True),
        Zombie("Plague Carrier", 80, 18, 8, 80, 60, 0.6, is_boss=True),
        Zombie("Screamer", 60, 15, 5, 60, 50, 0.3, is_boss=True),
        Zombie("Festering Horror", 100, 22, 12, 120, 85, 0.45, is_boss=True),

        # NEW BOSS ZOMBIES
        Zombie("Hive Mind", 200, 35, 20, 200, 150, 0.7, is_boss=True),
        Zombie("Corpse Collector", 180, 40, 18, 180, 130, 0.5, is_boss=True),
        Zombie("Rotting Titan", 250, 45, 25, 250, 200, 0.6, is_boss=True),
        Zombie("Viral Prophet", 120, 30, 15, 150, 120, 0.8, is_boss=True),
        Zombie("Flesh Amalgam", 300, 50, 30, 300, 250, 0.4, is_boss=True)
    ]

def get_animal_types():
    return [
        Animal("Rabid Dog", 15, 6, 1, 8, 8, "Bite has infection chance"),
        Animal("Feral Cat", 10, 5, 0, 5, 6, "Quick and agile"),
        Animal("Wild Boar", 25, 8, 3, 12, 12, "Charges for extra damage"),
        Animal("Scavenger Bird", 8, 4, 0, 3, 5, "Can steal items"),
        Animal("Mutated Rat", 12, 5, 1, 6, 7, "Carries diseases"),
        Animal("Hunting Wolf", 20, 7, 2, 10, 10, "Hunts in packs"),
        Animal("Territorial Bear", 40, 12, 5, 20, 20, "Very powerful"),
        Animal("Cunning Fox", 14, 6, 1, 7, 8, "Tricky to hit")
    ]

def get_insect_types():
    return [
        Insect("Giant Mosquito", 5, 3, 0, 2, 4, "Drains blood"),
        Insect("Swarm of Flies", 8, 4, 0, 3, 5, "Causes confusion"),
        Insect("Radioactive Cockroach", 10, 5, 1, 4, 6, "Radiation damage"),
        Insect("Poisonous Spider", 7, 4, 0, 3, 5, "Venomous bite"),
        Insect("Hive Beetle", 12, 6, 1, 5, 7, "Calls reinforcements"),
        Insect("Stinging Wasp", 6, 4, 0, 3, 5, "Painful sting"),
        Insect("Carrion Beetle", 9, 5, 1, 4, 6, "Feeds on corpses"),
        Insect("Parasitic Tick", 4, 3, 0, 2, 4, "Latches on for damage over time")
    ]

def show_horde_warning(sound=True):
    for line in [
        "__________________________________________________!",
        "________________________!",
        "______________!",
        "________!",
        "____!",
        "__!",
        "!",
    ]:
        type_text(line, sound=sound)
    type_text("HORDE INCOMING!", sound=sound)
    audio_manager.play_horde()
    type_text("GET READY TO ESCAPE!", sound=sound)
    # Use the working generic sound instead
    audio_manager.play_zombie_sound("generic", "groan")  # Changed from "horde", "warning"

def horde_escape_sequence(sound=True):
    """
    Horde escape mini-game.
    A random short sequence of keys is shown. The player types them as a
    single string (e.g. "WWSSADAD") and presses Enter. No raw key polling
    — zero risk of terminal freeze.
    """
    type_text("The horde is closing in! Type the escape sequence and press ENTER!", sound=sound)

    # Simple single-character sequences only — arrow/mixed combos removed to
    # guarantee input works reliably on every terminal.
    sequence_types = [
        {"name": "WASD Combo",   "pool": list("WASD")},
        {"name": "Number Combo", "pool": list("12345678")},
        {"name": "Alpha Combo",  "pool": list("QWERTY")},
    ]
    seq_type = random.choice(sequence_types)
    length   = random.randint(4, 6)          # 4-6 keys — fair and fast
    sequence = [random.choice(seq_type["pool"]) for _ in range(length)]
    target   = "".join(sequence)

    type_text(f"Escape sequence ({seq_type['name']}): {' - '.join(sequence)}", sound=sound)
    type_text(f"Type exactly: {target}  (then press ENTER)", sound=sound)

    try:
        _clear_rshift()
        answer = input("> ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        type_text("Escape interrupted!", sound=sound)
        audio_manager.stop()
        return False

    if answer == target:
        type_text("You successfully escaped the horde!", sound=sound)
        audio_manager.play_confirmation(True)
        audio_manager.stop()
        return True
    else:
        type_text(f"Wrong sequence! ({answer} vs {target}) The horde overwhelms you!", sound=sound)
        audio_manager.play_confirmation(False)
        audio_manager.stop()
        return False


def attempt_parry(player, sound=True):
    """
    Parry prompt — player types SPACE (or just presses ENTER) to parry.
    Text-input based: no raw polling, no terminal freeze.
    """
    type_text("\n*** PARRY CHANCE! Type SPACE and press ENTER to parry! ***", sound=sound)
    try:
        pressed = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        pressed = ""

    triggered = (pressed == "" or pressed.upper() in ("SPACE", " ", "P"))

    if not triggered:
        type_text("Parry failed! (wrong input)", sound=sound)
        audio_manager.play_confirmation(False)
        return False

    # Resolve parry chance
    if player.parry_boost_active and player.parry_boost_uses > 0:
        parry_chance = random.uniform(0.7, 1.0)
        player.parry_boost_uses -= 1
        if player.parry_boost_uses <= 0:
            player.parry_boost_active = False
            type_text("Your Rabbit's Pendant has been used up!", sound=sound)
    else:
        parry_chance = player.parry_chance

    if random.random() < parry_chance:
        type_text("Successful parry!", sound=sound)
        audio_manager.play_confirmation(True)
        return True
    else:
        type_text("Parry failed!", sound=sound)
        audio_manager.play_confirmation(False)
        return False


def attempt_escape(sound=True):
    """
    Escape prompt — player types ESC (or E) and presses ENTER to flee.
    Text-input based: no raw polling, no terminal freeze.
    """
    type_text("\n*** ESCAPE! Type E and press ENTER to flee! ***", sound=sound)
    try:
        pressed = input("> ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        pressed = ""

    if pressed in ("E", "ESC", "ESCAPE", ""):
        type_text("Escape successful!", sound=sound)
        audio_manager.play_confirmation(True)
        return True
    else:
        type_text("Escape failed!", sound=sound)
        audio_manager.play_confirmation(False)
        return False


def handle_boss_rewards(player, zombie, sound=True):
    if zombie.reward_type == 'resources':
        # Resource-rich boss
        bonus_resources = random.randint(20, 40)
        player.change += bonus_resources
        type_text(f"The boss was carrying extra supplies! +{bonus_resources} resources", sound=sound)

        # Guaranteed equipment drop from boss
        equipment = ["Reinforced Vest", "Sharpened Weapon", "Reinforced Armor", "Silent Boots", "Sturdy Backpack"]
        dropped_equipment = random.choice(equipment)
        player.inventory[dropped_equipment] = player.inventory.get(dropped_equipment, 0) + 1
        type_text(f"The boss dropped: {dropped_equipment}!", sound=sound)
        # Play item drop sound
        audio_manager.play_item_sound(dropped_equipment)

    else:  # XP reward type
        # XP-rich boss
        bonus_xp = zombie.exp_reward * 2  # Double XP reward
        player.gain_exp(bonus_xp)
        type_text(f"Defeating this boss taught you valuable combat experience! +{bonus_xp} XP", sound=sound)

        # Chance to learn a new skill from XP-rich bosses
        if random.random() < 0.4 and player.skill_points < 3:  # 40% chance, max 3 skill points
            player.skill_points += 1
            type_text(f"You gained insight from the battle! +1 Skill Point", sound=sound)

def simple_battle(player, enemy, sound=True):
    """Simplified battle for animals and insects"""
    type_text(f"\nA {enemy.name} attacks!", sound=sound)

    while player.hp > 0 and enemy.hp > 0:
        # Player's turn
        damage = max(1, player.attack - getattr(enemy, 'defense', 0) // 2)
        enemy.hp -= damage
        type_text(f"{player.name} attacks the {enemy.name} for {damage} damage!", sound=sound)

        if enemy.hp <= 0:
            player.change += enemy.change_reward
            player.gain_exp(enemy.exp_reward)
            type_text(f"You defeated the {enemy.name}!", sound=sound)
            type_text(f"Found {enemy.change_reward} supplies!", sound=sound)
            return True

        # Enemy's turn
        enemy_damage = max(1, enemy.attack - player.defense // 2)
        player.hp -= enemy_damage
        type_text(f"The {enemy.name} attacks for {enemy_damage} damage!", sound=sound)

        if player.hp <= 0:
            type_text(f"You were defeated by the {enemy.name}!", sound=sound)
            return False

    return True

def battle(player, zombie, sound=True):
    type_text(f"\nA {zombie.name} shambles toward you!", sound=sound)
    # Play zombie sound
    if zombie.is_boss:
        audio_manager.play_zombie_sound("boss", "roar")
    else:
        audio_manager.play_zombie_sound("generic", "groan")

    # play battle / boss music if available
    try:
        if audio_manager and isinstance(audio_manager, AudioManager):
            if zombie.is_boss:
                audio_manager.play_boss()
            else:
                audio_manager.play_battle()
    except Exception as e:
        print(f"Audio error in battle: {e}")

    while player.hp > 0 and zombie.hp > 0:
        if not player.process_infection():
            return False

        if zombie.on_fire:
            fire_damage = max(3, player.magic // 2)
            zombie.hp -= fire_damage
            zombie.fire_turns -= 1
            type_text(f"The {zombie.name} takes {fire_damage} damage from being on fire!", sound=sound)
            if zombie.fire_turns <= 0:
                zombie.on_fire = False

        type_text("\n" + "="*50, sound=sound)
        player.display_stats(sound=sound)
        zombie.display_stats(sound=sound)
        type_text("="*50, sound=sound)

        type_text(f"\nChoose your action:", sound=sound)
        type_text("1. Attack", sound=sound)
        type_text("2. Skill", sound=sound)
        type_text("3. Item", sound=sound)
        type_text("4. Attempt to Flee", sound=sound)

        _clear_rshift()
        choice = input(f"\nEnter your choice: ")

        # Player's turn
        if choice == "1":
            damage = max(1, player.attack - zombie.defense // 2)
            zombie.hp -= damage
            type_text(f"{player.name} attacks the {zombie.name} for {damage} damage!", sound=sound)
            player.noise_level += 10  # Add noise when attacking

        elif choice == "2":
            if not player.spells:
                type_text(f"You don't know any skills!", sound=sound)
                continue

            type_text(f"\nChoose a skill:", sound=sound)
            for i, spell in enumerate(player.spells, 1):
                type_text(f"{i}. {spell}", sound=sound)

            try:
                spell_choice = int(input(f"\nEnter your choice: ")) - 1
                if 0 <= spell_choice < len(player.spells):
                    spell = player.spells[spell_choice]

                    spell_effects = {
                        "First Aid": {"mp": 5, "effect": lambda: f"{player.name} performs First Aid and recovers {player.magic + 10} HP!", "action": lambda: setattr(player, 'hp', min(player.max_hp, player.hp + player.magic + 10)), "noise": 0},
                        "Molotov": {"mp": 8, "effect": lambda: f"{player.name} throws a Molotov at the {zombie.name} for {max(5, player.magic * 2 - zombie.defense // 4)} damage and sets it on fire!", "action": lambda: [setattr(zombie, 'hp', zombie.hp - max(5, player.magic * 2 - zombie.defense // 4)), setattr(zombie, 'on_fire', True), setattr(zombie, 'fire_turns', 3)], "noise": 20},
                        "Trap Setup": {"mp": 6, "effect": lambda: f"{player.name} sets up a trap! Next attack will be more effective!", "action": lambda: setattr(player, 'attack', player.attack * 2), "noise": 5},
                        "Heal Wounds": {"mp": 10, "effect": lambda: f"{player.name} tends to their wounds and recovers {player.magic * 2} HP!", "action": lambda: setattr(player, 'hp', min(player.max_hp, player.hp + player.magic * 2)), "noise": 0},
                        "Antidote": {"mp": 7, "effect": lambda: f"{player.name} uses medical knowledge to prevent infection!", "action": lambda: None, "noise": 0},
                        "Revitalize": {"mp": 12, "effect": lambda: f"{player.name} revitalizes themselves, recovering HP and MP!", "action": lambda: [setattr(player, 'hp', min(player.max_hp, player.hp + 30)), setattr(player, 'mp', min(player.max_mp, player.mp + 15))], "noise": 0},
                        "Bash": {"mp": 8, "effect": lambda: f"{player.name} bashes the {zombie.name} for {max(3, player.attack * 2 - zombie.defense)} damage!", "action": lambda: setattr(zombie, 'hp', zombie.hp - max(3, player.attack * 2 - zombie.defense)), "noise": 15},
                        "Silent Takedown": {"mp": 10, "effect": lambda: f"{player.name} performs a silent takedown on the {zombie.name} for {max(8, player.attack + player.magic - zombie.defense // 2)} damage!", "action": lambda: setattr(zombie, 'hp', zombie.hp - max(8, player.attack + player.magic - zombie.defense // 2)), "noise": -10},
                        "Group Heal": {"mp": 15, "effect": lambda: f"{player.name} uses advanced medical knowledge to recover {player.magic * 3} HP!", "action": lambda: setattr(player, 'hp', min(player.max_hp, player.hp + player.magic * 3)), "noise": 0},
                        # Infected class skills
                        "Viral Burst": {"mp": 10, "effect": lambda: f"{player.name} releases a viral burst for {max(10, player.magic * 3 - zombie.defense)} damage!", "action": lambda: setattr(zombie, 'hp', zombie.hp - max(10, player.magic * 3 - zombie.defense)), "noise": 5},
                        "Consume": {"mp": 15, "effect": lambda: f"{player.name} consumes part of the {zombie.name} and recovers {player.attack} HP!", "action": lambda: setattr(player, 'hp', min(player.max_hp, player.hp + player.attack)), "noise": 10},
                        "Mutate": {"mp": 20, "effect": lambda: f"{player.name} triggers a controlled mutation, temporarily increasing stats!", "action": lambda: [setattr(player, 'attack', player.attack + 5), setattr(player, 'defense', player.defense + 3)], "noise": 15},
                        "Viral Surge": {"mp": 25, "effect": lambda: f"{player.name} unleashes a viral surge for massive damage!", "action": lambda: setattr(zombie, 'hp', zombie.hp - max(20, player.magic * 5 - zombie.defense)), "noise": 20}
                    }

                    if spell in spell_effects:
                        effect = spell_effects[spell]
                        if player.mp >= effect["mp"]:
                            player.mp -= effect["mp"]
                            effect["action"]()
                            type_text(effect["effect"](), sound=sound)

                            # Apply noise effect from the skill
                            player.noise_level = max(0, player.noise_level + effect["noise"])
                            if effect["noise"] > 0:
                                type_text(f"The skill made noise! (+{effect['noise']} noise level)", sound=sound)
                            elif effect["noise"] < 0:
                                type_text(f"The skill was quiet! ({effect['noise']} noise level)", sound=sound)
                        else:
                            type_text(f"Not enough MP!", sound=sound)
                            continue
                    else:
                        type_text(f"Skill not implemented!", sound=sound)
                        continue
                else:
                    type_text(f"Invalid choice!", sound=sound)
                    continue
            except ValueError:
                type_text(f"Invalid input!", sound=sound)
                continue

        elif choice == "3":
            # Include Molotov Cocktail in usable items during battle
            usable_items = [item for item in player.inventory if item in ["Purified Water", "Bandage", "Antidote", "Medkit", "Advanced Medkit", "Rabbit's Pendant", "Purified Herbs", "Molotov Cocktail"] and player.inventory[item] > 0]

            if not usable_items:
                type_text(f"You don't have any usable items!", sound=sound)
                continue

            type_text(f"\nChoose an item:", sound=sound)
            for i, item in enumerate(usable_items, 1):
                type_text(f"{i}. {item} x{player.inventory[item]}", sound=sound)
            type_text(f"{len(usable_items)+1}. Back", sound=sound)

            try:
                item_choice = int(input(f"\nEnter your choice: "))
                if item_choice == len(usable_items)+1:
                    continue
                elif 1 <= item_choice <= len(usable_items):
                    item = usable_items[item_choice-1]
                    if item == "Molotov Cocktail":
                        # Handle Molotov Cocktail use in battle
                        damage = max(10, player.magic * 3 - zombie.defense // 2)
                        zombie.hp -= damage
                        zombie.on_fire = True
                        zombie.fire_turns = 3
                        player.inventory[item] -= 1
                        type_text(f"{player.name} throws a Molotov Cocktail at the {zombie.name} for {damage} damage and sets it on fire!", sound=sound)
                        player.noise_level += 25
                        type_text(f"The loud explosion increases noise level!", sound=sound)
                        audio_manager.play_item_sound("Molotov Cocktail")
                    else:
                        if not player.use_item(item):
                            continue
                        # Some items make noise when used
                        if item in ["Molotov Cocktail", "Rabbit's Pendant"]:
                            player.noise_level += 10
                            type_text(f"Using {item} made noise!", sound=sound)
                else:
                    type_text(f"Invalid choice!", sound=sound)
                    continue
            except ValueError:
                type_text(f"Invalid input!", sound=sound)
                continue

        elif choice == "4":
            if attempt_escape():
                # Escaping makes noise
                player.noise_level += 15
                return True
            else:
                type_text(f"You couldn't escape!", sound=sound)
                # Failed escape still makes some noise
                player.noise_level += 5

        else:
            type_text(f"Invalid choice!", sound=sound)
            continue

        # Check if zombie is defeated
        if zombie.hp <= 0:
            # stop battle music and resume day music if possible
            try:
                if audio_manager and isinstance(audio_manager, AudioManager):
                    # Check if we have day music, otherwise stop music
                    if audio_manager._music_tracks.get('day'):
                        audio_manager.play_day()
                    else:
                        audio_manager.stop()
            except Exception as e:
                print(f"Audio error after battle: {e}")

            type_text(f"\nYou defeated the {zombie.name}!", sound=sound)
            player.change += zombie.change_reward
            type_text(f"Found {zombie.change_reward} supplies!", sound=sound)
            player.gain_exp(zombie.exp_reward)

            # FIXED: Show rewards for crafting materials after battle
            if random.random() < 0.6:  # 60% chance to find crafting materials
                materials = ["Scrap Metal", "Cloth", "Herbs", "Electronic Parts", "Mechanical Parts"]
                weights = [0.3, 0.3, 0.2, 0.1, 0.1]

                # Determine how many materials to award
                num_materials = random.randint(1, 3)
                type_text(f"\nYou search the body and find:", sound=sound)

                for _ in range(num_materials):
                    material = random.choices(materials, weights=weights, k=1)[0]
                    quantity = random.randint(1, 3)
                    player.inventory[material] = player.inventory.get(material, 0) + quantity
                    type_text(f"- {quantity} {material}", sound=sound)
                    audio_manager.play_item_sound(material)

            # Equipment drop chance
            if random.random() < 0.15:  # 15% chance for equipment
                equipment = ["Reinforced Vest", "Sharpened Weapon", "Silent Boots"]
                found_equipment = random.choice(equipment)
                player.inventory[found_equipment] = player.inventory.get(found_equipment, 0) + 1
                type_text(f"You found a {found_equipment}!", sound=sound)
                audio_manager.play_item_sound(found_equipment)

            return True

        # Zombie's turn
        if random.random() < 0.2:
            type_text(f"\nThe {zombie.name} grabs you in a grapple!", sound=sound)
            audio_manager.play_zombie_sound("generic", "grapple")
            zombie.grappling = True
            grapple_turns = 0

            while zombie.grappling and grapple_turns < 3 and player.hp > 0:
                grapple_turns += 1
                type_text(f"The zombie tries to bite you! Press SPACE to parry!", sound=sound)

                if attempt_parry(player):
                    type_text(f"You break free from the grapple!", sound=sound)
                    zombie.grappling = False
                    if random.random() < 0.5:
                        damage = max(1, player.attack // 2)
                        zombie.hp -= damage
                        type_text(f"{player.name} counter attacks for {damage} damage!", sound=sound)
                    break
                else:
                    zombie_damage = max(2, zombie.attack - player.defense // 3)
                    player.hp -= zombie_damage
                    type_text(f"The {zombie.name} bites you for {zombie_damage} damage!", sound=sound)
                    audio_manager.play_item_sound("zombie_bite")

                    if random.random() < zombie.infection_chance and not player.infected:
                        player.infected = True
                        player.infection_timer = 3
                        type_text(f"The zombie's bite has infected you! Find an Antidote soon!", sound=sound)

                    if random.random() < 0.1 and player.hp <= player.max_hp // 4:
                        type_text(f"The zombie delivers a fatal bite!", sound=sound)
                        return False

            if zombie.grappling and player.hp > 0:
                type_text(f"You manage to break free from the grapple!", sound=sound)
                zombie.grappling = False
        else:
            if random.random() < 0.3:
                type_text(f"\nThe {zombie.name} telegraphes its attack!", sound=sound)
                if attempt_parry(player):
                    type_text(f"{player.name} parried the attack successfully!", sound=sound)
                    if random.random() < 0.5:
                        damage = max(1, player.attack // 2)
                        zombie.hp -= damage
                        type_text(f"{player.name} counter attacks for {damage} damage!", sound=sound)
                else:
                    zombie_damage = max(1, zombie.attack - player.defense // 2)
                    player.hp -= zombie_damage
                    type_text(f"Parry failed! The {zombie.name} attacks {player.name} for {zombie_damage} damage!", sound=sound)

                    if random.random() < zombie.infection_chance and not player.infected:
                        player.infected = True
                        player.infection_timer = 3
                        type_text(f"The zombie's attack has infected you! Find an Antidote soon!", sound=sound)
            else:
                zombie_damage = max(1, zombie.attack - player.defense // 2)
                player.hp -= zombie_damage
                type_text(f"\nThe {zombie.name} attacks {player.name} for {zombie_damage} damage!", sound=sound)

                if random.random() < zombie.infection_chance and not player.infected:
                    player.infected = True
                    player.infection_timer = 3
                    type_text(f"The zombie's attack has infected you! Find an Antidote soon!", sound=sound)

        if player.hp <= 0:
            type_text(f"\n{player.name} has been overwhelmed...", sound=sound)
            return False

    return True

def horde_encounter(player, sound=True):
    """
    Triggered when noise attracts a horde. Uses the same safe text-input
    escape system — no raw polling, no terminal freeze.
    """
    type_text("A horde is drawn by your noise! Type the escape code and press ENTER!", sound=sound)

    pool     = list("WASD1234")
    length   = random.randint(3, 5)
    sequence = [random.choice(pool) for _ in range(length)]
    target   = "".join(sequence)

    type_text(f"Escape: {' '.join(sequence)}  →  type: {target}  (ENTER)", sound=sound)

    try:
        _clear_rshift()
        answer = input("> ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        player.hp -= 10
        type_text("You froze! The horde hit you for 10 damage.", sound=sound)
        return player.hp > 0

    if answer == target:
        type_text("You slipped away from the horde!", sound=sound)
        audio_manager.play_confirmation(True)
        audio_manager.stop()
        return True
    else:
        damage = random.randint(15, 30)
        player.hp -= damage
        type_text(f"Wrong! The horde catches you — {damage} damage!", sound=sound)
        audio_manager.play_confirmation(False)
        audio_manager.stop()
        return player.hp > 0


def random_encounter(player, sound=True, day=1):
    """Random encounter during scavenging or resting"""
    # Base chance for random encounter: 15%
    encounter_chance = 0.15

    # Increase chance based on noise level
    encounter_chance += (player.noise_level / 100) * 0.3  # Up to 30% additional chance

    if random.random() < encounter_chance:
        # Determine encounter type
        encounter_type = random.choices(
            ["zombie", "animal", "insect", "special"],
            weights=[0.5, 0.3, 0.15, 0.05],
            k=1
        )[0]

        if encounter_type == "zombie":
            danger = min(3.0, 1.0 + (day - 1) * 0.08)
            zombies = get_daily_zombies(day, danger)
            # Weight toward easier zombies for random encounters
            zombie = random.choices(zombies[:5], weights=[0.3, 0.25, 0.2, 0.15, 0.1], k=1)[0]
            type_text(f"\nA {zombie.name} appears from the shadows!", sound=sound)
            return battle(player, zombie, sound=sound)

        elif encounter_type == "animal":
            animals = get_animal_types()
            animal = random.choice(animals)
            type_text(f"\nA {animal.name} attacks!", sound=sound)
            return simple_battle(player, animal, sound=sound)

        elif encounter_type == "insect":
            insects = get_insect_types()
            insect = random.choice(insects)
            type_text(f"\nA {insect.name} attacks!", sound=sound)
            return simple_battle(player, insect, sound=sound)

        elif encounter_type == "special":
            # Special encounter: could be helpful or harmful
            special_events = [
                {"type": "helpful", "message": "You find an abandoned stash of supplies!", "effect": lambda: player.change + random.randint(20, 40)},
                {"type": "harmful", "message": "You stumble into a trap!", "effect": lambda: player.hp - random.randint(10, 20)},
                {"type": "neutral", "message": "You discover an interesting landmark.", "effect": lambda: None},
                {"type": "helpful", "message": "You find a working first aid kit!", "effect": lambda: player.hp + random.randint(15, 30)},
                {"type": "harmful", "message": "You encounter a toxic cloud!", "effect": lambda: [setattr(player, 'hp', player.hp - 15), setattr(player, 'infected', True) if not player.infected else None]}
            ]

            event = random.choice(special_events)
            type_text(f"\n{event['message']}", sound=sound)

            if event["type"] == "helpful":
                if "change" in str(event["effect"]):
                    bonus = random.randint(20, 40)
                    player.change += bonus
                    type_text(f"Found {bonus} supplies!", sound=sound)
                    audio_manager.play_confirmation(True)
                elif "hp" in str(event["effect"]):
                    heal = random.randint(15, 30)
                    player.hp = min(player.max_hp, player.hp + heal)
                    type_text(f"Recovered {heal} HP!", sound=sound)
                    audio_manager.play_confirmation(True)
            elif event["type"] == "harmful":
                if "trap" in event["message"]:
                    damage = random.randint(10, 20)
                    player.hp -= damage
                    type_text(f"Took {damage} damage from the trap!", sound=sound)
                    audio_manager.play_confirmation(False)
                elif "toxic" in event["message"]:
                    player.hp -= 15
                    type_text(f"Took 15 damage from the toxic cloud!", sound=sound)
                    audio_manager.play_confirmation(False)
                    if not player.infected and not player.is_infected_class:
                        player.infected = True
                        player.infection_timer = 3
                        type_text(f"You've been infected by the toxic cloud!", sound=sound)

            return player.hp > 0

    return True

def scavenge_location(player, time_remaining, is_night=False, sound=True, day=1):
    type_text(f"\n{player.get_dialogue(is_night)}", sound=sound)
    # Play dialog sound
    audio_manager.play_dialog("player", player.job_class.lower())

    time_spent = random.randint(30, 120)

    if time_spent > time_remaining:
        time_spent = time_remaining
        type_text(f"You need to return to safety before nightfall!", sound=sound)

    # Calculate boss chance based on noise level
    boss_chance = SoundManager.calculate_boss_chance(player.noise_level)

    # Increased horde chance with visual representation
    horde_chance = 0.35 + (0.15 if is_night else 0)  # 35% base chance, 50% at night
    if random.random() < horde_chance:
        show_horde_warning(sound=sound)
        if not horde_escape_sequence(sound=sound):
            # Player failed to escape the horde
            damage_taken = random.randint(20, 40)
            player.hp -= damage_taken
            type_text(f"The horde overwhelms you! You take {damage_taken} damage!", sound=sound)

            if player.hp <= 0:
                type_text(f"You've been overrun by the horde...", sound=sound)
                return time_spent, False
            else:
                type_text(f"You barely escape with your life!", sound=sound)
                return time_spent, True

    # Check for noise attracting zombies - higher noise increases chance
    attraction_chance = (player.noise_level / 100) * 0.8  # Up to 80% chance at max noise
    if player.noise_level > 0 and random.random() < attraction_chance:
        type_text(f"Your noise has attracted attention!", sound=sound)
        if not horde_encounter(player, sound=sound):
            return time_spent, False

    # Random encounter chance
    if not random_encounter(player, sound=sound, day=day):
        return time_spent, False

    # Reduce noise level gradually instead of resetting
    player.noise_level = max(0, player.noise_level - 20)

    # Procedural environmental encounter
    if random.random() < 0.45:
        proc_enc = generate_encounter(day, index=random.randint(0, 99))
        apply_encounter(player, proc_enc, sound=sound)
        if player.hp <= 0:
            return time_spent, False

    encounter_chance = 0.3 + (time_spent / 300)
    if random.random() < encounter_chance:
        danger = min(3.0, 1.0 + (day - 1) * 0.08)
        zombies = get_daily_zombies(day, danger)

        # Determine if we get a boss based on noise level
        is_boss_encounter = random.random() < boss_chance

        if is_boss_encounter:
            # Filter for boss zombies only
            boss_zombies = [z for z in zombies if z.is_boss]
            if boss_zombies:
                zombie = random.choice(boss_zombies)
                type_text(f"A terrifying {zombie.name} appears! Your noise attracted a boss!", sound=sound)
                # immediate boss audio cue
                try:
                    if audio_manager and isinstance(audio_manager, AudioManager):
                        audio_manager.play_boss()
                except Exception as e:
                    print(f"Audio error playing boss: {e}")
            else:
                # Fallback to regular zombie if no bosses available
                zombie = random.choice(zombies[:5])
        else:
            # Regular encounter - weight the chance for regular vs boss zombies
            if random.random() < 0.8:  # 80% chance for regular zombies
                zombie = random.choice(zombies[:5])  # First 5 are regular zombies
            else:  # 20% chance for boss zombies (natural spawn)
                boss_zombies = [z for z in zombies if z.is_boss]
                if boss_zombies:
                    zombie = random.choice(boss_zombies)
                    type_text(f"A terrifying {zombie.name} appears! This is a boss encounter!", sound=sound)
                    try:
                        if audio_manager and isinstance(audio_manager, AudioManager):
                            audio_manager.play_boss()
                    except Exception as e:
                        print(f"Audio error playing boss: {e}")
                else:
                    zombie = random.choice(zombies[:5])

        battle_result = battle(player, zombie, sound=sound)
        if not battle_result:
            return time_spent, False

        # After battle, if it was a boss, handle special rewards
        if zombie.is_boss and zombie.hp <= 0:
            handle_boss_rewards(player, zombie, sound=sound)
    else:
        found_supplies = random.randint(5, 20)
        player.change += found_supplies
        type_text(f"You found {found_supplies} supplies!", sound=sound)
        audio_manager.play_confirmation(True)

        # FIXED: Always show crafting materials when scavenging successfully
        materials = ["Scrap Metal", "Cloth", "Herbs", "Electronic Parts", "Mechanical Parts"]
        weights = [0.35, 0.35, 0.2, 0.05, 0.05]

        found_materials = []
        # Always find at least one material
        num_materials = random.randint(1, 3)
        for _ in range(num_materials):
            material = random.choices(materials, weights=weights, k=1)[0]
            quantity = random.randint(1, 3)
            player.inventory[material] = player.inventory.get(material, 0) + quantity
            found_materials.append(f"{quantity} {material}")
            # Play material found sound
            audio_manager.play_item_sound(material)

        if found_materials:
            type_text(f"You also found:", sound=sound)
            for material_found in found_materials:
                type_text(f"- {material_found}", sound=sound)

        # Chance to find equipment
        if random.random() < 0.1:
            equipment = ["Reinforced Vest", "Sharpened Weapon", "Silent Boots"]
            found_equipment = random.choice(equipment)
            player.inventory[found_equipment] = player.inventory.get(found_equipment, 0) + 1
            type_text(f"You found a {found_equipment}!", sound=sound)
            # Play equipment found sound
            audio_manager.play_item_sound(found_equipment)

        # Chance to find lore documents
        if random.random() < 0.15:
            lore_documents = [
                {
                    "title": "Research Note #42",
                    "content": "The infection seems to spread through bodily fluids. Those bitten turn within hours. Strangely, some subjects show immunity to the transformation, becoming carriers instead."
                },
                {
                    "title": "Emergency Broadcast Transcript",
                    "content": "...repeating this emergency broadcast. Avoid population centers. The infected are attracted to noise. If you must travel, do so quietly and only during daylight hours. Safe zones have been established at..."
                },
                {
                    "title": "Diary Entry - Day 17",
                    "content": "We thought we were safe in the bunker, but Jenkins came back from the supply run with a bite on his arm. He hid it from us. Now half our group is gone. The other half... changed."
                },
                {
                    "title": "Scientific Journal Page",
                    "content": "The virus appears to reanimate neural tissue while shutting down higher brain functions. Subjects retain basic motor functions and predatory instincts; more study is required to understand the triggers for aggressive behavior."
                }
            ]
            doc = random.choice(lore_documents)
            player.found_lore.append(doc)
            type_text(f"You found a lore document: {doc['title']}", sound=sound)
            audio_manager.play_item_sound("document")

    return time_spent, True

# ------------------ EXPANDED NPC DIALOGUES ------------------
def talk_to_npcs(player, settlement_type, sound=True):
    npc_dialogues = {
        "refugee_camp": [
            "Old Man: 'I've seen things... things that would make your blood run cold. The night is not your friend.'",
            "Scavenger: 'Keep your eyes open and your ears sharp. They're always listening.'",
            "Mother: 'My children... I haven't seen them since the evacuation. Have you seen any little ones out there?'",
            "Guard: 'We're safe here for now, but supplies are running low. We need more people willing to venture out.'",
            "Young Scout: 'I saw something strange in the woods yesterday... glowing eyes in the dark.'",
            "Cook: 'Food's running low. We're down to canned goods and whatever we can forage.'",
            "Mechanic: 'If you find any working vehicles, let me know. We could use the parts.'",
            "Teacher: 'I try to keep the children occupied with lessons. Helps them forget the horrors outside.'",
            "Doctor: 'Medical supplies are critical. Antibiotics, bandages, anything sterile.'",
            "Engineer: 'The perimeter fence needs constant maintenance. The infected test it every night.'",
            "Hunter: 'Game is getting scarce. The infected have driven most animals away or... changed them.'",
            "Farmer: 'We're trying to grow what we can, but the soil feels... wrong somehow.'"
        ],
        "abandoned_town": [
            "Shopkeeper: 'Business is slow these days. Not many customers left, if you catch my meaning.'",
            "Hunter: 'The infected avoid certain areas. I've noticed they don't like running water.'",
            "Elder: 'This town has stood for generations. We won't let some infection drive us out now.'",
            "Youth: 'I've been practicing with my knife. One day I'll be strong enough to protect everyone.'",
            "Bartender: 'Last call was years ago, but I still keep the place clean. Habit, I guess.'",
            "Librarian: 'Knowledge is our greatest weapon now. I've been compiling everything we know about the infection.'",
            "Mayor: 'We've lost so many... but those of us left are determined to survive.'",
            "Blacksmith: 'I can fix almost anything metal. Bring me tools and I'll make you weapons.'",
            "School Teacher: 'The schoolhouse is our main shelter now. The children sleep in the classrooms.'",
            "Postman: 'I still make my rounds, checking empty houses for supplies. Old habits die hard.'",
            "Cemetery Keeper: 'The graves... some of them have been disturbed. Not by scavengers.'",
            "Church Organist: 'I play sometimes, when it's safe. The music seems to calm people.'"
        ],
        "military_outpost": [
            "Soldier: 'We're holding the line, but we can't do it forever. We need more supplies and manpower.'",
            "Medic: 'The infection works fast. If you get bitten, you have about an hour before... changes happen.'",
            "Engineer: 'I'm working on a barrier that could keep them out for good. Just need more parts.'",
            "Commander: 'We've lost contact with command. We're on our own out here.'",
            "Sniper: 'From the watchtower, I can see them moving in the distance. More every day.'",
            "Quartermaster: 'Inventory is critical. We track every bullet, every bandage.'",
            "Radio Operator: 'Static... nothing but static for weeks now. Sometimes I think I hear voices.'",
            "Drill Sergeant: 'Discipline keeps us alive. Panic gets you killed.'",
            "Field Scientist: 'We've been studying the infected. Their behavior patterns are... concerning.'",
            "Armorer: 'Maintenance is key. A jammed weapon is a death sentence out there.'",
            "Helicopter Pilot: 'Bird's grounded. No fuel, and the engine needs parts we don't have.'",
            "Military Police: 'We maintain order here. Can't have people losing their heads.'"
        ],
        "barricaded_city": [
            "Scavenger: 'The city center is overrun. Don't go there unless you've got a death wish.'",
            "Survivor: 'They're more active at night. I've seen them... organizing.'",
            "Mechanic: 'I can fix anything, but parts are hard to come by these days.'",
            "Leader: 'We've built a community here. We look out for each other. You could stay, if you pull your weight.'",
            "Rooftop Lookout: 'From up here, you can see the fires burning in the distance. Never stops.'",
            "Sewer Dweller: 'The tunnels are relatively safe. Dark, wet, but the infected rarely go down there.'",
            "Hospital Worker: 'The medical center was overrun in the first week. We saved what supplies we could.'",
            "Firefighter: 'We still try to put out fires when we can. Prevents the whole city from burning.'",
            "Store Owner: 'My shop's empty now. Took me thirty years to build that business.'",
            "Musician: 'I play on safe nights. Helps people remember there's still beauty in the world.'",
            "Journalist: 'I keep a record of everything. Someone needs to remember what happened here.'",
            "City Planner: 'The barricades follow old evacuation routes. We reinforced what was already there.'"
        ],
        "roadside_junkyard": [
            "Scarred Scrapper: 'You can call me Night Rogue. There is nothing better than a stranger who keeps to themselves.'",
            "Trader: 'Up to no good? I can tell you something interesting. If you want better kicks, some parts might do your feet some good.'",
            "Workshop: 'Going around place to place, gets a man thinking, what's the world coming to?'",
            "Alchemist: 'I can mix a battery and a filter into something useful in a pinch.'",
            "Junkyard Dog Handler: 'The dogs keep watch. Better than any alarm system.'",
            "Car Crusher Operator: 'Used to crush cars for scrap. Now I crush anything that shouldn't be moving.'",
            "Tire Salesman: 'Good tires are worth their weight in gold now. Mobility means survival.'",
            "Gas Station Attendant: 'The pumps are dry, but I still keep the place clean. Force of habit.'",
            "Bus Driver: 'My bus is my home now. Armored it up with scrap metal.'",
            "Roadside Diner Cook: 'The grill's cold, but I still make stew from whatever people bring in.'",
            "Highway Patrol: 'Used to give tickets. Now I just try to keep this stretch of road clear.'",
            "Trucker: 'Rig's out of diesel. Been living in the cab for months now.'"
        ],
    }

    dialogue = random.choice(npc_dialogues.get(settlement_type, ["They have nothing to say."]))
    type_text(f"\n{dialogue}", sound=sound)
    # Play matched NPC voiceover if available, else generic
    audio_manager.play_npc_voiceover(dialogue)

    # Sometimes NPCs give useful tips or small rewards
    if random.random() < 0.3:
        tips = [
            "I heard there's a stash of supplies in the abandoned building to the north.",
            "Be careful around the hospital. It's crawling with infected.",
            "They say someone found a working vehicle with a full tank of gas.",
            "If you're low on supplies, try checking cars. People often leave things behind.",
            "I once saw someone take down a horde with nothing but a molotov and some quick thinking.",
            "The infected avoid bright light. Flashlights can be more useful than weapons sometimes.",
            "Running water seems to confuse them. Rivers and streams are relatively safe.",
            "They're attracted to noise. The quieter you are, the longer you'll live.",
            "Check basements and attics. People hid supplies when things got bad.",
            "Full moons make them more aggressive. Stay inside if you can.",
            "Some animals seem immune to the infection. Their meat is safe to eat.",
            "Radioactive areas keep them away, but don't stay there too long yourself."
        ]
        tip = random.choice(tips)
        type_text(f"\n{tip}", sound=sound)

    if random.random() < 0.2:
        small_rewards = {
            "Bandage": 1,
            "Purified Water": 1,
            "Herbs": 2,
            "Scrap Metal": 3,
            "Cloth": 2
        }
        item, quantity = random.choice(list(small_rewards.items()))
        player.inventory[item] = player.inventory.get(item, 0) + quantity
        type_text(f"They give you {quantity} {item} as a token of appreciation!", sound=sound)
        # Play item received sound
        audio_manager.play_item_sound(item)

def visit_settlement(player, time_remaining, game_settings, end_time, settlement_type, sound=True, proc_settlement=None):
    settlements = {
        "refugee_camp": {
            "name": "Refugee Camp",
            "description": "You arrive at a makeshift camp surrounded by barricades. Survivors move about cautiously, trading scarce resources.",
            "trader_dialogue": "Trader: 'Supplies are limited, but I've got what you need. What'll it be?'",
            "workshop_dialogue": "Workshop: 'I can reinforce your gear for better protection.'",
            "sanctuary_dialogue": "Sanctuary: 'Rest here, it's safe. For a price.'",
            "alchemist_dialogue": "Alchemist: 'I can purify herbs for better healing properties.'"
        },
        "abandoned_town": {
            "name": "Abandoned Town",
            "description": "The remains of a small town stand silent. A few determined survivors have set up trading posts in the relatively intact buildings.",
            "trader_dialogue": "Scavenger: 'Found some good stuff in the ruins. Interested?'",
            "workshop_dialogue": "Mechanic: 'I can improve your gear with what I've salvaged.'",
            "sanctuary_dialogue": "Innkeeper: 'Safe rooms are scarce. Cost you supplies to stay.'",
            "alchemist_dialogue": "Herbalist: 'I know secrets of plant purification that can enhance their medicinal properties.'"
        },
        "military_outpost": {
            "name": "Military Outpost",
            "description": "A fortified position with watchtowers and sandbag emplacements. Soldiers trade military-grade supplies for useful resources.",
            "trader_dialogue": "Quartermaster: 'Standard issue gear available. What do you need?'",
            "workshop_dialogue": "Armorer: 'I can upgrade your equipment to military specs.'",
            "sanctuary_dialogue": "Officer: 'The barracks are secure. For a donation to our supplies.'",
            "alchemist_dialogue": "Medic: 'I've developed advanced purification techniques for medical supplies.'"
        },
        "barricaded_city": {
            "name": "Barricaded City",
            "description": "A city mostly engulfed in flames, and screams of terror. Some survivors stand watch over the tallest points of the barricades.",
            "trader_dialogue": "Goods!: 'Welcome to the city of the dead, need anything?'",
            "workshop_dialogue": "Gear?: 'I can upgrade your equipment, but we got to do this quick.'",
            "sanctuary_dialogue": "Safe House: 'A few leaks here and there but it beats taking dirt nap! Need to rest up?'",
            "alchemist_dialogue": "Chemist: 'My lab survived the outbreak. I can create potent medicinal compounds.'"
        },
        "roadside_junkyard": {
            "name": "Roadside Junkyard",
            "description": "Pillars of smoke above a few bon fires. Broken down cars and parts here and there and the smell of burnt rubber. The survivors look like they are scavenging for parts, some resting by the fires, others standing watching as lookouts.",
            "trader_dialogue": "Hey we don't like outsiders, but since you don't look like much of a threat, how can I assist you stranger?",
            "workshop_dialogue": "Fancy shoes there pal heh. What is it that you need?",
            "sanctuary_dialogue": "Hey don't mind if you kick up your feet, but any funny business your flesh for the horde, other than that get the rest you need.",
            "alchemist_dialogue": "Uh if only.... Hey where'd you come from. Is there something your looking for?"
        }
    }

    settlement = settlements.get(settlement_type, settlements["refugee_camp"])
    # Override with procedurally generated settlement data if provided
    if proc_settlement:
        settlement = dict(settlement)  # copy
        settlement["name"]               = proc_settlement["name"]
        settlement["description"]        = proc_settlement["description"]
        settlement["trader_dialogue"]    = proc_settlement["trader_dialogue"]
        settlement["workshop_dialogue"]  = proc_settlement["workshop_dialogue"]
        settlement["sanctuary_dialogue"] = proc_settlement["sanctuary_dialogue"]
        settlement["alchemist_dialogue"] = proc_settlement["alchemist_dialogue"]

    type_text(f"\n{settlement['description']}", sound=sound)

    # Play town-specific music when entering settlement
    try:
        if audio_manager and isinstance(audio_manager, AudioManager):
            audio_manager.play_town(settlement_type)
    except Exception as e:
        print(f"Audio error playing town music: {e}")

    if game_settings.get("auto_save", True):
        current_time = time.time()
        remaining_time = max(0, end_time - current_time)
        remaining_minutes = int(remaining_time / 60)
        save_game(player, days_survived, remaining_minutes, "autosave")
        type_text(f"Game automatically saved.", sound=sound)
        audio_manager.play_confirmation(True)

    time_spent = 0
    while time_spent < time_remaining:
        current_time = time.time()
        remaining_time = max(0, end_time - current_time)
        remaining_minutes = remaining_time / 60

        type_text(f"\nYour supplies: {player.change}", sound=sound)
        type_text(f"\nWhere would you like to go in {settlement['name']}?", sound=sound)
        type_text("1. Sanctuary (restore HP/MP)", sound=sound)
        type_text("2. Trading Post", sound=sound)
        type_text("3. Workshop", sound=sound)
        type_text("4. Crafting Area", sound=sound)
        type_text("5. Alchemy Lab", sound=sound)
        type_text("6. Talk to Locals", sound=sound)
        type_text("7. Equipment Management", sound=sound)
        type_text("8. Backpack (Use Items)", sound=sound)
        type_text("9. Save Game", sound=sound)
        type_text("10. Check Time", sound=sound)
        type_text("11. Leave settlement", sound=sound)

        _clear_rshift()
        choice = input(f"\nEnter your choice: ")

        if choice == "1":
            if remaining_minutes < 60:
                type_text(f"Not enough time before nightfall! You need at least 60 minutes to rest.", sound=sound)
                audio_manager.play_confirmation(False)
                continue

            if player.change >= 20:
                player.change -= 20
                player.hp = player.max_hp
                player.mp = player.max_mp

                # Sanctuary now has a chance to cure infection
                if player.infected and not player.is_infected_class:
                    cure_chance = 0.7  # 70% chance to cure infection at sanctuary
                    if random.random() < cure_chance:
                        player.infected = False
                        player.infection_timer = 0
                        type_text(f"The sanctuary's medical facilities have cured your infection!", sound=sound)
                        audio_manager.play_confirmation(True)
                    else:
                        type_text(f"The sanctuary's medical facilities have slowed the infection's progression.", sound=sound)
                        player.infection_timer += 2  # Add extra time before next damage

                time_spent += 60
                end_time += 60 * 60
                type_text(f"{settlement['sanctuary_dialogue']}", sound=sound)
                type_text(f"You rest and restore all HP and MP!", sound=sound)
                audio_manager.play_confirmation(True)
            else:
                type_text(f"You need 20 supplies to stay at the Sanctuary!", sound=sound)
                audio_manager.play_confirmation(False)

        elif choice == "2":
            if remaining_minutes < 30:
                type_text(f"Not enough time before nightfall! You need at least 30 minutes to trade.", sound=sound)
                audio_manager.play_confirmation(False)
                continue

            time_spent += 30
            end_time += 30 * 60

            # Trading loop with quantity support
            while True:
                type_text(f"\n{settlement['trader_dialogue']}", sound=sound)
                type_text("1. Buy Items", sound=sound)
                type_text("2. Sell Items", sound=sound)
                type_text("3. Back to settlement menu", sound=sound)

                _clear_rshift()
                shop_choice = input(f"\nEnter your choice: ")

                if shop_choice == "1":
                    # Barter system with quantity
                    prices = {
                        "Purified Water": random.randint(15, 25),
                        "Bandage": random.randint(8, 12),
                        "Antidote": random.randint(20, 30),
                        "Medkit": random.randint(40, 60),
                        "Rabbit's Pendant": random.randint(70, 100),
                        "Molotov Cocktail": random.randint(25, 40)
                    }
                    trade_with_quantity(player, prices, is_buying=True)

                elif shop_choice == "2":
                    # Selling with quantity
                    price_ranges = {
                        "Scrap Metal": (3, 5), "Cloth": (2, 4), "Herbs": (4, 6),
                        "Electronic Parts": (8, 12), "Mechanical Parts": (10, 15),
                        "Purified Water": (8, 12), "Bandage": (5, 8),
                        "Antidote": (10, 15), "Medkit": (20, 30),
                        "Molotov Cocktail": (10, 20)
                    }

                    # Create prices for items player actually has
                    sell_prices = {}
                    for item in price_ranges:
                        if item in player.inventory and player.inventory[item] > 0:
                            sell_prices[item] = random.randint(*price_ranges[item])

                    if not sell_prices:
                        type_text("You don't have anything to sell!", sound=sound)
                        continue

                    trade_with_quantity(player, sell_prices, is_buying=False)

                elif shop_choice == "3":
                    break
                else:
                    type_text(f"Invalid choice!", sound=sound)
                    audio_manager.play_confirmation(False)

        elif choice == "3":
            if remaining_minutes < 45:
                type_text(f"Not enough time before nightfall! You need at least 45 minutes to visit the workshop.", sound=sound)
                audio_manager.play_confirmation(False)
                continue

            workshop_time_spent = 0
            workshop_end_time = end_time

            # Workshop loop
            while workshop_time_spent < 45 and workshop_time_spent < time_remaining:
                type_text(f"\n{settlement['workshop_dialogue']}", sound=sound)
                type_text(f"Your supplies: {player.change}", sound=sound)

                # Show current stats for comparison
                type_text(f"\nYour current stats:", sound=sound)
                type_text(f"Attack: {player.attack}  Defense: {player.defense}  Max HP: {player.max_hp}", sound=sound)

                prices = {
                    "Reinforced Vest": {"price": random.randint(35, 45), "defense": 3},
                    "Sharpened Weapon": {"price": random.randint(45, 55), "attack": 3},
                    "Reinforced Armor": {"price": random.randint(80, 100), "defense": 5}
                }

                type_text(f"\nAvailable upgrades:", sound=sound)
                for i, (item, details) in enumerate(prices.items(), 1):
                    stat_boost = ""
                    if "defense" in details:
                        stat_boost = f"(Defense +{details['defense']})"
                    elif "attack" in details:
                        stat_boost = f"(Attack +{details['attack']})"

                    type_text(f"{i}. {item} {stat_boost} - {details['price']} supplies", sound=sound)

                type_text("4. Back to settlement menu", sound=sound)

                _clear_rshift()
                shop_choice = input(f"\nEnter your choice: ")
                if shop_choice == "1":
                    if player.change >= prices["Reinforced Vest"]["price"]:
                        player.change -= prices["Reinforced Vest"]["price"]
                        player.defense += prices["Reinforced Vest"]["defense"]
                        workshop_time_spent += 15
                        workshop_end_time += 15 * 60
                        type_text(f"You bought a Reinforced Vest! Defense increased by {prices['Reinforced Vest']['defense']}!", sound=sound)
                        audio_manager.play_confirmation(True)
                    else:
                        type_text(f"You don't have enough supplies!", sound=sound)
                        audio_manager.play_confirmation(False)
                elif shop_choice == "2":
                    if player.change >= prices["Sharpened Weapon"]["price"]:
                        player.change -= prices["Sharpened Weapon"]["price"]
                        player.attack += prices["Sharpened Weapon"]["attack"]
                        workshop_time_spent += 15
                        workshop_end_time += 15 * 60
                        type_text(f"You sharpened your weapon! Attack increased by {prices['Sharpened Weapon']['attack']}!", sound=sound)
                        audio_manager.play_confirmation(True)
                    else:
                        type_text(f"You don't have enough supplies!", sound=sound)
                        audio_manager.play_confirmation(False)
                elif shop_choice == "3":
                    if "Reinforced Vest" not in player.inventory or player.inventory["Reinforced Vest"] <= 0:
                        type_text(f"You need a Reinforced Vest to upgrade to Reinforced Armor!", sound=sound)
                        audio_manager.play_confirmation(False)
                    elif player.change >= prices["Reinforced Armor"]["price"]:
                        player.change -= prices["Reinforced Armor"]["price"]
                        player.defense += prices["Reinforced Armor"]["defense"]
                        player.inventory["Reinforced Vest"] -= 1
                        if player.inventory["Reinforced Vest"] <= 0:
                            del player.inventory["Reinforced Vest"]
                        workshop_time_spent += 15
                        workshop_end_time += 15 * 60
                        type_text(f"You upgraded to Reinforced Armor! Defense increased by {prices['Reinforced Armor']['defense']}!", sound=sound)
                        audio_manager.play_confirmation(True)
                    else:
                        type_text(f"You don't have enough supplies!", sound=sound)
                        audio_manager.play_confirmation(False)
                elif shop_choice == "4":
                    break
                else:
                    type_text(f"Invalid choice!", sound=sound)
                    audio_manager.play_confirmation(False)

            time_spent += workshop_time_spent
            end_time = workshop_end_time

        elif choice == "4":
            if remaining_minutes < 60:
                type_text(f"Not enough time before nightfall! You need at least 60 minutes to craft items.", sound=sound)
                audio_manager.play_confirmation(False)
                continue

            time_spent += 60
            end_time += 60 * 60
            craft_items(player)

        elif choice == "5":
            if remaining_minutes < 45:
                type_text(f"Not enough time before nightfall! You need at least 45 minutes for alchemy.", sound=sound)
                audio_manager.play_confirmation(False)
                continue

            # Alchemy loop
            while True:
                type_text(f"\n{settlement['alchemist_dialogue']}", sound=sound)
                type_text("1. Purify Herbs (3 Herbs + 1 Purified Water = Purified Herbs)", sound=sound)
                type_text("2. Learn Advanced Alchemy (Requires Alchemy Skill)", sound=sound)
                type_text("3. Back", sound=sound)

                _clear_rshift()
                alchemy_choice = input(f"\nEnter your choice: ")

                if alchemy_choice == "1":
                    if "Herbs" in player.inventory and player.inventory["Herbs"] >= 3 and "Purified Water" in player.inventory and player.inventory["Purified Water"] >= 1:
                        player.inventory["Herbs"] -= 3
                        player.inventory["Purified Water"] -= 1
                        player.inventory["Purified Herbs"] = player.inventory.get("Purified Herbs", 0) + 1
                        time_spent += 45
                        end_time += 45 * 60
                        type_text("You successfully purified the herbs! Created Purified Herbs.", sound=sound)
                        audio_manager.play_confirmation(True)
                    else:
                        type_text("You don't have enough materials! Need 3 Herbs and 1 Purified Water.", sound=sound)
                        audio_manager.play_confirmation(False)
                elif alchemy_choice == "2":
                    if "Alchemy" in player.learned_skills:
                        type_text("You learn advanced alchemical techniques! Your potions will be more effective.", sound=sound)
                        audio_manager.play_confirmation(True)
                        # This would unlock new recipes or improve existing ones
                    else:
                        type_text("You need to learn the Alchemy skill first!", sound=sound)
                        audio_manager.play_confirmation(False)
                elif alchemy_choice == "3":
                    break
                else:
                    type_text("Invalid choice!", sound=sound)
                    audio_manager.play_confirmation(False)

        elif choice == "6":
            if remaining_minutes < 15:
                type_text(f"Not enough time before nightfall! You need at least 15 minutes to talk to locals.", sound=sound)
                audio_manager.play_confirmation(False)
                continue

            time_spent += 15
            end_time += 15 * 60
            talk_to_npcs(player, settlement_type, sound=sound)

        elif choice == "7":
            if remaining_minutes < 30:
                type_text(f"Not enough time before nightfall! You need at least 30 minutes for equipment management.", sound=sound)
                audio_manager.play_confirmation(False)
                continue

            time_spent += 30
            end_time += 30 * 60
            player.display_equipment(sound=sound)

        elif choice == "8":
            if remaining_minutes < 15:
                type_text(f"Not enough time before nightfall! You need at least 15 minutes to use items.", sound=sound)
                audio_manager.play_confirmation(False)
                continue

            time_spent += 15
            end_time += 15 * 60
            use_items_from_backpack(player)

        elif choice == "9":
            current_time = time.time()
            remaining_time = max(0, end_time - current_time)
            remaining_minutes = int(remaining_time / 60)
            save_game(player, days_survived, remaining_minutes, "manual")
            type_text(f"Game saved successfully!", sound=sound)
            audio_manager.play_confirmation(True)

        elif choice == "10":
            current_time = time.time()
            remaining_time = max(0, end_time - current_time)
            remaining_minutes = remaining_time / 60
            type_text(f"Time until nightfall: {format_time(remaining_minutes)}", sound=sound)
            continue

        elif choice == "11":
            # Stop town music when leaving settlement
            audio_manager.stop()
            type_text(f"You leave the settlement.", sound=sound)
            break

        else:
            type_text(f"Invalid choice!", sound=sound)
            audio_manager.play_confirmation(False)

    return time_spent, end_time

def trade_with_quantity(player, prices, is_buying=True, sound=True):
    """Helper function for trading with quantity selection"""
    items = list(prices.keys())

    while True:
        type_text(f"\nAvailable items:", sound=sound)
        for i, item in enumerate(items, 1):
            price = prices[item]
            if is_buying:
                type_text(f"{i}. {item} - {price} supplies", sound=sound)
            else:
                type_text(f"{i}. {item} (You have: {player.inventory.get(item, 0)}) - {price} supplies each", sound=sound)

        type_text(f"{len(items)+1}. Done trading", sound=sound)

        try:
            _clear_rshift()
            choice = int(input(f"\nSelect item (or {len(items)+1} to finish): "))
            if choice == len(items)+1:
                break
            elif 1 <= choice <= len(items):
                item = items[choice-1]
                price = prices[item]

                if is_buying:
                    max_affordable = player.change // price
                    if max_affordable <= 0:
                        type_text(f"You can't afford any {item}!", sound=sound)
                        audio_manager.play_confirmation(False)
                        continue

                    quantity = int(input(f"How many {item} do you want to buy? (Max: {max_affordable}): "))
                    quantity = min(quantity, max_affordable)

                    if quantity > 0:
                        total_cost = quantity * price
                        player.change -= total_cost
                        player.inventory[item] = player.inventory.get(item, 0) + quantity
                        type_text(f"Bought {quantity} {item} for {total_cost} supplies!", sound=sound)
                        audio_manager.play_confirmation(True)
                        # Play item purchase sound
                        audio_manager.play_item_sound(item)
                else:
                    max_sellable = player.inventory.get(item, 0)
                    if max_sellable <= 0:
                        type_text(f"You don't have any {item} to sell!", sound=sound)
                        audio_manager.play_confirmation(False)
                        continue

                    quantity = int(input(f"How many {item} do you want to sell? (Max: {max_sellable}): "))
                    quantity = min(quantity, max_sellable)

                    if quantity > 0:
                        total_gain = quantity * price
                        player.change += total_gain
                        player.inventory[item] -= quantity
                        if player.inventory[item] <= 0:
                            del player.inventory[item]
                        type_text(f"Sold {quantity} {item} for {total_gain} supplies!", sound=sound)
                        audio_manager.play_confirmation(True)
            else:
                type_text(f"Invalid choice!", sound=sound)
                audio_manager.play_confirmation(False)
        except ValueError:
            type_text(f"Invalid input!", sound=sound)
            audio_manager.play_confirmation(False)

def craft_items(player, sound=True):
    """Crafting menu"""
    while True:
        type_text(f"\n=== CRAFTING MENU ===", sound=sound)
        type_text(f"Crafting Level: {player.crafting_level}", sound=sound)

        available_recipes = []
        for recipe_name in player.crafting_recipes:
            # Check if player has materials for at least one
            recipe = player.crafting_recipes[recipe_name]
            can_craft = True
            for material, amount in recipe.items():
                if player.inventory.get(material, 0) < amount:
                    can_craft = False
                    break
            if can_craft:
                available_recipes.append(recipe_name)

        if not available_recipes:
            type_text("You don't have materials for any recipes.", sound=sound)
            break

        for i, recipe in enumerate(available_recipes, 1):
            type_text(f"{i}. {recipe}", sound=sound)

        type_text(f"{len(available_recipes)+1}. Back to main menu", sound=sound)

        try:
            _clear_rshift()
            choice = int(input(f"\nSelect recipe to craft: "))
            if choice == len(available_recipes)+1:
                break
            elif 1 <= choice <= len(available_recipes):
                recipe_name = available_recipes[choice-1]
                player.craft_item(recipe_name, sound=sound)
            else:
                type_text(f"Invalid choice!", sound=sound)
                audio_manager.play_confirmation(False)
        except ValueError:
            type_text(f"Invalid input!", sound=sound)
            audio_manager.play_confirmation(False)

def use_items_from_backpack(player, sound=True):
    """Use items from inventory with improved information display"""
    usable_items = [item for item in player.inventory if item in ["Purified Water", "Bandage", "Antidote", "Medkit", "Advanced Medkit", "Rabbit's Pendant", "Purified Herbs", "Molotov Cocktail"] and player.inventory[item] > 0]

    if not usable_items:
        type_text("You don't have any usable items!", sound=sound)
        return

    while True:
        type_text(f"\n=== USE ITEMS ===", sound=sound)
        type_text(f"Current HP: {player.hp}/{player.max_hp}", sound=sound)
        type_text(f"Current MP: {player.mp}/{player.max_mp}", sound=sound)
        if player.infected and not player.is_infected_class:
            type_text(f"Infected! Timer: {player.infection_timer} turns", sound=sound)

        item_descriptions = {
            "Purified Water": "Heals 30 HP",
            "Bandage": "Heals 15 HP",
            "Antidote": "Cures infection",
            "Medkit": "Heals 50 HP",
            "Advanced Medkit": "Heals 80 HP and cures infection",
            "Rabbit's Pendant": "Boosts next 3 parries (70-100% chance)",
            "Purified Herbs": "Heals 25 HP and 10 MP",
            "Molotov Cocktail": "Throwable weapon for battle (damage + fire)"
        }

        for i, item in enumerate(usable_items, 1):
            description = item_descriptions.get(item, "No description")
            type_text(f"{i}. {item} x{player.inventory[item]} - {description}", sound=sound)

        type_text(f"{len(usable_items)+1}. Back", sound=sound)

        try:
            _clear_rshift()
            choice = int(input(f"\nSelect item to use (or {len(usable_items)+1} to go back): "))
            if choice == len(usable_items)+1:
                break
            elif 1 <= choice <= len(usable_items):
                item = usable_items[choice-1]
                player.use_item(item, sound=sound)
            else:
                type_text(f"Invalid choice!", sound=sound)
                audio_manager.play_confirmation(False)
        except ValueError:
            type_text(f"Invalid input!", sound=sound)
            audio_manager.play_confirmation(False)

def manage_equipment_in_settlement(player, sound=True):
    """Equipment management in settlement"""
    player.display_equipment(sound=sound)

def save_game(player, days, time_remaining, save_type="manual"):
    save_data = {
        "player": {
            "name": player.name,
            "job_class": player.job_class,
            "level": player.level,
            "exp": player.exp,
            "exp_to_next": player.exp_to_next,
            "crafting_level": player.crafting_level,
            "crafting_exp": player.crafting_exp,
            "crafting_exp_to_next": player.crafting_exp_to_next,
            "max_hp": player.max_hp,
            "hp": player.hp,
            "max_mp": player.max_mp,
            "mp": player.mp,
            "attack": player.attack,
            "defense": player.defense,
            "magic": player.magic,
            "parry_chance": player.parry_chance,
            "change": player.change,
            "inventory": player.inventory,
            "spells": player.spells,
            "infected": player.infected,
            "infection_timer": player.infection_timer,
            "skill_points": player.skill_points,
            "learned_skills": player.learned_skills,
            "found_lore": player.found_lore,
            "stealth_bonus": player.stealth_bonus,
            "collectables": player.collectables,
            "equipped": player.equipped,
            "base_stats": player.base_stats,
            "is_infected_class": player.is_infected_class,
            "night_health_drain": player.night_health_drain,
            "mutation_chance": player.mutation_chance,
            "mutations": player.mutations,
            "mutation_benefits": player.mutation_benefits
        },
        "days_survived": days,
        "time_remaining": time_remaining,
        "save_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "save_type": save_type
    }

    filename = f"hordes_save_{save_type}.json"
    with open(filename, 'w') as f:
        json.dump(save_data, f, indent=2)

def load_game():
    saves = []
    if os.path.exists("hordes_save_manual.json"):
        saves.append(("Manual Save", "hordes_save_manual.json"))
    if os.path.exists("hordes_save_autosave.json"):
        saves.append(("Auto Save", "hordes_save_autosave.json"))

    if not saves:
        return None, 0, 0

    type_text(f"\nAvailable saves:")
    for i, (save_name, filename) in enumerate(saves, 1):
        with open(filename, 'r') as f:
            save_data = json.load(f)
            type_text(f"{i}. {save_name} - Day {save_data['days_survived']} - {save_data['save_date']}")

    try:
        _clear_rshift()
        choice = int(input(f"\nSelect save to load (0 to cancel): "))
        if choice == 0:
            return None, 0, 0
        elif 1 <= choice <= len(saves):
            _, filename = saves[choice-1]
            with open(filename, 'r') as f:
                save_data = json.load(f)

            player = Character(save_data["player"]["name"], save_data["player"]["job_class"])
            for attr, value in save_data["player"].items():
                if hasattr(player, attr):
                    setattr(player, attr, value)

            return player, save_data["days_survived"], save_data["time_remaining"]
    except (ValueError, IndexError):
        pass

    return None, 0, 0

def game_settings_menu():
    settings = {
        "auto_save": True,
        "text_speed": 0.03,
        "show_tutorials": True,
        "typing_sound": True,
        "typing_sound_volume": 0.3,
        "music_volume": 0.8,
        "menu_speed": menu_settings.get_speed()
    }

    if os.path.exists("hordes_settings.json"):
        with open("hordes_settings.json", 'r') as f:
            loaded_settings = json.load(f)
            settings.update(loaded_settings)
            # Update menu settings
            if "menu_speed" in loaded_settings:
                menu_settings.set_speed(loaded_settings["menu_speed"])

    while True:
        type_text(f"\n=== GAME SETTINGS ===")
        type_text(f"1. Auto-save: {'ON' if settings['auto_save'] else 'OFF'}")
        type_text(f"2. Text speed: {'Fast' if settings['text_speed'] < 0.03 else 'Normal' if settings['text_speed'] == 0.03 else 'Slow'}")
        type_text(f"3. Show tutorials: {'ON' if settings['show_tutorials'] else 'OFF'}")
        type_text(f"4. Typing sound: {'ON' if settings['typing_sound'] else 'OFF'}")
        type_text(f"5. Typing sound volume: {int(settings['typing_sound_volume'] * 100)}%")
        type_text(f"6. Music volume: {int(settings['music_volume'] * 100)}%")
        type_text(f"7. Speed Menu: {settings['menu_speed'].title()}")
        type_text("8. Save and return to main menu")

        _clear_rshift()
        choice = input(f"\nEnter your choice: ")

        if choice == "1":
            settings["auto_save"] = not settings["auto_save"]
            type_text(f"Auto-save turned {'ON' if settings['auto_save'] else 'OFF'}")
            audio_manager.play_menu_select()
        elif choice == "2":
            speed_options = [0.01, 0.03, 0.05]
            speed_names = ["Fast", "Normal", "Slow"]
            type_text(f"\nText speed options:")
            for i, (speed, name) in enumerate(zip(speed_options, speed_names), 1):
                type_text(f"{i}. {name}")

            try:
                speed_choice = int(input(f"Select text speed: "))
                if 1 <= speed_choice <= len(speed_options):
                    settings["text_speed"] = speed_options[speed_choice-1]
                    type_text(f"Text speed set to {speed_names[speed_choice-1]}")
                    audio_manager.play_menu_select()
                else:
                    type_text(f"Invalid choice!")
                    audio_manager.play_confirmation(False)
            except ValueError:
                type_text(f"Invalid input!")
                audio_manager.play_confirmation(False)
        elif choice == "3":
            settings["show_tutorials"] = not settings["show_tutorials"]
            type_text(f"Tutorials turned {'ON' if settings['show_tutorials'] else 'OFF'}")
            audio_manager.play_menu_select()
        elif choice == "4":
            settings["typing_sound"] = not settings["typing_sound"]
            typing_sound.set_enabled(settings["typing_sound"])
            type_text(f"Typing sound turned {'ON' if settings['typing_sound'] else 'OFF'}")
            audio_manager.play_menu_select()
        elif choice == "5":
            try:
                vol = int(input("Enter typing sound volume (0-100): "))
                vol = max(0, min(100, vol))
                settings["typing_sound_volume"] = vol / 100
                typing_sound.set_volume(settings["typing_sound_volume"])
                type_text(f"Typing sound volume set to {vol}%")
                audio_manager.play_menu_select()
            except ValueError:
                type_text(f"Invalid input!")
                audio_manager.play_confirmation(False)
        elif choice == "6":
            try:
                vol = int(input("Enter music volume (0-100): "))
                vol = max(0, min(100, vol))
                settings["music_volume"] = vol / 100
                audio_manager.set_volume(settings["music_volume"])
                type_text(f"Music volume set to {vol}%")
                audio_manager.play_menu_select()
            except ValueError:
                type_text(f"Invalid input!")
                audio_manager.play_confirmation(False)
        elif choice == "7":
            type_text(f"\nMenu Speed Options:")
            type_text(f"1. Normal - Menus display with typing animation")
            type_text(f"2. Instant - Menus appear instantly")

            try:
                speed_choice = int(input(f"Select menu speed: "))
                if speed_choice == 1:
                    settings["menu_speed"] = "normal"
                    menu_settings.set_speed("normal")
                    type_text(f"Menu speed set to Normal")
                    audio_manager.play_menu_select()
                elif speed_choice == 2:
                    settings["menu_speed"] = "instant"
                    menu_settings.set_speed("instant")
                    type_text(f"Menu speed set to Instant")
                    audio_manager.play_menu_select()
                else:
                    type_text(f"Invalid choice!")
                    audio_manager.play_confirmation(False)
            except ValueError:
                type_text(f"Invalid input!")
                audio_manager.play_confirmation(False)
        elif choice == "8":
            with open("hordes_settings.json", 'w') as f:
                json.dump(settings, f, indent=2)
            return settings
        else:
            type_text(f"Invalid choice!")
            audio_manager.play_confirmation(False)

def main_menu():
    # Ensure audio manager is ready and play menu music immediately
    if audio_manager._has_mixer and audio_manager.enabled:
        audio_manager.stop_immediately()  # Clear any existing music
        time.sleep(0.1)  # Brief pause
        audio_manager.play_intro()  # Using intro music for main menu (will loop seamlessly)

    while True:
        type_text(f"\n==========================================HOƦDEZ==============================================")
        type_text("1. New Game")
        type_text("2. Load Game")
        type_text("3. Settings")
        type_text("4. Exit")

        _clear_rshift()
        choice = input(f"\nEnter your choice: ")

        if choice == "1":
            # Play menu select sound
            audio_manager.play_menu_select()
            # Stop intro music before starting new game
            audio_manager.stop()
            return new_game()
        elif choice == "2":
            audio_manager.play_menu_select()
            player, days, time_remaining = load_game()
            if player:
                # Stop intro music when loading game
                audio_manager.stop()
                return player, days, time_remaining
            else:
                type_text(f"No save games found or invalid selection!")
                audio_manager.play_confirmation(False)
        elif choice == "3":
            audio_manager.play_menu_select()
            settings = game_settings_menu()
            # Resume menu music after settings
            if audio_manager._has_mixer and audio_manager.enabled:
                audio_manager.play_intro()
            continue
        elif choice == "4":
            audio_manager.play_menu_select()
            type_text(f"Thanks for playing!")
            exit()
        else:
            type_text(f"Invalid choice!")
            audio_manager.play_confirmation(False)

def new_game():
    # Day music will start when main() begins

    type_text(f"The outbreak has decimated civilization. You are one of the few survivors...")

    name = input(f"\nEnter your character's name: ")

    type_text(f"\nChoose your survivor class:")
    type_text("1. Survivor - Balanced fighter with good health and combat skills")
    type_text("2. Scavenger - Resourceful with trap-making and improvisation skills")
    type_text("3. Medic - Healing expertise and medical knowledge")
    type_text("4. Infected - Viral host with unique abilities (Hard Mode)")

    class_choice = input(f"\nEnter your choice: ")

    class_map = {"1": "Survivor", "2": "Scavenger", "3": "Medic", "4": "Infected"}
    job_class = class_map.get(class_choice, "Survivor")

    if job_class == "Infected":
        type_text(f"\nWarning: The Infected class is a hard mode character.")
        type_text(f"You are immune to infection but suffer health drain at night.")
        type_text(f"You also have a chance to mutate each hour, gaining permanent stat boosts.")

    player = Character(name, job_class)
    type_text(f"\n {player.name}! Your struggle for survival begins...")
    return player, 0, 480

def game_over_screen(days_survived):
    type_text(f"\n{'='*60}")
    type_text(f"{'GAME OVER'.center(60)}")
    type_text(f"{'='*60}")
    type_text(f"You survived for {days_survived} days.")
    type_text(f"The hordes have overwhelmed you...")
    type_text(f"\n1. Return to Main Menu")
    type_text(f"2. Exit Game")

    _clear_rshift()
    choice = input(f"\nEnter your choice: ")

    if choice == "1":
        return True
    elif choice == "2":
        type_text(f"Thanks for playing!")
        exit()
    else:
        type_text(f"Invalid choice!")
        return game_over_screen(days_survived)

def main():
    global days_survived

    game_settings = {}
    if os.path.exists("hordes_settings.json"):
        with open("hordes_settings.json", 'r') as f:
            game_settings = json.load(f)
    else:
        game_settings = {
            "auto_save": True,
            "text_speed": 0.03,
            "show_tutorials": True,
            "typing_sound": True,
            "typing_sound_volume": 0.3,
            "music_volume": 0.8,
            "menu_speed": "normal"
        }

    # Apply settings
    typing_sound.set_enabled(game_settings.get("typing_sound", True))
    typing_sound.set_volume(game_settings.get("typing_sound_volume", 0.3))
    audio_manager.set_volume(game_settings.get("music_volume", 0.8))
    menu_settings.set_speed(game_settings.get("menu_speed", "normal"))

    player, days_survived, time_remaining = main_menu()

    game_over = False

    while not game_over:
        days_survived += 1
        time_remaining = 480

        # Play day music (will loop seamlessly)
        audio_manager.play_day()

        type_text(f"\n--- Day {days_survived} ---")
        type_text(f"The sun rises. 8 hours until nightfall... Zombies are stronger during the night.")

        start_time = time.time()
        end_time = start_time + (time_remaining * 60)

        while time_remaining > 0 and not game_over:
            current_time = time.time()
            if current_time < end_time:
                remaining_seconds = int(end_time - current_time)
                minutes = remaining_seconds // 60
                seconds = remaining_seconds % 60
                time_remaining = minutes + (seconds / 60)
            else:
                time_remaining = 0

            if not player.process_infection():
                game_over = True
                break

            player.display_stats()

            type_text(f"\nWhat would you like to do?")
            type_text("1. Scavenge for supplies")
            type_text("2. Return to camp/Check supplies")

            if random.random() < 0.25:
                # Procedurally generate today's settlement
                _proc_settle = generate_settlement(days_survived, slot=random.randint(0, 4))
                settlement_type = _proc_settle["base_type"]
                type_text(f"3. Visit {_proc_settle['name']}")
                type_text("4. Craft Items")
                type_text("5. Check Status")
                type_text("6. Backpack (Use Items)")
                type_text("7. Check Inventory")
                type_text("8. Check Lore Documents")
                type_text("9. Check Collectables")
                type_text("10. Skill Tree")
                type_text("11. Equipment Management")
                type_text("12. Rest (pass time)")
                type_text("13. Check Time")
                type_text("14. Save and Quit")

                _clear_rshift()
                choice = input(f"\nEnter your choice: ")

                if choice == "1":
                    # Stop day music when scavenging
                    audio_manager.stop()
                    time_spent, survived = scavenge_location(player, time_remaining, is_night=False, day=days_survived)
                    # Resume day music after scavenging
                    audio_manager.play_day()
                    end_time -= (time_spent * 60)
                    time_remaining -= time_spent
                    if not survived:
                        game_over = True

                elif choice == "2":
                    type_text("You return to your temporary camp to organize your supplies.", sound=True)
                    player.display_inventory()
                    player.display_status()
                    time_spent = 15
                    end_time -= (time_spent * 60)
                    time_remaining -= time_spent

                elif choice == "3":
                    # Stop day music when entering settlement
                    audio_manager.stop()
                    time_spent, end_time = visit_settlement(player, time_remaining, game_settings, end_time, settlement_type, proc_settlement=_proc_settle if "_proc_settle" in dir() else None)
                    # Resume day music after leaving settlement
                    audio_manager.play_day()
                    time_remaining -= time_spent

                elif choice == "4":
                    craft_items(player)
                    time_spent = 30
                    end_time -= (time_spent * 60)
                    time_remaining -= time_spent

                elif choice == "5":
                    player.display_status()
                    continue

                elif choice == "6":
                    use_items_from_backpack(player)
                    time_spent = 15
                    end_time -= (time_spent * 60)
                    time_remaining -= time_spent

                elif choice == "7":
                    player.display_inventory()
                    continue

                elif choice == "8":
                    player.display_lore()
                    continue

                elif choice == "9":
                    player.display_collectables()
                    continue

                elif choice == "10":
                    player.show_skill_tree()
                    continue

                elif choice == "11":
                    player.display_equipment()
                    continue

                elif choice == "12":
                    rest_time = min(time_remaining, 120)
                    end_time -= (rest_time * 60)
                    time_remaining -= rest_time
                    heal_amount = min(player.max_hp - player.hp, rest_time // 2)
                    player.hp += heal_amount
                    type_text(f"You rest for {rest_time} minutes and recover {heal_amount} HP.")

                    # Random encounter during rest
                    if not random_encounter(player):
                        game_over = True
                        break

                elif choice == "13":
                    type_text(f"Time until nightfall: {format_time(time_remaining)}")
                    continue

                elif choice == "14":
                    current_time = time.time()
                    remaining_time = max(0, end_time - current_time)
                    remaining_minutes = int(remaining_time / 60)
                    save_game(player, days_survived, remaining_minutes, "manual")
                    type_text(f"Game saved. Thanks for playing!")
                    return

                else:
                    type_text(f"Invalid choice!")
                    audio_manager.play_confirmation(False)
            else:
                type_text("3. Craft Items")
                type_text("4. Check Status")
                type_text("5. Backpack (Use Items)")
                type_text("6. Check Inventory")
                type_text("7. Check Lore Documents")
                type_text("8. Check Collectables")
                type_text("9. Skill Tree")
                type_text("10. Equipment Management")
                type_text("11. Rest (pass time)")
                type_text("12. Check Time")
                type_text("13. Save and Quit")

                _clear_rshift()
                choice = input(f"\nEnter your choice: ")

                if choice == "1":
                    # Stop day music when scavenging
                    audio_manager.stop()
                    time_spent, survived = scavenge_location(player, time_remaining, is_night=False, day=days_survived)
                    # Resume day music after scavenging
                    audio_manager.play_day()
                    end_time -= (time_spent * 60)
                    time_remaining -= time_spent
                    if not survived:
                        game_over = True

                elif choice == "2":
                    type_text("You return to your temporary camp to organize your supplies.", sound=True)
                    player.display_inventory()
                    player.display_status()
                    time_spent = 15
                    end_time -= (time_spent * 60)
                    time_remaining -= time_spent

                elif choice == "3":
                    craft_items(player)
                    time_spent = 30
                    end_time -= (time_spent * 60)
                    time_remaining -= time_spent

                elif choice == "4":
                    player.display_status()
                    continue

                elif choice == "5":
                    use_items_from_backpack(player)
                    time_spent = 15
                    end_time -= (time_spent * 60)
                    time_remaining -= time_spent

                elif choice == "6":
                    player.display_inventory()
                    continue

                elif choice == "7":
                    player.display_lore()
                    continue

                elif choice == "8":
                    player.display_collectables()
                    continue

                elif choice == "9":
                    player.show_skill_tree()
                    continue

                elif choice == "10":
                    player.display_equipment()
                    continue

                elif choice == "11":
                    rest_time = min(time_remaining, 120)
                    end_time -= (rest_time * 60)
                    time_remaining -= rest_time
                    heal_amount = min(player.max_hp - player.hp, rest_time // 2)
                    player.hp += heal_amount
                    type_text(f"You rest for {rest_time} minutes and recover {heal_amount} HP.")

                    # Random encounter during rest
                    if not random_encounter(player):
                        game_over = True
                        break

                elif choice == "12":
                    type_text(f"Time until nightfall: {format_time(time_remaining)}")
                    continue

                elif choice == "13":
                    current_time = time.time()
                    remaining_time = max(0, end_time - current_time)
                    remaining_minutes = int(remaining_time / 60)
                    save_game(player, days_survived, remaining_minutes, "manual")
                    type_text(f"Game saved. Thanks for playing!")
                    return

                else:
                    type_text(f"Invalid choice!")
                    audio_manager.play_confirmation(False)

        # If player is in a settlement when night falls, they stay there safely
        if not game_over:
            # Switch to night music
            audio_manager.play_night()

            type_text(f"\nNight falls. The zombies become more active and dangerous...")
            type_text(f"You have 8 hours to survive until dawn...")

            night_remaining = 480  # 8 hours in minutes, same duration as the day phase
            night_start_time = time.time()
            night_end_time = night_start_time + (night_remaining * 60)

            night_hours_processed = 0  # Track Infected class hourly drain

            while night_remaining > 0 and not game_over:
                current_time = time.time()
                if current_time < night_end_time:
                    remaining_seconds = int(night_end_time - current_time)
                    night_mins = remaining_seconds // 60
                    night_secs = remaining_seconds % 60
                    night_remaining = night_mins + (night_secs / 60)
                else:
                    night_remaining = 0

                # Process Infected class hourly night drain incrementally
                if player.is_infected_class:
                    hours_elapsed = int((480 - night_remaining) / 60)
                    while night_hours_processed < hours_elapsed:
                        if not player.process_night_effects(1):
                            game_over = True
                            break
                        night_hours_processed += 1
                    if game_over:
                        break

                # Process infection tick
                if not player.process_infection():
                    game_over = True
                    break

                player.display_stats()
                type_text(f"\n[NIGHT] Time until dawn: {format_time(night_remaining)}")
                type_text("\nWhat would you like to do?")
                type_text("1. Scavenge (DANGEROUS at night)")
                type_text("2. Hunker Down (Rest safely, pass 60 minutes)")
                type_text("3. Check Status")
                type_text("4. Backpack (Use Items)")
                type_text("5. Check Inventory")
                type_text("6. Skill Tree")
                type_text("7. Equipment Management")
                type_text("8. Check Time Until Dawn")
                type_text("9. Save and Quit")

                _clear_rshift()
                night_choice = input("\nEnter your choice: ")

                if night_choice == "1":
                    audio_manager.stop()
                    time_spent_night, survived_night = scavenge_location(
                        player, night_remaining, is_night=True
                    )
                    audio_manager.play_night()
                    night_end_time -= (time_spent_night * 60)
                    night_remaining -= time_spent_night
                    if not survived_night:
                        game_over = True

                elif night_choice == "2":
                    rest_time = min(night_remaining, 60)
                    night_end_time -= (rest_time * 60)
                    night_remaining -= rest_time
                    heal_amount = min(player.max_hp - player.hp, int(rest_time // 3))
                    player.hp += heal_amount
                    type_text(f"You hunker down for {int(rest_time)} minutes and recover {heal_amount} HP.")
                    # Small random encounter chance even while hunkered down
                    if random.random() < 0.15:
                        type_text("Something creeps close while you rest...")
                        if not random_encounter(player):
                            game_over = True

                elif night_choice == "3":
                    player.display_status()
                    continue

                elif night_choice == "4":
                    use_items_from_backpack(player)
                    night_end_time -= (15 * 60)
                    night_remaining -= 15

                elif night_choice == "5":
                    player.display_inventory()
                    continue

                elif night_choice == "6":
                    player.show_skill_tree()
                    continue

                elif night_choice == "7":
                    player.display_equipment()
                    continue

                elif night_choice == "8":
                    type_text(f"Time until dawn: {format_time(night_remaining)}")
                    continue

                elif night_choice == "9":
                    current_t = time.time()
                    rem_min = int(max(0, night_end_time - current_t) / 60)
                    save_game(player, days_survived, rem_min, "manual")
                    type_text("Game saved. Thanks for playing!")
                    return

                else:
                    type_text("Invalid choice!")
                    audio_manager.play_confirmation(False)

            if not game_over:
                type_text(f"\nDawn breaks. You survived the night!")
                type_text(f"You rest briefly as the sun rises, recovering some strength.")
                player.hp = min(player.max_hp, player.hp + player.max_hp // 4)
                player.mp = min(player.max_mp, player.mp + player.max_mp // 3)
                audio_manager.play_day()
                # Auto-save at dawn
                if game_settings.get("auto_save", True):
                    save_game(player, days_survived, 480, "autosave")
                    type_text("Game auto-saved.")

    if game_over:
        # Stop all music on game over
        audio_manager.stop()
        if game_over_screen(days_survived):
            main()

if __name__ == "__main__":
    days_survived = 0
    main()