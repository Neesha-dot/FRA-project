import numpy as np

def extract_features(freq, mag):
    """MUST MATCH the exact logic used while training the model"""

    modal_1 = freq[np.argmax(mag)]
    modal_2 = np.mean(freq)
    modal_3 = np.max(freq)

    modal_spacing = modal_3 - modal_1

    # Energy in bands
    E_low = np.sum(mag[freq < 1000])
    E_mid = np.sum(mag[(freq >= 1000) & (freq < 20000)])
    E_high = np.sum(mag[freq >= 20000])

    midband_turbulence = np.std(mag[(freq > 2000) & (freq < 10000)])
    hf_decay_rate = (mag[-1] - mag[len(mag)//2]) / (freq[-1] - freq[len(freq)//2])
    global_attenuation = np.max(mag) - np.min(mag)

    return {
        "modal_1": float(modal_1),
        "modal_2": float(modal_2),
        "modal_3": float(modal_3),
        "modal_spacing_index": float(modal_spacing),
        "E_low": float(E_low),
        "E_mid": float(E_mid),
        "E_high": float(E_high),
        "midband_turbulence": float(midband_turbulence),
        "hf_decay_rate": float(hf_decay_rate),
        "global_attenuation": float(global_attenuation)
    }
