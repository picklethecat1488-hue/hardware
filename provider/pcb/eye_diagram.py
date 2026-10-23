"""PCIe high-speed transmission line signal integrity and Eye Diagram simulation engine."""

import math
from typing import List, Tuple, Dict, Any, Optional
import numpy as np
from pydantic import BaseModel, Field


# Physical constants
SPEED_OF_LIGHT_M_S = 299792458.0
PERMEABILITY_VACUUM = 4.0 * math.pi * 1e-7
COPPER_RESISTIVITY_OHM_M = 1.68e-8
PCIE_GEN4_NYQUIST_GHZ = 8.0
PCIE_GEN4_MIN_EYE_HEIGHT_MV = 15.0
PCIE_GEN4_MIN_EYE_WIDTH_UI = 0.30


class EyeDiagramConfig(BaseModel):
    """Configuration parameters for PCIe high-speed transmission line eye diagram simulation."""

    pcie_gen: int = Field(default=4, description="PCIe generation standard (3, 4, or 5)")
    data_rate_gts: float = Field(default=16.0, gt=0.0, description="Data transfer rate in GigaTransfers per second")
    trace_length_mm: float = Field(default=100.0, gt=0.0, description="Conductor trace physical routing length in mm")
    characteristic_impedance_ohms: float = Field(default=85.0, gt=0.0, description="Target differential impedance")
    trace_width_mm: float = Field(default=0.15, gt=0.0, description="Trace conductor width in mm")
    dielectric_constant: float = Field(default=4.2, gt=1.0, description="Substrate relative permittivity (epsilon_r)")
    loss_tangent: float = Field(default=0.018, gt=0.0, description="Dielectric loss tangent (tan delta)")
    copper_roughness_um: float = Field(default=1.5, ge=0.0, description="RMS copper surface roughness in micrometers")
    voltage_swing_mv: float = Field(default=800.0, gt=0.0, description="Transmitter differential peak-to-peak voltage")
    rise_time_ps: float = Field(default=20.0, gt=0.0, description="Transmitter 20-80% step rise time in picoseconds")
    samples_per_ui: int = Field(default=32, ge=8, description="Oversampling rate per unit interval (UI)")
    num_bits: int = Field(default=511, ge=127, description="Total PRBS bit count for eye synthesis")
    ctle_peaking_db: float = Field(default=6.0, ge=0.0, description="Receiver CTLE equalization boost at Nyquist")


class EyeDiagramResult(BaseModel):
    """Quantitative signal integrity figures of merit and folded 2D eye diagram traces."""

    pcie_gen: int
    data_rate_gts: float
    ui_ps: float
    trace_length_mm: float
    attenuation_db: float
    eye_height_mv: float
    eye_width_ps: float
    eye_width_ui: float
    jitter_ps: float
    mask_margin_mv: float
    passed: bool
    folded_time_ps: List[float]
    folded_traces: List[List[float]]
    compliance_mask: Dict[str, Any]


def generate_prbs9(num_bits: int = 511) -> List[int]:
    """Generate pseudo-random binary sequence of order 9 (PRBS-9) using polynomial x^9 + x^5 + 1."""
    state = 0x1FF  # Non-zero 9-bit seed
    bits = []
    for _ in range(num_bits):
        new_bit = ((state >> 8) ^ (state >> 4)) & 1
        state = ((state << 1) | new_bit) & 0x1FF
        bits.append(new_bit)
    return bits


class EyeDiagramSimulator:
    """Simulates high-speed channel attenuation, dispersion, CTLE receiver equalization, and eye diagrams."""

    def __init__(self, config: EyeDiagramConfig):
        """Initialize the simulator with high-speed channel and signaling configurations."""
        self.config = config
        self.ui_sec = 1.0 / (config.data_rate_gts * 1e9)
        self.ui_ps = self.ui_sec * 1e12

    def simulate(self) -> EyeDiagramResult:
        """Execute full-wave channel impulse response filtering and eye diagram analysis."""
        bits = generate_prbs9(self.config.num_bits)
        n_samples_ui = self.config.samples_per_ui
        dt = self.ui_sec / n_samples_ui
        total_samples = len(bits) * n_samples_ui

        # 1. Generate TX Non-Return-to-Zero (NRZ) waveform with exponential rise/fall edge rate
        tx_waveform = np.zeros(total_samples, dtype=np.float64)
        v_high = self.config.voltage_swing_mv / 2.0
        v_low = -self.config.voltage_swing_mv / 2.0
        tau = (self.config.rise_time_ps * 1e-12) / 2.2

        current_v = v_low if bits[0] == 0 else v_high
        for bit_idx, bit in enumerate(bits):
            target_v = v_high if bit == 1 else v_low
            start_sample = bit_idx * n_samples_ui
            for s in range(n_samples_ui):
                idx = start_sample + s
                current_v += (target_v - current_v) * (1.0 - math.exp(-dt / max(tau, 1e-15)))
                tx_waveform[idx] = current_v

        # 2. Compute channel frequency response H(f) over FFT bins
        freqs = np.fft.rfftfreq(total_samples, d=dt)
        h_channel = np.ones(len(freqs), dtype=np.complex128)

        length_m = self.config.trace_length_mm * 1e-3
        er = self.config.dielectric_constant
        tan_d = self.config.loss_tangent
        w_m = self.config.trace_width_mm * 1e-3
        z0 = self.config.characteristic_impedance_ohms
        roughness_m = self.config.copper_roughness_um * 1e-6

        # Avoid divide-by-zero at DC
        valid_freqs = freqs[1:]
        alpha_d = (math.pi * valid_freqs * math.sqrt(er) * tan_d) / SPEED_OF_LIGHT_M_S

        # Skin effect skin depth
        skin_depth = np.sqrt(COPPER_RESISTIVITY_OHM_M / (math.pi * valid_freqs * PERMEABILITY_VACUUM))
        surface_resistance = COPPER_RESISTIVITY_OHM_M / skin_depth
        roughness_factor = 1.0 + (2.0 / math.pi) * np.arctan(
            1.4 * np.square(roughness_m / np.maximum(skin_depth, 1e-12))
        )
        alpha_c = (surface_resistance * roughness_factor) / (2.0 * z0 * w_m)

        alpha_total = alpha_d + alpha_c
        phase_beta = (2.0 * math.pi * valid_freqs * math.sqrt(er)) / SPEED_OF_LIGHT_M_S

        h_channel[1:] = np.exp(-alpha_total * length_m - 1j * phase_beta * length_m)

        # 3. Apply Continuous-Time Linear Equalization (CTLE) peaking boost at Nyquist
        nyquist_hz = (self.config.data_rate_gts * 1e9) / 2.0
        boost_linear = 10.0 ** (self.config.ctle_peaking_db / 20.0)
        # CTLE zero-pole transfer function model
        w_z = 2.0 * math.pi * (nyquist_hz / 3.0)
        w_p1 = 2.0 * math.pi * nyquist_hz
        w_p2 = 2.0 * math.pi * (nyquist_hz * 2.5)

        s_freq = 1j * 2.0 * math.pi * freqs
        h_ctle = boost_linear * (1.0 + s_freq / w_z) / ((1.0 + s_freq / w_p1) * (1.0 + s_freq / w_p2))
        # Normalize CTLE DC gain to unity
        h_ctle /= np.abs(h_ctle[0]) if abs(h_ctle[0]) > 0.0 else 1.0

        # Frequency domain convolution
        tx_fft = np.fft.rfft(tx_waveform)
        rx_fft = tx_fft * h_channel * h_ctle
        rx_waveform = np.fft.irfft(rx_fft, n=total_samples)

        # Channel attenuation at Nyquist in dB
        nyquist_idx = np.argmin(np.abs(freqs - nyquist_hz))
        nyquist_att_db = -20.0 * math.log10(max(abs(h_channel[nyquist_idx]), 1e-6))

        # 4. Fold signal into 2-UI Eye Diagram segments
        ui_samples = n_samples_ui
        two_ui_samples = 2 * ui_samples
        num_traces = (total_samples // two_ui_samples) - 1

        folded_time = [round(i * (2.0 * self.ui_ps / two_ui_samples), 2) for i in range(two_ui_samples)]
        folded_traces = []

        # Discard initial transient (first 10 UIs)
        start_idx = 10 * ui_samples
        while start_idx + two_ui_samples <= total_samples:
            segment = rx_waveform[start_idx : start_idx + two_ui_samples].tolist()
            folded_traces.append([round(v, 2) for v in segment])
            start_idx += two_ui_samples

        # 5. Extract Eye Height, Eye Width, and Jitter metrics
        # Eye center is at 1.0 UI (sample index = ui_samples)
        center_samples = [trace[ui_samples] for trace in folded_traces]
        high_levels = [v for v in center_samples if v > 0.0]
        low_levels = [v for v in center_samples if v < 0.0]

        min_high = min(high_levels) if high_levels else 0.0
        max_low = max(low_levels) if low_levels else 0.0
        eye_height = max(0.0, min_high - max_low)

        # Zero crossing jitter analysis around left transition (0.5 UI) and right transition (1.5 UI)
        crossings_left = []
        crossings_right = []
        idx_left_center = ui_samples // 2
        idx_right_center = ui_samples + (ui_samples // 2)

        for trace in folded_traces:
            # Check left crossing
            for i in range(max(0, idx_left_center - ui_samples // 4), idx_left_center + ui_samples // 4):
                if (trace[i] <= 0.0 <= trace[i + 1]) or (trace[i] >= 0.0 >= trace[i + 1]):
                    # Linear interpolation for zero crossing time
                    denom = trace[i + 1] - trace[i]
                    frac = (0.0 - trace[i]) / denom if abs(denom) > 1e-9 else 0.0
                    crossings_left.append((i + frac) * (self.ui_ps / ui_samples))
                    break

            # Check right crossing
            for i in range(idx_right_center - ui_samples // 4, idx_right_center + ui_samples // 4):
                if (trace[i] <= 0.0 <= trace[i + 1]) or (trace[i] >= 0.0 >= trace[i + 1]):
                    denom = trace[i + 1] - trace[i]
                    frac = (0.0 - trace[i]) / denom if abs(denom) > 1e-9 else 0.0
                    crossings_right.append((i + frac) * (self.ui_ps / ui_samples))
                    break

        if crossings_left and crossings_right:
            jitter_ps = max(crossings_left) - min(crossings_left)
            t_left_inner = max(crossings_left)
            t_right_inner = min(crossings_right)
            eye_width_ps = max(0.0, t_right_inner - t_left_inner)
        else:
            jitter_ps = 15.0
            eye_width_ps = max(0.0, self.ui_ps - jitter_ps)

        eye_width_ui = eye_width_ps / self.ui_ps

        # Compliance evaluation against PCIe Gen4 standard
        passed = (eye_height >= PCIE_GEN4_MIN_EYE_HEIGHT_MV) and (eye_width_ui >= PCIE_GEN4_MIN_EYE_WIDTH_UI)
        mask_margin_mv = eye_height - PCIE_GEN4_MIN_EYE_HEIGHT_MV

        compliance_mask = {
            "center_time_ps": self.ui_ps,
            "min_height_mv": PCIE_GEN4_MIN_EYE_HEIGHT_MV,
            "min_width_ui": PCIE_GEN4_MIN_EYE_WIDTH_UI,
            "mask_polygon": [
                [self.ui_ps - (PCIE_GEN4_MIN_EYE_WIDTH_UI * self.ui_ps) / 2.0, 0.0],
                [self.ui_ps, PCIE_GEN4_MIN_EYE_HEIGHT_MV / 2.0],
                [self.ui_ps + (PCIE_GEN4_MIN_EYE_WIDTH_UI * self.ui_ps) / 2.0, 0.0],
                [self.ui_ps, -PCIE_GEN4_MIN_EYE_HEIGHT_MV / 2.0],
            ],
        }

        return EyeDiagramResult(
            pcie_gen=self.config.pcie_gen,
            data_rate_gts=self.config.data_rate_gts,
            ui_ps=round(self.ui_ps, 3),
            trace_length_mm=self.config.trace_length_mm,
            attenuation_db=round(nyquist_att_db, 2),
            eye_height_mv=round(eye_height, 2),
            eye_width_ps=round(eye_width_ps, 2),
            eye_width_ui=round(eye_width_ui, 3),
            jitter_ps=round(jitter_ps, 2),
            mask_margin_mv=round(mask_margin_mv, 2),
            passed=passed,
            folded_time_ps=folded_time,
            folded_traces=folded_traces[:40],  # Return up to 40 overlaid waveforms for rendering
            compliance_mask=compliance_mask,
        )
