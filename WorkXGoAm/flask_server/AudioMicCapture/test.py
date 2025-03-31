import pyaudio
p = pyaudio.PyAudio()
for i in range(p.get_device_count()):
    info = p.get_device_info_by_index(i)
    print(f"ID {info['index']}: {info['name']} - In:{info['maxInputChannels']} Out:{info['maxOutputChannels']}")
p.terminate()

import soundcard as sc
mics = sc.all_microphones(include_loopback=True)
speakers = sc.all_speakers()
for mic in mics:
    print("Mic:", mic.name)
for spk in speakers:
    print("Speaker:", spk.name)