# Onboard presentation

Open the onboard view (V), then the bottom-right image controls. Real video,
strength, OSD display, OSD burn-in and 0/80/150 ms display delay are independent.
Delay defaults to zero. Normal rendering bypasses the postprocessor when possible.
Photo exports always render a fresh frame to match the unmodified observation
camera and geometry evidence; recording uses the displayed delayed frames.
Burn-in applies to exported photos and the cockpit's canvas recording, while
live OSD remains visible independently. Non-onboard cameras bypass all effects.

暂定：OSD uses the research report's V6-generation layout description as a
provisional reference, pending X1 screenshots. It is not a reproduction or a
claim about X1. Only available state is shown; no invented temperature, DVL,
cable-counter or camera metadata is reported.

The material hook attenuates incoming sunlight by surface depth and spot/point
light by lamp-to-surface distance. The depth pass reconstructs surface-to-camera
range and attenuates RGB separately, completing the total path. Backscatter has
separate RGB coefficients and increases with the authoritative lamp setting.
Exposure uses a center-pixel meter with 900 ms adaptation. Distortion is a mild
radial approximation; grain and block sampling approximate low-light/compression
artifacts. All coefficients, response times and lens parameters are provisional
presentation assumptions, not calibrated water types, sensor models or measured
vehicle specifications. No third-party assets or dependencies are added.

This self-contained render module can later be integrated into T07's compositor.
The bounded eight-target buffer samples at roughly 30 Hz; latency is quantized
by frame rate and initially warms up from the oldest available frame. At high
DPI it consumes additional GPU memory; targets are disposed on resolution change.
