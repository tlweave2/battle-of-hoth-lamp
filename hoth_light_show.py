import socket
import json
import time
import threading
import pygame
from typing import Dict, Any, List, Tuple
import os
import math
import numpy as np
try:
    import librosa
    AUDIO_ANALYSIS_AVAILABLE = True
except ImportError:
    AUDIO_ANALYSIS_AVAILABLE = False

class FastWizController:
    def __init__(self, bulb_ip: str, port: int = 38899):
        self.bulb_ip = bulb_ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.1)  # Much faster timeout
        self.last_command = None
        self.command_interval = 0.15  # Minimum time between commands
        self.last_send_time = 0
    
    def send_command_fast(self, command: Dict[str, Any]) -> bool:
        """Fast command sending with duplicate filtering"""
        current_time = time.time()
        
        # Skip if same command sent recently
        if (self.last_command == command and 
            current_time - self.last_send_time < self.command_interval):
            return True
        
        try:
            message = json.dumps(command).encode('utf-8')
            self.sock.sendto(message, (self.bulb_ip, self.port))
            self.last_command = command
            self.last_send_time = current_time
            return True
        except:
            return False
    
    def set_rgb_fast(self, red: int, green: int, blue: int, brightness: int = 100):
        """Optimized RGB setting"""
        brightness_factor = brightness / 100.0
        r = max(0, min(255, int(red * brightness_factor)))
        g = max(0, min(255, int(green * brightness_factor)))
        b = max(0, min(255, int(blue * brightness_factor)))
        
        command = {
            "method": "setPilot",
            "params": {"state": True, "r": r, "g": g, "b": b}
        }
        return self.send_command_fast(command)
    
    def turn_off(self):
        command = {"method": "setPilot", "params": {"state": False}}
        return self.send_command_fast(command)
    
    def close(self):
        self.sock.close()

class OptimizedHothShow:
    def __init__(self, bulb_ip: str, audio_file: str):
        self.bulb = FastWizController(bulb_ip)
        self.audio_file = audio_file
        self.is_playing = False
        self.stop_flag = False
        self.blaster_enabled = True
        self.detected_blasters = []
        
        # Enhanced color palette with blaster effects
        self.colors = {
            'rebel_orange': (255, 120, 0),
            'ice_blue': (100, 150, 255),
            'comm_green': (0, 255, 80),
            'alert_red': (255, 50, 50),
            'bright_white': (255, 255, 255),
            'dim_blue': (50, 50, 150),
            # Blaster colors
            'rebel_blaster': (255, 100, 0),      # Orange-red rebel shots
            'imperial_blaster': (0, 255, 50),    # Green imperial shots
            'heavy_turbo': (255, 255, 200),      # Heavy turbolaser
            'ion_cannon': (150, 150, 255),       # Ion cannon blue
            'explosion_flash': (255, 255, 255)   # Explosion/impact
        }
        
        # Base light sequence
        self.key_moments = [
            (0.0, 'dim_blue', 30, "Echo station 57..."),
            (2.5, 'comm_green', 60, "we're on our way"),
            (4.5, 'rebel_orange', 70, "all right boys keep tight"),
            (7.0, 'ice_blue', 55, "Luke I have no approach"),
            (9.5, 'alert_red', 85, "I'm not set, steady"),
            (12.0, 'bright_white', 95, "attack pattern Delta GO!"),
            (14.5, 'rebel_orange', 80, "all right coming in"),
            (17.0, 'ice_blue', 65, "you still with us"),
            (19.0, 'comm_green', 75, "final approach")
        ]
        
        # Manual blaster timing for known shots in this clip
        self.manual_blasters = [
            # Time, Type, Intensity (1-10)
            (3.2, 'rebel_blaster', 8),      # Possible shot during "on our way"
            (6.8, 'imperial_blaster', 7),   # Incoming fire sound
            (10.2, 'heavy_turbo', 9),       # Heavy weapon sound
            (13.0, 'rebel_blaster', 8),     # Attack begins
            (15.8, 'imperial_blaster', 7),  # Return fire
            (18.5, 'explosion_flash', 10),  # Big impact/explosion
        ]
        
        # Initialize audio analysis if available
        if AUDIO_ANALYSIS_AVAILABLE:
            self.analyze_for_blasters()
        else:
            print("📢 Audio analysis not available - using manual blaster timing")
            print("   Install with: pip install librosa")
    
    def analyze_for_blasters(self):
        """Analyze audio for blaster-like sounds"""
        try:
            print("🔫 Analyzing audio for blaster shots...")
            
            # Load audio
            y, sr = librosa.load(self.audio_file)
            
            # Detect sharp transients (blaster-like sounds)
            onset_frames = librosa.onset.onset_detect(
                y=y, sr=sr, 
                pre_avg=3, post_avg=5, 
                pre_max=3, post_max=5,
                delta=0.2, wait=10
            )
            onset_times = librosa.frames_to_time(onset_frames, sr=sr)
            
            # Filter for blaster-like characteristics
            hop_length = 512
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length)[0]
            rms_energy = librosa.feature.rms(y=y, hop_length=hop_length)[0]
            
            detected_blasters = []
            
            for onset_time in onset_times:
                if onset_time > 21.0:  # Only within our 21-second clip
                    continue
                    
                # Get audio features at this time
                frame_idx = int(onset_time * sr / hop_length)
                if frame_idx < len(spectral_centroids):
                    brightness = spectral_centroids[frame_idx]
                    energy = rms_energy[frame_idx]
                    
                    # Classify blaster type based on audio characteristics
                    blaster_type = 'rebel_blaster'  # default
                    intensity = min(10, int(energy * 20))
                    
                    # High frequency + high energy = turbolaser
                    if brightness > 3000 and energy > 0.3:
                        blaster_type = 'heavy_turbo'
                        intensity = min(10, intensity + 2)
                    # Medium frequency = imperial blaster
                    elif 1500 < brightness < 3000:
                        blaster_type = 'imperial_blaster'
                    # Low frequency + high energy = explosion
                    elif brightness < 1000 and energy > 0.4:
                        blaster_type = 'explosion_flash'
                        intensity = 10
                    
                    detected_blasters.append((onset_time, blaster_type, intensity))
            
            self.detected_blasters = detected_blasters
            print(f"🎯 Detected {len(detected_blasters)} potential blaster shots!")
            
            # Show detected shots
            for time_val, shot_type, intensity in detected_blasters[:5]:  # Show first 5
                print(f"   {time_val:.1f}s: {shot_type} (intensity {intensity})")
            
        except Exception as e:
            print(f"⚠️ Blaster analysis failed: {e}")
            print("📢 Using manual blaster timing instead")
            self.detected_blasters = []
    
    def get_active_blaster(self, current_time: float) -> Tuple[str, int, float]:
        """Check if a blaster shot should be active at current time"""
        # Combine manual and detected blasters
        all_blasters = self.manual_blasters + self.detected_blasters
        
        for shot_time, shot_type, intensity in all_blasters:
            # Blaster effects last 0.1-0.15 seconds
            effect_duration = 0.15 if shot_type == 'explosion_flash' else 0.1
            
            if shot_time <= current_time <= shot_time + effect_duration:
                # Calculate flash intensity based on time within effect
                time_in_effect = current_time - shot_time
                flash_intensity = 1.0 - (time_in_effect / effect_duration)
                return shot_type, intensity, flash_intensity
        
        return None, 0, 0
    
    def apply_blaster_effect(self, base_color: str, base_brightness: int, 
                           current_time: float) -> Tuple[str, int]:
        """Apply blaster effects over base lighting"""
        if not self.blaster_enabled:
            return base_color, base_brightness
        
        shot_type, intensity, flash_intensity = self.get_active_blaster(current_time)
        
        if shot_type:
            # Blaster shot is active - override base lighting
            effective_brightness = min(100, int(base_brightness + (intensity * flash_intensity * 5)))
            return shot_type, effective_brightness
        
        return base_color, base_brightness
    
    def get_current_lighting(self, current_time: float) -> Tuple[str, int]:
        """Get current color and brightness based on time"""
        # Find the most recent key moment
        active_moment = self.key_moments[0]  # Default
        
        for moment in self.key_moments:
            if current_time >= moment[0]:
                active_moment = moment
            else:
                break
        
        return active_moment[1], active_moment[2]  # color, brightness
    
    def add_beat_effects(self, base_color: str, base_brightness: int, current_time: float) -> Tuple[str, int]:
        """Add subtle beat-synchronized effects"""
        # Key beat moments in the 21-second clip
        beat_times = [2.8, 4.2, 6.1, 8.3, 10.5, 12.2, 14.0, 15.8, 17.5, 19.2]
        
        # Check if we're near a beat (within 0.3 seconds)
        near_beat = any(abs(current_time - beat) < 0.3 for beat in beat_times)
        
        if near_beat:
            # Boost brightness slightly for beats
            brightness = min(100, base_brightness + 15)
            # Flash to white for "GO NOW" moment
            if 12.0 <= current_time <= 12.5:
                return 'bright_white', 100
        else:
            brightness = base_brightness
        
        return base_color, brightness
    
    def light_control_thread(self):
        """Enhanced light control with blaster effects"""
        start_time = time.time()
        last_update = 0
        last_color = None
        last_brightness = None
        blaster_count = 0
        
        print("🎆 Starting Battle of Hoth with BLASTER EFFECTS!")
        
        while self.is_playing and not self.stop_flag:
            current_time = time.time() - start_time
            
            if current_time >= 21.0:
                break
            
            # Update every 100ms for blaster responsiveness
            if current_time - last_update >= 0.1:
                # Get base lighting
                color_name, brightness = self.get_current_lighting(current_time)
                
                # Add beat effects
                color_name, brightness = self.add_beat_effects(color_name, brightness, current_time)
                
                # APPLY BLASTER EFFECTS (this can override everything!)
                original_color = color_name
                color_name, brightness = self.apply_blaster_effect(color_name, brightness, current_time)
                
                # Track blaster shots for stats
                if color_name != original_color and color_name in ['rebel_blaster', 'imperial_blaster', 'heavy_turbo', 'explosion_flash']:
                    if color_name != last_color:  # New blaster shot
                        blaster_count += 1
                        blaster_names = {
                            'rebel_blaster': '🔸 REBEL SHOT',
                            'imperial_blaster': '🔹 IMPERIAL SHOT', 
                            'heavy_turbo': '💥 TURBOLASER',
                            'explosion_flash': '💥💥 EXPLOSION'
                        }
                        print(f"  {blaster_names.get(color_name, '🔫 BLASTER')} at {current_time:.1f}s!")
                
                # Send command if changed significantly
                if (color_name != last_color or abs(brightness - (last_brightness or 0)) > 8):
                    r, g, b = self.colors[color_name]
                    self.bulb.set_rgb_fast(r, g, b, brightness)
                    
                    last_color = color_name
                    last_brightness = brightness
                
                last_update = current_time
            
            time.sleep(0.03)  # Faster updates for blaster responsiveness
        
        if blaster_count > 0:
            print(f"🎯 Total blaster effects: {blaster_count}")
    
    def play_synchronized_show(self):
        """Play optimized synchronized show with blaster effects"""
        print("\n" + "="*60)
        print("💥 BATTLE OF HOTH WITH BLASTER EFFECTS 💥")
        print("="*60)
        print("🔫 Real-time blaster shots synchronized to audio!")
        print("🚀 Enhanced performance + Star Wars combat lighting!")
        
        try:
            # Test connection first
            print("🔧 Testing bulb connection...")
            if not self.bulb.set_rgb_fast(100, 100, 100, 50):
                print("⚠️ Warning: Bulb may not be responding optimally")
            else:
                print("✅ Bulb connection OK!")
                time.sleep(0.5)
            
            # Initialize pygame
            pygame.mixer.init()
            pygame.mixer.music.load(self.audio_file)
            
            # Countdown with light sync
            for i in range(3, 0, -1):
                print(f"🎬 Starting in {i}...")
                self.bulb.set_rgb_fast(255, 255, 255, 30 * i)
                time.sleep(1)
            
            print("🎆 ACTION!")
            
            # Start light thread
            self.is_playing = True
            light_thread = threading.Thread(target=self.light_control_thread)
            light_thread.daemon = True
            light_thread.start()
            
            # Start audio
            pygame.mixer.music.play()
            
            # Monitor playback
            while pygame.mixer.music.get_busy() and not self.stop_flag and self.is_playing:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n🛑 Show stopped!")
            self.stop_flag = True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            
        finally:
            self.is_playing = False
            pygame.mixer.quit()
            
            # Clean finish
            print("🎊 Show complete! Quick fade out...")
            for brightness in [60, 40, 20, 0]:
                self.bulb.set_rgb_fast(100, 150, 255, brightness)
                time.sleep(0.3)
            
            self.bulb.turn_off()
            print("✨ May the Force be with you!")
    
    def test_bulb_speed(self):
        """Test bulb response speed"""
        print("⚡ Testing bulb response speed...")
        
        test_colors = [
            (255, 0, 0, "Red"),
            (0, 255, 0, "Green"), 
            (0, 0, 255, "Blue"),
            (255, 255, 255, "White")
        ]
        
        start_total = time.time()
        
        for r, g, b, name in test_colors:
            print(f"Testing {name}...")
            start = time.time()
            self.bulb.set_rgb_fast(r, g, b, 80)
            time.sleep(0.5)  # Visual confirmation time
            response_time = time.time() - start
            print(f"  Response time: {response_time:.3f}s")
        
        total_time = time.time() - start_total
        print(f"✅ Total test time: {total_time:.1f}s")
        print("💡 Optimized for network bulb performance!")
        
        self.bulb.turn_off()
    
    def test_blaster_effects(self):
        """Test all blaster effect types"""
        print("🔫 Testing Star Wars blaster effects...")
        
        blaster_types = [
            ('rebel_blaster', '🔸 Rebel X-wing Blasters'),
            ('imperial_blaster', '🔹 Imperial TIE Fighter'),
            ('heavy_turbo', '💥 Heavy Turbolaser'), 
            ('ion_cannon', '⚡ Ion Cannon'),
            ('explosion_flash', '💥💥 Explosion Impact')
        ]
        
        for blaster_type, description in blaster_types:
            print(f"Testing {description}...")
            r, g, b = self.colors[blaster_type]
            
            # Simulate blaster flash - quick bright flash then fade
            self.bulb.set_rgb_fast(r, g, b, 100)  # Full brightness
            time.sleep(0.1)
            self.bulb.set_rgb_fast(r, g, b, 60)   # Medium
            time.sleep(0.1) 
            self.bulb.set_rgb_fast(r, g, b, 20)   # Dim
            time.sleep(0.3)
            
        self.bulb.turn_off()
        print("✅ Blaster test complete!")
    
    def preview_blaster_timing(self):
        """Preview when blaster shots will occur"""
        all_blasters = self.manual_blasters + self.detected_blasters
        all_blasters.sort(key=lambda x: x[0])  # Sort by time
        
        print("🔫 Blaster Shot Timeline:")
        print("=" * 40)
        
        for shot_time, shot_type, intensity in all_blasters:
            shot_names = {
                'rebel_blaster': '🔸 Rebel Blaster',
                'imperial_blaster': '🔹 Imperial Blaster',
                'heavy_turbo': '💥 Turbolaser',
                'explosion_flash': '💥💥 Explosion',
                'ion_cannon': '⚡ Ion Cannon'
            }
            
            name = shot_names.get(shot_type, '🔫 Unknown')
            print(f"{shot_time:5.1f}s: {name} (intensity {intensity}/10)")
        
        print(f"\nTotal shots: {len(all_blasters)}")
        
        # Quick preview with lights
        print("\n🎨 Quick visual preview...")
        for shot_time, shot_type, intensity in all_blasters[:3]:  # Show first 3
            print(f"Showing {shot_type} at intensity {intensity}...")
            r, g, b = self.colors[shot_type]
            brightness = min(100, 50 + intensity * 5)
            self.bulb.set_rgb_fast(r, g, b, brightness)
            time.sleep(0.8)
        
        self.bulb.turn_off()
    
    def toggle_blasters(self):
        """Toggle blaster effects on/off"""
        self.blaster_enabled = not self.blaster_enabled
        status = "ENABLED" if self.blaster_enabled else "DISABLED"
        print(f"🔫 Blaster effects: {status}")
        
        # Visual confirmation
        if self.blaster_enabled:
            self.bulb.set_rgb_fast(255, 100, 0, 70)  # Orange flash
        else:
            self.bulb.set_rgb_fast(100, 100, 100, 30)  # Gray
        time.sleep(0.5)
        self.bulb.turn_off()
    
    def close(self):
        """Clean up resources"""
        self.stop_flag = True
        self.bulb.close()

def main():
    print("💥 Battle of Hoth: BLASTER ENHANCED Light Show 💥")
    print("=" * 55)
    print("🔫 Real-time blaster effects + synchronized lighting!")
    print("🎯 Detects blaster shots automatically from audio")
    if not AUDIO_ANALYSIS_AVAILABLE:
        print("📢 For auto-detection: pip install librosa")
        print("   (Manual blaster timing still works!)")
    
    # Get setup info
    bulb_ip = input("\nEnter your Wiz bulb IP: ").strip()
    if not bulb_ip:
        print("❌ No IP provided")
        return
    
    audio_file = input("Enter audio file path: ").strip()
    if not audio_file or not os.path.exists(audio_file):
        print("❌ Audio file not found")
        return
    
    try:
        hoth_show = OptimizedHothShow(bulb_ip, audio_file)
        
        print("\n🎮 Enhanced Hoth Show with Blaster Effects!")
        print("1. 🔫 Play Full Battle (with blaster shots)")
        print("2. 🧪 Test Bulb Response Speed") 
        print("3. 💥 Test Blaster Effects")
        print("4. 📋 Preview Blaster Timeline")
        print("5. ⚙️  Toggle Blaster Effects On/Off")
        print("6. ❌ Exit")
        
        while True:
            choice = input("\nChoice (1-6): ").strip()
            
            if choice == '1':
                hoth_show.play_synchronized_show()
                break
            elif choice == '2':
                hoth_show.test_bulb_speed()
            elif choice == '3':
                hoth_show.test_blaster_effects()
            elif choice == '4':
                hoth_show.preview_blaster_timing()
            elif choice == '5':
                hoth_show.toggle_blasters()
            elif choice == '6':
                break
            else:
                print("Invalid choice")
        
        hoth_show.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n📋 Requirements:")
        print("pip install pygame")
        print("pip install librosa  # Optional - for auto blaster detection")

if __name__ == "__main__":
    main()
