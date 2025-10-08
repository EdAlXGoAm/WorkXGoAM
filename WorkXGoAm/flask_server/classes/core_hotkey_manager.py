#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Global Hotkey Manager - Gestor centralizado de atajos de teclado globales
Permite configurar y gestionar combinaciones de teclas desde un solo punto
"""

from pynput import keyboard
from typing import Dict, List, Callable, Optional, Set
from dataclasses import dataclass
from enum import Enum


class ModifierKey(Enum):
    """Teclas modificadoras soportadas"""
    CTRL = "ctrl"
    SHIFT = "shift"
    ALT = "alt"
    WIN = "win"


@dataclass
class Hotkey:
    """Representa una combinación de teclas (hotkey)"""
    name: str  # Nombre descriptivo del hotkey
    modifiers: Set[ModifierKey]  # Teclas modificadoras (CTRL, SHIFT, ALT, etc.)
    key: str  # Tecla principal (ej: 'u', 'f', 'escape')
    callback: Callable  # Función a ejecutar cuando se detecta la combinación
    enabled: bool = True  # Si el hotkey está activo o no
    
    def __str__(self):
        mod_str = "+".join([m.value.upper() for m in sorted(self.modifiers, key=lambda x: x.value)])
        return f"{mod_str}+{self.key.upper()}" if mod_str else self.key.upper()


class GlobalHotkeyManager:
    """
    Gestor centralizado de atajos de teclado globales.
    Permite registrar, gestionar y detectar combinaciones de teclas.
    """
    
    def __init__(self, debug_mode: bool = False):
        """
        Inicializa el gestor de hotkeys.
        
        Args:
            debug_mode: Si True, muestra información de debug
        """
        self.debug_mode = debug_mode
        self.hotkeys: Dict[str, Hotkey] = {}
        self.keyboard_listener: Optional[keyboard.Listener] = None
        
        # Estado actual de las teclas presionadas
        self._pressed_keys: Set[str] = set()
        self._pressed_modifiers: Set[ModifierKey] = set()
        
        # Mapeo de teclas de pynput a nuestros modificadores
        self._modifier_mapping = {
            keyboard.Key.ctrl_l: ModifierKey.CTRL,
            keyboard.Key.ctrl_r: ModifierKey.CTRL,
            keyboard.Key.shift: ModifierKey.SHIFT,
            keyboard.Key.shift_r: ModifierKey.SHIFT,
            keyboard.Key.alt_l: ModifierKey.ALT,
            keyboard.Key.alt_r: ModifierKey.ALT,
            keyboard.Key.alt_gr: ModifierKey.ALT,
            keyboard.Key.cmd: ModifierKey.WIN,
            keyboard.Key.cmd_r: ModifierKey.WIN,
        }
        
        # Mapeo de códigos virtuales (para cuando las teclas se presionan con modificadores)
        self._vk_mapping = {
            85: 'u',  # U
            89: 'y',  # Y
            70: 'f',  # F
            71: 'g',  # G
            72: 'h',  # H
            # Agregar más según sea necesario
        }
    
    def register_hotkey(self, 
                       name: str,
                       modifiers: List[str],
                       key: str,
                       callback: Callable,
                       enabled: bool = True) -> None:
        """
        Registra un nuevo hotkey.
        
        Args:
            name: Nombre único identificador del hotkey
            modifiers: Lista de modificadores ['ctrl', 'shift', 'alt', 'win']
            key: Tecla principal (ej: 'u', 'f', 'escape')
            callback: Función a ejecutar cuando se detecta la combinación
            enabled: Si el hotkey está activo desde el inicio
            
        Example:
            manager.register_hotkey(
                name="bring_face_front",
                modifiers=['ctrl', 'shift', 'alt'],
                key='u',
                callback=lambda: print("Hotkey activated!")
            )
        """
        # Convertir strings de modificadores a enum
        modifier_set = set()
        for mod_str in modifiers:
            mod_str_lower = mod_str.lower()
            if mod_str_lower == 'ctrl':
                modifier_set.add(ModifierKey.CTRL)
            elif mod_str_lower == 'shift':
                modifier_set.add(ModifierKey.SHIFT)
            elif mod_str_lower == 'alt':
                modifier_set.add(ModifierKey.ALT)
            elif mod_str_lower == 'win':
                modifier_set.add(ModifierKey.WIN)
        
        hotkey = Hotkey(
            name=name,
            modifiers=modifier_set,
            key=key.lower(),
            callback=callback,
            enabled=enabled
        )
        
        self.hotkeys[name] = hotkey
        
        if self.debug_mode:
            print(f"[HotkeyManager] Registrado: {name} -> {hotkey}")
    
    def unregister_hotkey(self, name: str) -> bool:
        """
        Elimina un hotkey registrado.
        
        Args:
            name: Nombre del hotkey a eliminar
            
        Returns:
            True si se eliminó, False si no existía
        """
        if name in self.hotkeys:
            del self.hotkeys[name]
            if self.debug_mode:
                print(f"[HotkeyManager] Desregistrado: {name}")
            return True
        return False
    
    def enable_hotkey(self, name: str) -> bool:
        """Habilita un hotkey deshabilitado"""
        if name in self.hotkeys:
            self.hotkeys[name].enabled = True
            if self.debug_mode:
                print(f"[HotkeyManager] Habilitado: {name}")
            return True
        return False
    
    def disable_hotkey(self, name: str) -> bool:
        """Deshabilita un hotkey sin eliminarlo"""
        if name in self.hotkeys:
            self.hotkeys[name].enabled = False
            if self.debug_mode:
                print(f"[HotkeyManager] Deshabilitado: {name}")
            return True
        return False
    
    def _on_press(self, key):
        """Callback interno cuando se presiona una tecla"""
        try:
            # Detectar modificadores
            if key in self._modifier_mapping:
                modifier = self._modifier_mapping[key]
                self._pressed_modifiers.add(modifier)
                if self.debug_mode:
                    print(f"[HotkeyManager] Modificador presionado: {modifier.value}")
            
            # Detectar tecla principal
            key_char = None
            if hasattr(key, 'char') and key.char:
                key_char = key.char.lower()
            elif hasattr(key, 'vk') and key.vk in self._vk_mapping:
                key_char = self._vk_mapping[key.vk]
            
            if key_char:
                self._pressed_keys.add(key_char)
                if self.debug_mode:
                    print(f"[HotkeyManager] Tecla presionada: {key_char}")
                
                # Verificar si algún hotkey coincide
                self._check_hotkeys()
        
        except Exception as e:
            if self.debug_mode:
                print(f"[HotkeyManager] Error en _on_press: {e}")
    
    def _on_release(self, key):
        """Callback interno cuando se suelta una tecla"""
        try:
            # Resetear modificadores
            if key in self._modifier_mapping:
                modifier = self._modifier_mapping[key]
                self._pressed_modifiers.discard(modifier)
                if self.debug_mode:
                    print(f"[HotkeyManager] Modificador soltado: {modifier.value}")
            
            # Resetear tecla principal
            key_char = None
            if hasattr(key, 'char') and key.char:
                key_char = key.char.lower()
            elif hasattr(key, 'vk') and key.vk in self._vk_mapping:
                key_char = self._vk_mapping[key.vk]
            
            if key_char:
                self._pressed_keys.discard(key_char)
                if self.debug_mode:
                    print(f"[HotkeyManager] Tecla soltada: {key_char}")
        
        except Exception as e:
            if self.debug_mode:
                print(f"[HotkeyManager] Error en _on_release: {e}")
    
    def _check_hotkeys(self):
        """Verifica si alguna combinación registrada está activa"""
        for name, hotkey in self.hotkeys.items():
            if not hotkey.enabled:
                continue
            
            # Verificar si los modificadores coinciden
            modifiers_match = self._pressed_modifiers == hotkey.modifiers
            
            # Verificar si la tecla principal está presionada
            key_match = hotkey.key in self._pressed_keys
            
            if modifiers_match and key_match:
                if self.debug_mode:
                    print(f"[HotkeyManager] ✓ Hotkey detectado: {name} ({hotkey})")
                
                try:
                    # Ejecutar el callback
                    hotkey.callback()
                except Exception as e:
                    print(f"[HotkeyManager] Error ejecutando callback para {name}: {e}")
                
                # Limpiar las teclas presionadas para evitar ejecuciones múltiples
                self._pressed_keys.clear()
    
    def start(self):
        """Inicia el listener de teclado global"""
        if self.keyboard_listener is None:
            self.keyboard_listener = keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release
            )
            self.keyboard_listener.start()
            
            if self.debug_mode:
                print(f"[HotkeyManager] Listener iniciado con {len(self.hotkeys)} hotkeys registrados")
                for name, hotkey in self.hotkeys.items():
                    status = "✓" if hotkey.enabled else "✗"
                    print(f"  {status} {name}: {hotkey}")
    
    def stop(self):
        """Detiene el listener de teclado"""
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
            
            if self.debug_mode:
                print("[HotkeyManager] Listener detenido")
    
    def get_registered_hotkeys(self) -> Dict[str, str]:
        """Retorna un diccionario con todos los hotkeys registrados"""
        return {name: str(hotkey) for name, hotkey in self.hotkeys.items()}
    
    def __del__(self):
        """Cleanup al destruir el objeto"""
        self.stop()

